"""Evidence Manager, Analyst and Sceptic/Challenger nodes, plus the evidence-sufficiency router."""

from __future__ import annotations

import asyncio
from typing import Any

from langgraph.runtime import Runtime

from sip.agents.contracts import Calls
from sip.domain import (
    Actor,
    AuditAction,
    Challenge,
    ChallengeStatus,
    Claim,
    Classification,
    Evidence,
    Hypothesis,
    HypothesisStatus,
    ReviewState,
    RoutingDecision,
    Severity,
    StopReason,
    TaskStatus,
    utcnow,
)
from sip.evidence.confidence import assess_claim
from sip.evidence.ledger import (
    absolutist_contradictions,
    dedupe_sources,
    detect_contradictions,
    evidence_key,
    evidence_view,
    route_links,
    split_by_segment,
    stable_id,
)
from sip.evidence.sceptic import merge_challenges, run_sceptic
from sip.graph.context import InvestigationContext
from sip.graph.helpers import audit, policy_event, usage_from
from sip.graph.state import RESET, InvestigationState
from sip.research.text import normalise

MANAGER = Actor.agent("evidence_manager")
ANALYST = Actor.agent("analyst")
SCEPTIC = Actor.agent("sceptic")


# ---- evidence manager -----------------------------------------------------------------------------
async def evidence_manager(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    staged = state.get("staging") or []
    existing_sources = state.get("sources") or {}
    existing_evidence = state.get("evidence") or {}
    hyps = state.get("hypotheses") or {}
    new_sources = {s.id: s for out in staged for s in out.sources}
    remap = dedupe_sources(existing_sources, new_sources)
    sources = {sid: s for sid, s in new_sources.items() if sid not in remap and sid not in existing_sources}
    documents = {sid: txt for out in staged for sid, txt in out.documents.items() if sid in sources}
    seen = {evidence_key(e) for e in existing_evidence.values()}
    evidence: dict[str, Evidence] = {}
    tasks = {}
    dup_evidence = 0
    for out in staged:
        kept = []
        for e in out.evidence:
            if e.source_id in remap:
                e = e.model_copy(update={"source_id": remap[e.source_id]})
            key = evidence_key(e)
            if key in seen and e.id not in existing_evidence:
                dup_evidence += 1
                continue
            seen.add(key)
            e = route_links(e, hyps)
            if e.id in existing_evidence:  # same item found again: merge hypothesis links
                old = existing_evidence[e.id]
                links = {lk.hypothesis_id: lk for lk in [*old.links, *e.links]}
                e = old.model_copy(update={"links": list(links.values())})
            evidence[e.id] = e
            kept.append(e.id)
        tasks[out.task.id] = out.task.model_copy(
            update={"evidence_ids": kept, "source_ids": [remap.get(s, s) for s in out.task.source_ids]}
        )
    events = [
        audit(
            MANAGER,
            AuditAction.EVIDENCE_ADDED,
            f"Round {state.get('iteration', 0)}: {len(evidence)} evidence item(s), {len(sources)} new "
            f"source(s); {len(remap)} duplicate source(s) and {dup_evidence} duplicate evidence item(s) "
            "merged.",
            new_evidence=len(evidence),
            duplicate_sources=len(remap),
        )
    ]
    for s in sources.values():
        events.append(
            audit(
                MANAGER,
                AuditAction.SOURCE_ADDED,
                s.title,
                subject_type="source",
                subject_id=s.id,
                source_type=s.source_type.value,
                synthetic=s.synthetic,
            )
        )
    return {
        "sources": sources,
        "documents": documents,
        "evidence": evidence,
        "tasks": tasks,
        "staging": RESET,
        "audit": events,
    }


# ---- analyst --------------------------------------------------------------------------------------
def _status_for(verdict: str, cls: Classification, has_against: bool, blocked: bool) -> HypothesisStatus:
    if verdict == "supports":
        if cls.strength >= Classification.INFERRED.strength:
            return HypothesisStatus.SUPPORTED
        return HypothesisStatus.WEAKENED if has_against else HypothesisStatus.INVESTIGATING
    if verdict == "contradicts":
        return (
            HypothesisStatus.CONTRADICTED
            if cls.strength >= Classification.INFERRED.strength
            else HypothesisStatus.WEAKENED
        )
    if blocked or cls == Classification.UNKNOWN:
        return HypothesisStatus.UNRESOLVED
    return HypothesisStatus.INVESTIGATING


async def analyse(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    fr = state["frame"]
    assert fr is not None
    hyps: dict[str, Hypothesis] = dict(state.get("hypotheses") or {})
    evidence: dict[str, Evidence] = dict(state.get("evidence") or {})
    sources = state.get("sources") or {}
    tasks = state.get("tasks") or {}
    existing_claims = state.get("claims") or {}
    iteration = state.get("iteration", 0)
    events = [policy_event(ANALYST, ctx.governance.evaluate("classify_claim"))]

    # 1. Refine the hypothesis tree where evidence diverges by segment.
    names = ctx.catalog.display_names()
    material = {
        seg for e in evidence.values() if "major_contributor_to_decline" in (e.locator or "") for seg in e.segments
    }
    parents, children = split_by_segment(
        hyps, evidence, ctx.taxonomy, material, names, fr.organisation or "the organisation", ctx.catalog.own_entities()
    )
    hyps |= parents
    for c in children:
        hyps.setdefault(c.id, c)
        events.append(
            audit(
                ANALYST,
                AuditAction.HYPOTHESIS_CREATED,
                f"Emergent: {c.statement}",
                subject_type="hypothesis",
                subject_id=c.id,
                parent=c.parent_id,
            )
        )
    changed_evidence = {}
    if children:
        for e in evidence.values():
            routed = route_links(e, hyps)
            if routed is not e:
                changed_evidence[routed.id] = routed
        evidence |= changed_evidence

    # 2. Draft claims per leaf hypothesis (in parallel), then apply the rubric.
    def blocked_for(h: Hypothesis) -> list[str]:
        ids = {h.id, h.parent_id}
        return [
            t.status_reason
            for t in tasks.values()
            if t.status == TaskStatus.BLOCKED_UNAVAILABLE and ids & set(t.hypothesis_ids) and t.required_dataset_role
        ]

    leaves = [h for h in hyps.values() if h.status != HypothesisStatus.SPLIT]
    jobs = []
    for h in leaves:
        views = [evidence_view(e, sources, h.id) for e in evidence.values() if e.stance_for(h.id)]
        blocked = blocked_for(h)
        if views or blocked:
            jobs.append((h, ctx.reasoner.draft_claims(fr, h, views, blocked), bool(blocked)))
    results = await asyncio.gather(*(j[1] for j in jobs))

    claims: dict[str, Claim] = {}
    produced: set[str] = set()
    calls_all = Calls()
    hyp_updates: dict[str, Hypothesis] = dict(parents)
    for (h, _, is_blocked), (drafts, calls) in zip(jobs, results, strict=True):
        calls_all.extend(calls)
        verdict_cls: tuple[str, Classification, bool] | None = None
        for d in drafts:
            support = [i for i in d.supporting_evidence_ids if i in evidence]
            against = [i for i in d.contradicting_evidence_ids if i in evidence]
            cited = len(d.supporting_evidence_ids) + len(d.contradicting_evidence_ids)
            dropped = cited - len(support) - len(against)
            cid = stable_id("clm", normalise(d.statement))
            prior = existing_claims.get(cid) or claims.get(cid)
            related = sorted({h.id, *(prior.related_hypothesis_ids if prior else [])})
            claim = Claim(
                id=cid,
                statement=d.statement,
                classification=d.proposed_classification,
                proposed_classification=d.proposed_classification,
                causal=d.causal,
                supporting_evidence_ids=support,
                contradicting_evidence_ids=against,
                reasoning_summary=d.reasoning_summary,
                inferential_step=d.inferential_step,
                limitations=d.limitations
                + ([f"{dropped} cited evidence id(s) did not exist and were removed."] if dropped else []),
                missing_evidence=d.missing_evidence,
                related_hypothesis_ids=related,
                next_question=d.next_question,
                created_by=ANALYST,
                iteration=iteration,
                created_at=prior.created_at if prior else utcnow(),
                review_state=prior.review_state if prior else ReviewState.UNREVIEWED,
                human_override=prior.human_override if prior else None,
            )
            result = assess_claim(claim, evidence, sources, ctx.quality)
            tiers = sorted({q.tier.value for i in support if (q := evidence[i].quality) is not None})
            claim = claim.model_copy(
                update={
                    "classification": claim.human_override.new if claim.human_override else result.classification,
                    "confidence": result.assessment,
                    "source_quality_summary": f"{len(support)} supporting ({', '.join(tiers) or 'none'}), "
                    f"{len(against)} contradicting.",
                }
            )
            if result.classification != d.proposed_classification:
                events.append(
                    audit(
                        ANALYST,
                        AuditAction.CLAIM_DOWNGRADED,
                        f"{d.proposed_classification.value} -> {result.classification.value}: "
                        + "; ".join(result.assessment.ceiling_reasons[:2]),
                        subject_type="claim",
                        subject_id=cid,
                    )
                )
            if cid not in existing_claims or existing_claims[cid].classification != claim.classification:
                events.append(
                    audit(
                        ANALYST,
                        AuditAction.CLAIM_CLASSIFIED,
                        f"{claim.classification.value.upper()} ({result.assessment.band.value}): "
                        f"{claim.statement[:140]}",
                        subject_type="claim",
                        subject_id=cid,
                    )
                )
            claims[cid] = claim
            produced.add(cid)
            if d.hypothesis_verdict != "none":
                verdict_cls = (d.hypothesis_verdict, claim.classification, bool(against))
        if verdict_cls:
            status = _status_for(verdict_cls[0], verdict_cls[1], verdict_cls[2], is_blocked)
            if status != h.status:
                hyp_updates[h.id] = h.model_copy(
                    update={"status": status, "updated_at": utcnow(), "status_reason": f"Analysis round {iteration}."}
                )
                events.append(
                    audit(
                        ANALYST,
                        AuditAction.HYPOTHESIS_UPDATED,
                        f"{status.value}: {h.statement[:140]}",
                        subject_type="hypothesis",
                        subject_id=h.id,
                    )
                )

    # 3. Summary claims for split parents: where the driver applies and where it does not.
    current = hyps | hyp_updates
    for p in (h for h in current.values() if h.status == HypothesisStatus.SPLIT):
        kids = [k for k in current.values() if k.parent_id == p.id]
        sup = [k for k in kids if k.status == HypothesisStatus.SUPPORTED]
        rej = [k for k in kids if k.status == HypothesisStatus.CONTRADICTED]
        if not sup:
            continue
        label = ctx.taxonomy.categories[p.category].label
        stmt = (
            f"{label} explains part of the change: supported for "
            f"{', '.join(names.get(k.segment or '', k.segment or '') for k in sup)}"
            + (
                f"; not supported for {', '.join(names.get(k.segment or '', k.segment or '') for k in rej)}."
                if rej
                else "."
            )
        )
        support_ids = sorted(
            {
                cid_e
                for k in sup
                for c in claims.values()
                if k.id in c.related_hypothesis_ids and c.causal
                for cid_e in c.supporting_evidence_ids
            }
        )
        cid = stable_id("clm", "split", p.id)
        claim = Claim(
            id=cid,
            statement=stmt,
            classification=Classification.INFERRED,
            proposed_classification=Classification.INFERRED,
            causal=True,
            supporting_evidence_ids=support_ids,
            related_hypothesis_ids=[p.id, *(k.id for k in sup)],
            inferential_step="Aggregates segment-level conclusions.",
            reasoning_summary="Segment-level hypotheses were tested separately.",
            limitations=["Share of the total change attributable to this driver is approximate."],
            created_by=ANALYST,
            iteration=iteration,
        )
        result = assess_claim(claim, evidence, sources, ctx.quality)
        claims[cid] = claim.model_copy(
            update={"classification": result.classification, "confidence": result.assessment}
        )
        produced.add(cid)

    # 4. Claims no longer produced become inactive (kept for history).
    analysed = {h.id for h, _, _ in jobs} | {p.id for p in current.values() if p.status == HypothesisStatus.SPLIT}
    for cid, old in existing_claims.items():
        if cid not in produced and old.active and set(old.related_hypothesis_ids) & analysed:
            claims[cid] = old.model_copy(update={"active": False, "updated_at": utcnow()})

    contradictions = {
        c.id: c for c in [*detect_contradictions(current, evidence), *absolutist_contradictions(current, evidence)]
    }
    return {
        "hypotheses": {**hyp_updates, **{c.id: current[c.id] for c in children}},
        "evidence": changed_evidence,
        "claims": claims,
        "contradictions": contradictions,
        "audit": events,
        "usage": usage_from(calls_all),
    }


# ---- sceptic / challenger -------------------------------------------------------------------------
async def challenge(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    fr = state["frame"]
    assert fr is not None
    claims = state.get("claims") or {}
    evidence = state.get("evidence") or {}
    sources = state.get("sources") or {}
    hyps = state.get("hypotheses") or {}
    tasks = state.get("tasks") or {}
    iteration = state.get("iteration", 0)
    fresh = run_sceptic(
        claims=claims,
        evidence=evidence,
        sources=sources,
        hypotheses=hyps,
        tasks=tasks,
        catalog=ctx.catalog,
        iteration=iteration,
    )
    active = [c for c in claims.values() if c.active]
    drafts, calls = await ctx.reasoner.challenge(
        fr,
        [
            {
                "id": c.id,
                "statement": c.statement,
                "classification": c.classification.value,
                "causal": c.causal,
                "supporting": c.supporting_evidence_ids,
                "contradicting": c.contradicting_evidence_ids,
                "limitations": c.limitations,
            }
            for c in active
        ],
        [evidence_view(e, sources) for e in evidence.values() if e.usable][:120],
    )
    valid_targets = {c.id for c in active} | set(hyps)
    for d in drafts:
        if d.target_id in valid_targets:
            fresh.append(
                Challenge(
                    id=stable_id("chl", "llm", d.kind.value, d.target_id),
                    target_type="claim" if d.target_id in claims else "hypothesis",
                    target_id=d.target_id,
                    kind=d.kind,
                    severity=d.severity,
                    argument=d.argument,
                    research_question=d.research_question,
                    raised_by=SCEPTIC,
                    iteration=iteration,
                )
            )
    existing = state.get("challenges") or {}
    merged = merge_challenges(existing, fresh)
    events = []
    for c in merged.values():
        if c.id not in existing:
            events.append(
                audit(
                    SCEPTIC,
                    AuditAction.CHALLENGE_RAISED,
                    f"[{c.severity.value}] {c.kind.value}: {c.argument[:160]}",
                    subject_type=c.target_type,
                    subject_id=c.target_id,
                )
            )
        elif existing[c.id].status != c.status:
            events.append(
                audit(
                    SCEPTIC,
                    AuditAction.CHALLENGE_RESOLVED,
                    f"{c.kind.value} -> {c.status.value}",
                    subject_type=c.target_type,
                    subject_id=c.target_id,
                )
            )
    challenged = {c.target_id for c in merged.values() if c.status == ChallengeStatus.OPEN}
    claim_updates = {
        cid: c.model_copy(update={"review_state": ReviewState.CHALLENGED})
        for cid, c in claims.items()
        if cid in challenged and c.review_state == ReviewState.UNREVIEWED
    }

    routing = decide_routing(state, {**existing, **merged})
    events.append(
        audit(
            SCEPTIC,
            AuditAction.ROUTING_DECISION,
            routing.rationale,
            continue_research=routing.continue_research,
            stop_reason=routing.stop_reason.value if routing.stop_reason else None,
        )
    )
    return {
        "challenges": merged,
        "claims": claim_updates,
        "routing": [routing],
        "audit": events,
        "usage": usage_from(calls),
    }


def decide_routing(state: InvestigationState, challenges: dict[str, Challenge]) -> RoutingDecision:
    """Evidence-sufficiency and stopping logic. Deterministic and bounded."""
    budget = state["budget"]
    iteration = state.get("iteration", 0)
    usage = state.get("usage")
    round_ids = set(state.get("round_task_ids") or [])
    new_evidence = sum(1 for e in (state.get("evidence") or {}).values() if e.task_id in round_ids)
    open_challenges = [c for c in challenges.values() if c.status == ChallengeStatus.OPEN]
    blocking = sum(1 for c in open_challenges if c.severity == Severity.BLOCKING)
    actionable = [
        c
        for c in open_challenges
        if c.severity in {Severity.BLOCKING, Severity.MAJOR}
        and (c.research_question or c.suggested_analysis)
        and not c.research_attempted
    ]
    proposed = [h for h in (state.get("hypotheses") or {}).values() if h.status == HypothesisStatus.PROPOSED]
    exhausted = usage.exhausted(budget) if usage else []

    def decision(cont: bool, reason: StopReason | None, why: str) -> RoutingDecision:
        return RoutingDecision(
            iteration=iteration,
            continue_research=cont,
            stop_reason=reason,
            rationale=why,
            open_blocking_challenges=blocking,
            new_evidence_last_round=new_evidence,
        )

    if exhausted:
        return decision(False, StopReason.BUDGET, "Stopping: " + "; ".join(exhausted) + ".")
    if iteration >= budget.max_iterations:
        return decision(
            False,
            StopReason.MAX_ITERATIONS,
            f"Stopping: reached the maximum of {budget.max_iterations} research rounds.",
        )
    if actionable or proposed or state.get("research_requests"):
        parts = []
        if actionable:
            parts.append(f"{len(actionable)} open challenge(s) ask for further research")
        if proposed:
            parts.append(f"{len(proposed)} hypothesis(es) not yet investigated")
        return decision(True, None, "Continuing: " + "; ".join(parts) + ".")
    if iteration > 1 and new_evidence == 0:
        return decision(False, StopReason.DIMINISHING_RETURNS, "Stopping: the last round produced no new evidence.")
    return decision(
        False,
        StopReason.SUFFICIENT,
        "Stopping: no open challenge requests further research and all hypotheses have been tested.",
    )


def route_after_challenge(state: InvestigationState) -> str:
    routing = state.get("routing") or []
    return "plan" if routing and routing[-1].continue_research else "findings_gate"
