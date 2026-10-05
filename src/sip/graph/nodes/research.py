"""Research worker: executes one research task (one ``Send`` branch).

Three methods share one output shape (``ResearchOutput``):
* web search -> fetch -> screen -> extract -> verify quotes -> assess source quality;
* internal document search over *sanitised, released* documents only;
* deterministic dataset analysis.
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from datetime import date
from typing import Any

import structlog
from langgraph.runtime import Runtime
from langsmith.run_helpers import tracing_context

from sip.agents.contracts import EvidenceDraft, SourceView
from sip.domain import (
    Actor,
    AuditAction,
    AuditEvent,
    Evidence,
    EvidenceNeed,
    Freshness,
    HypothesisLink,
    QuoteVerification,
    ResearchBudget,
    ResearchMethod,
    ResearchTask,
    Source,
    SourceOrigin,
    SourceType,
    TaskStatus,
    Usage,
    utcnow,
)
from sip.domain.hypotheses import Hypothesis
from sip.domain.sources import RetrievalMethod
from sip.evidence.ledger import evidence_from_analysis, stable_id
from sip.graph.context import InvestigationContext
from sip.graph.helpers import audit, policy_event, usage_from
from sip.graph.state import ResearchOutput
from sip.research.injection import is_suspicious
from sip.research.search.base import FetchError, SearchError
from sip.research.text import Passage, normalise, split_passages, verify_quote
from sip.retrieval.bm25 import BM25Index
from sip.tools.analytics import AnalysisError, run_operation

log = structlog.get_logger(__name__)
WEB = Actor.agent("web_researcher")
DOCS = Actor.agent("document_researcher")
ANALYST = Actor.agent("data_analyst")

_DEFAULT_NEED = {
    SourceType.OFFICIAL_STATISTICS: EvidenceNeed.STATISTIC,
    SourceType.GOVERNMENT_POLICY: EvidenceNeed.POLICY,
    SourceType.REGULATOR: EvidenceNeed.POLICY,
    SourceType.COMPETITOR_OFFICIAL: EvidenceNeed.COMPETITOR_OFFER,
    SourceType.CRM_RECORD: EvidenceNeed.CUSTOMER_FEEDBACK,
    SourceType.INTERNAL_DOCUMENT: EvidenceNeed.INTERNAL_PERFORMANCE,
    SourceType.INTERNAL_DATASET: EvidenceNeed.INTERNAL_PERFORMANCE,
    SourceType.TRADE_PRESS: EvidenceNeed.MARKET_INTERPRETATION,
    SourceType.NEWS: EvidenceNeed.MARKET_INTERPRETATION,
    SourceType.COMMENTARY: EvidenceNeed.MARKET_INTERPRETATION,
    SourceType.INDUSTRY_BODY: EvidenceNeed.MARKET_INTERPRETATION,
    SourceType.STANDARDS_BODY: EvidenceNeed.MARKET_INTERPRETATION,
}


_PSEUDONYM = re.compile(r"\b(PERSON|STAFF|EMPLOYER|EMAIL|PHONE|POSTCODE|NATIONAL_ID)_\d{4}\b|\[WITHHELD")


def safe_query(query: str) -> bool:
    """Queries go to a third-party search provider: never send pseudonyms or withheld markers, which
    would reveal that (and roughly what) confidential material exists."""
    return not _PSEUDONYM.search(query) and len(query) <= 300


def _source_view(s: Source) -> SourceView:
    return SourceView(
        id=s.id,
        title=s.title,
        publisher=s.publisher,
        source_type=s.source_type,
        dated=s.effective_date.isoformat() if s.effective_date else None,
        url=s.canonical_url,
        synthetic=s.synthetic,
    )


async def research(payload: dict[str, Any], runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    task: ResearchTask = payload["task"]
    with tracing_context(
        metadata={"research_task_id": task.id, "method": task.method.value, "hypothesis_ids": task.hypothesis_ids}
    ):
        try:
            if task.method == ResearchMethod.DATASET_ANALYSIS:
                out, usage, events = await _dataset(task, payload, ctx)
            elif task.method == ResearchMethod.WEB_SEARCH:
                out, usage, events = await _web(task, payload, ctx)
            else:
                out, usage, events = await _documents(task, payload, ctx)
        except Exception as exc:  # a failed task must not fail the investigation
            log.warning("research.task_failed", task_id=task.id, error=exc.__class__.__name__)
            failed = task.model_copy(
                update={
                    "status": TaskStatus.FAILED,
                    "completed_at": utcnow(),
                    "status_reason": f"{exc.__class__.__name__}: {str(exc)[:200]}",
                }
            )
            return {
                "staging": [ResearchOutput(task=failed)],
                "audit": [
                    audit(
                        Actor.system(),
                        AuditAction.TASK_COMPLETED,
                        f"Task failed: {task.question[:120]}",
                        subject_type="task",
                        subject_id=task.id,
                        status="failed",
                    )
                ],
            }
    return {"staging": [out], "usage": usage, "audit": events}


def _remaining(payload: dict[str, Any]) -> tuple[int, int]:
    budget: ResearchBudget = payload["budget"]
    used: Usage = payload.get("usage") or Usage()
    return budget.max_searches - used.searches, budget.max_fetches - used.fetches


def _done(task: ResearchTask, summary: str, evidence: list[Evidence], sources: list[Source]) -> ResearchTask:
    return task.model_copy(
        update={
            "status": TaskStatus.DONE,
            "completed_at": utcnow(),
            "result_summary": summary,
            "evidence_ids": [e.id for e in evidence],
            "source_ids": sorted({s.id for s in sources}),
        }
    )


# ---- dataset analysis -----------------------------------------------------------------------------
async def _dataset(task: ResearchTask, payload: dict[str, Any], ctx: InvestigationContext):  # type: ignore[no-untyped-def]
    assert task.analysis is not None
    a = task.analysis
    released: dict[str, str] = payload["released_dataset_ids"]
    ds = ctx.catalog.get(a.dataset_id)
    decision = ctx.governance.evaluate(
        "analyse_internal_dataset",
        personal_data=ds.manifest.classification.personal_data.value,
        confidentiality=ds.manifest.classification.confidentiality.value,
    )
    events = [policy_event(ANALYST, decision, "task", task.id)]
    if not decision.agent_may_proceed:
        blocked = task.model_copy(
            update={
                "status": TaskStatus.BLOCKED_UNAVAILABLE,
                "status_reason": decision.reason,
                "completed_at": utcnow(),
            }
        )
        return ResearchOutput(task=blocked), Usage(), events
    try:
        result = run_operation(ctx.catalog, a.operation, a.dataset_id, a.params)
    except AnalysisError as exc:
        failed = task.model_copy(
            update={"status": TaskStatus.FAILED, "status_reason": str(exc), "completed_at": utcnow()}
        )
        return ResearchOutput(task=failed), Usage(analyses=1), events
    # Evidence is attributed to the dataset that carries the measured quantity of interest.
    primary_id = result.dataset_ids[0]
    source_id = released[primary_id]
    # Placeholder source object for typing; the canonical Source is already in state from intake.
    m = ctx.catalog.get(primary_id).manifest
    src = Source(
        id=source_id,
        origin=SourceOrigin.INTERNAL,
        source_type=m.source_type,
        title=m.title,
        retrieval_method=RetrievalMethod.DATASET_QUERY,
        published_on=m.published_on,
    )
    evidence = evidence_from_analysis(result, task, src, payload["hypotheses"], ctx.taxonomy)
    if len(result.dataset_ids) > 1:  # e.g. own vs market: the market side is primary evidence too
        evidence = [
            e.model_copy(update={"locator": (e.locator or "") + f" datasets={result.dataset_ids}"}) for e in evidence
        ]
    evidence = [_with_quality(e, src, ctx, payload["as_of"]) for e in evidence]
    events.append(
        audit(
            ANALYST,
            AuditAction.TASK_COMPLETED,
            result.summary[:200],
            subject_type="task",
            subject_id=task.id,
            operation=a.operation,
            evidence=len(evidence),
        )
    )
    return (
        ResearchOutput(task=_done(task, result.summary, evidence, []), evidence=evidence),
        Usage(analyses=1),
        events,
    )


def _with_quality(e: Evidence, src: Source, ctx: InvestigationContext, as_of: date) -> Evidence:
    q = ctx.quality.assess(src, e.need, as_of)
    flags = list(e.flags) + (["stale"] if q.freshness == Freshness.STALE and "stale" not in e.flags else [])
    return e.model_copy(update={"quality": q, "flags": flags})


# ---- extraction shared by web and documents --------------------------------------------------------
async def _extract(
    task: ResearchTask,
    src: Source,
    passages: list[Passage],
    payload: dict[str, Any],
    ctx: InvestigationContext,
    actor: Actor,
) -> tuple[list[Evidence], Usage]:
    hyps: list[Hypothesis] = payload["hypotheses"]
    by_index = {p.index: p for p in passages}
    flagged = {p.index for p in passages if is_suspicious(p.text)}
    drafts, calls = await ctx.reasoner.extract(task.question, hyps, _source_view(src), passages)
    hyp_ids = {h.id: h for h in hyps}
    out: list[Evidence] = []
    for d in drafts:
        ev = _evidence_from_draft(d, task, src, by_index, flagged, hyp_ids, ctx, payload["as_of"], actor)
        if ev is not None:
            out.append(ev)
    return out, usage_from(calls)


def _evidence_from_draft(
    d: EvidenceDraft,
    task: ResearchTask,
    src: Source,
    by_index: dict[int, Passage],
    flagged: set[int],
    hyps: dict[str, Hypothesis],
    ctx: InvestigationContext,
    as_of: date,
    actor: Actor,
) -> Evidence | None:
    passage = by_index.get(d.passage_index)
    if passage is None:
        return None
    verified = verify_quote(d.quote, passage.text)
    links = [
        HypothesisLink(hypothesis_id=lk.hypothesis_id, stance=lk.stance, rationale=lk.rationale)
        for lk in d.links
        if lk.hypothesis_id in hyps
    ]
    need = _DEFAULT_NEED.get(src.source_type)
    if need is None:
        cats = [
            ctx.taxonomy.categories[hyps[lk.hypothesis_id].category]
            for lk in links
            if hyps[lk.hypothesis_id].category in ctx.taxonomy.categories
        ]
        need = cats[0].evidence_need if cats else EvidenceNeed.MARKET_INTERPRETATION
    flags = []
    if d.passage_index in flagged or is_suspicious(d.quote):
        flags.append("injection_suspected")
    if not verified:
        flags.append("quote_not_verified")
    entities, _dims = ctx.catalog.resolve_mentions(d.quote)
    ev = Evidence(
        id=stable_id("evd", src.id, normalise(d.quote)),
        source_id=src.id,
        task_id=task.id,
        statement=d.statement,
        quote=d.quote,
        locator=f"passage {d.passage_index}",
        kind=d.kind,
        need=need,
        relevance=d.relevance,
        links=links,
        segments=sorted(entities),
        verification=QuoteVerification.VERIFIED if verified else QuoteVerification.NOT_FOUND,
        flags=flags,
        extracted_by=actor,
        observed_on=src.effective_date,
    )
    return _with_quality(ev, src, ctx, as_of)


# ---- web ------------------------------------------------------------------------------------------
async def _web(task: ResearchTask, payload: dict[str, Any], ctx: InvestigationContext):  # type: ignore[no-untyped-def]
    events: list[AuditEvent] = []
    usage = Usage()
    if ctx.search is None or ctx.fetcher is None:
        blocked = task.model_copy(
            update={
                "status": TaskStatus.BLOCKED_UNAVAILABLE,
                "completed_at": utcnow(),
                "status_reason": "No search provider configured.",
            }
        )
        return ResearchOutput(task=blocked), usage, events
    decision = ctx.governance.evaluate("search_public_web")
    events.append(policy_event(WEB, decision, "task", task.id))
    searches_left, fetches_left = _remaining(payload)
    known = set(payload["known_urls"])
    candidates: list[str] = []
    for q in (task.queries or [task.question])[:2]:
        if searches_left <= 0:
            break
        if not safe_query(q):
            events.append(
                audit(
                    WEB,
                    AuditAction.ACTION_REFUSED,
                    "Search query withheld: contains pseudonymised or withheld internal content.",
                    subject_type="task",
                    subject_id=task.id,
                )
            )
            continue
        try:
            results = await ctx.search.search(q, ctx.results_per_query)
        except SearchError as exc:
            events.append(audit(WEB, AuditAction.TASK_SKIPPED, f"Search failed: {exc}", subject_id=task.id))
            continue
        usage.searches += 1
        searches_left -= 1
        for r in results:
            if r.url not in candidates:
                candidates.append(r.url)
    duplicates = sum(1 for u in candidates if u in known)
    fresh = [u for u in candidates if u not in known][: min(ctx.fetches_per_task, max(0, fetches_left))]
    sources: list[Source] = []
    documents: dict[str, str] = {}
    evidence: list[Evidence] = []

    async def read(url: str) -> tuple[Source | None, str, list[Evidence], Usage, list[AuditEvent]]:
        """Fetch, screen and extract one page. Pages within a task are processed concurrently."""
        local: list[AuditEvent] = []
        try:
            page = await ctx.fetcher.fetch(url)  # type: ignore[union-attr]
        except FetchError as exc:
            local.append(audit(WEB, AuditAction.TASK_SKIPPED, f"Fetch refused/failed: {exc}", subject_id=task.id))
            return None, "", [], Usage(), local
        src = Source(
            id=stable_id("src", page.url),
            origin=SourceOrigin.EXTERNAL_WEB,
            source_type=page.source_type_hint or SourceType.UNKNOWN,
            title=page.title,
            publisher=page.publisher,
            canonical_url=page.url,
            domain=page.domain,
            published_on=page.published_on,
            updated_on=page.updated_on,
            content_hash=page.sha256,
            retrieval_method=RetrievalMethod.WEB_SEARCH,
            retrieval_provider=ctx.search.name,  # type: ignore[union-attr]
            discovered_by_task_id=task.id,
            synthetic=page.synthetic,
            injection_flags=page.injection_flags,
        )
        if page.injection_flags:
            local.append(
                audit(
                    WEB,
                    AuditAction.INJECTION_FLAGGED,
                    f"Instruction-like content in '{page.title}'",
                    subject_type="source",
                    subject_id=src.id,
                    flags=page.injection_flags,
                )
            )
        found, u = await _extract(task, src, split_passages(page.text)[:40], payload, ctx, WEB)
        return src, page.text, found, u + Usage(fetches=1), local

    for src, text, found, u, local in await asyncio.gather(*(read(url) for url in fresh)):
        events.extend(local)
        usage = usage + u
        if src is None:
            continue
        sources.append(src)
        documents[src.id] = text
        evidence.extend(found)
    summary = (
        f"{usage.searches} search(es), {len(sources)} new source(s), {duplicates} already-known "
        f"source(s) skipped, {len(evidence)} evidence item(s)."
    )
    events.append(audit(WEB, AuditAction.TASK_COMPLETED, summary, subject_type="task", subject_id=task.id))
    out = ResearchOutput(
        task=_done(task, summary, evidence, sources),
        sources=sources,
        documents=documents,
        evidence=evidence,
        duplicates_skipped=duplicates,
    )
    return out, usage, events


# ---- internal documents -----------------------------------------------------------------------------
async def _documents(task: ResearchTask, payload: dict[str, Any], ctx: InvestigationContext):  # type: ignore[no-untyped-def]
    decision = ctx.governance.evaluate("read_sanitised_document")
    events = [policy_event(DOCS, decision, "task", task.id)]
    docs: dict[str, str] = payload["internal_documents"]
    srcs: dict[str, Source] = payload["internal_sources"]
    index = BM25Index()
    passages: dict[str, list[Passage]] = {}
    for sid, text in docs.items():
        passages[sid] = split_passages(text)
        for p in passages[sid]:
            index.add(f"{sid}#{p.index}", p.text)
    hits = index.search(" ".join(task.queries or [task.question]), k=10)
    chosen: dict[str, list[Passage]] = defaultdict(list)
    for key, _score in hits:
        sid, idx = key.split("#")
        chosen[sid].append(passages[sid][int(idx)])
    evidence: list[Evidence] = []
    usage = Usage()
    for sid, ps in chosen.items():
        found, u = await _extract(task, srcs[sid], sorted(ps, key=lambda p: p.index), payload, ctx, DOCS)
        evidence.extend(found)
        usage = usage + u
    summary = f"Searched {len(docs)} released document(s); {len(evidence)} evidence item(s)."
    events.append(audit(DOCS, AuditAction.TASK_COMPLETED, summary, subject_type="task", subject_id=task.id))
    return (
        ResearchOutput(task=_done(task, summary, evidence, [srcs[s] for s in chosen]), evidence=evidence),
        usage,
        events,
    )
