"""Deterministic offline reasoner.

Purpose: run the full investigation without model credentials (CI, demos, reproducible evaluation) and
provide an evaluation *floor* for the LLM reasoner. It is intentionally simple and fully generic:

* framing uses question patterns;
* hypotheses are instantiated from the generic driver taxonomy;
* planning maps hypothesis categories to analyses, queries and document searches;
* extraction selects sentences/passages containing the taxonomy's signal phrases;
* claim drafting weighs linked evidence by authority tier.

It contains no scenario knowledge. Everything specific comes from data.
"""

from __future__ import annotations

import re

from sip.agents.contracts import (
    Calls,
    ChallengeDraft,
    ClaimDraft,
    EvidenceDraft,
    EvidenceView,
    FindingView,
    FrameDraft,
    HypothesisDraft,
    LinkDraft,
    OptionDraft,
    PlanningContext,
    SourceTypeDraft,
    SourceView,
    TaskDraft,
)
from sip.agents.taxonomy import Taxonomy, default_taxonomy
from sip.domain.claims import Classification
from sip.domain.common import Level
from sip.domain.evidence import AuthorityTier, EvidenceKind, Stance
from sip.domain.hypotheses import Hypothesis, HypothesisStatus
from sip.domain.investigation import InvestigationFrame
from sip.domain.research import AnalysisRequest, ResearchMethod
from sip.domain.sources import SourceType
from sip.research.text import Passage, split_sentences
from sip.tools.analytics import OPERATION_ROLES

_WHY = re.compile(
    r"\bwhy\s+(?:have|has|are|is|did|do|does)\s+(?P<subject>.+?)\s+(?:been\s+)?"
    r"(?P<dir>declin\w*|f[ae]ll\w*|dropp\w*|decreas\w*|reduc\w*|increas\w*|ris\w*|grow\w*|grown|"
    r"chang\w*|deteriorat\w*|stall\w*)\b",
    re.I,
)
_PRESCRIPTIVE = re.compile(r"\b(what should|how should|should we|recommend|what can)\b", re.I)
_EVALUATIVE = re.compile(r"^\s*should\b", re.I)
_CORRELATION = re.compile(
    r"\b(coincided|coinciding|at the same time as|in the wake of|following the|"
    r"after the|since the)\b",
    re.I,
)
_OPINION = re.compile(r"\b(in my view|i believe|we believe|i think|we think|in our opinion)\b", re.I)
_DIGIT = re.compile(r"\d")
_TIER_RANK = {t.value: t.rank for t in AuthorityTier}
_FACT_TYPES = {
    SourceType.GOVERNMENT_POLICY,
    SourceType.REGULATOR,
    SourceType.STANDARDS_BODY,
    SourceType.COMPETITOR_OFFICIAL,
    SourceType.ORGANISATION_OFFICIAL,
}


def evidence_kind(source_type: SourceType, text: str) -> EvidenceKind:
    if _CORRELATION.search(text):
        return EvidenceKind.CORRELATION
    if _OPINION.search(text):
        return EvidenceKind.SOURCE_ASSERTION
    if source_type == SourceType.CRM_RECORD:
        return EvidenceKind.ANECDOTE
    if source_type in _FACT_TYPES:
        return EvidenceKind.DOCUMENTED_FACT
    if source_type in {SourceType.OFFICIAL_STATISTICS, SourceType.INDUSTRY_BODY, SourceType.ACADEMIC}:
        return EvidenceKind.MEASUREMENT if _DIGIT.search(text) else EvidenceKind.DOCUMENTED_FACT
    if source_type in {SourceType.INTERNAL_DOCUMENT, SourceType.INTERNAL_DATASET}:
        return EvidenceKind.DOCUMENTED_FACT
    return EvidenceKind.SOURCE_ASSERTION


def _phrase_hits(text: str, phrases: list[str]) -> list[str]:
    low = text.lower()
    return [p for p in phrases if re.search(rf"(?<!\w){re.escape(p.lower())}", low)]


def _simplify_subject(subject: str, organisation: str | None) -> str:
    s = subject.strip()
    if organisation:
        s = re.sub(rf"{re.escape(organisation)}'s\s+", "", s, flags=re.I)
        s = re.sub(rf"\b(at|of|for)\s+{re.escape(organisation)}\b", "", s, flags=re.I)
    s = re.sub(r"^(our|the|its)\s+", "", s, flags=re.I)
    m = re.match(r"(?P<what>[\w-]+)\s+in\s+(?:the\s+|our\s+)?(?P<where>.+)", s)
    if m:
        s = f"{m.group('where')} {m.group('what')}"
    return re.sub(r"\s+", " ", s).strip()


class OfflineReasoner:
    name = "offline-heuristic-v1"

    def __init__(self, taxonomy: Taxonomy | None = None) -> None:
        self.taxonomy = taxonomy or default_taxonomy()

    # ---------------------------------------------------------------------------------------------
    async def frame(self, question: str, organisation: str | None, context: str) -> tuple[FrameDraft, Calls]:
        m = _WHY.search(question)
        types: list = []
        if m:
            types.append("diagnostic")
        if _PRESCRIPTIVE.search(question):
            types.append("prescriptive")
        if _EVALUATIVE.search(question):
            types.append("evaluative")
        if not types:
            types.append("exploratory")
        subject = _simplify_subject(m.group("subject"), organisation) if m else question.strip(" ?")
        direction = m.group("dir").lower() if m else None
        org = organisation or "the organisation"
        vague = len(question.split()) < 6 or not m
        return FrameDraft(
            question_types=types,
            subject=subject,
            direction=direction,
            decision_context=context or f"{org} leadership needs to decide how to respond to the change in {subject}.",
            scope=f"Explain the change in {subject} for {org} using internal performance data, external "
            f"market and policy evidence, and supplied internal documents; identify options for "
            f"leadership. Distinguish what is known, inferred, hypothesised and unknown.",
            out_of_scope=[
                "Making the organisational decision (reserved for accountable humans).",
                "Individual-level performance assessment of staff or customers.",
            ],
            objectives=[
                "Establish whether the change is market-wide or specific to the organisation.",
                "Locate where (which segments) the change is concentrated.",
                "Test each plausible driver against evidence that could support or contradict it.",
                "Identify what cannot be resolved with available evidence and what would resolve it.",
                "Generate strategic options with explicit evidence, risks and uncertainties.",
            ],
            assumptions=[
                f"Internal {subject} figures use consistent definitions across the period.",
                "External market data covers a comparable population and period.",
            ],
            ambiguities=[f"'{direction or 'change'}' is measured on volume; value or margin may differ."],
            constraints=[
                "Research budget and iteration limits apply.",
                "Confidential internal material is only available in sanitised form.",
            ],
            needs_clarification=vague,
            clarification_questions=(
                [
                    "What metric and time period does the question refer to?",
                    "Which organisation or business unit is in scope?",
                ]
                if vague
                else []
            ),
        ), Calls()

    # ---------------------------------------------------------------------------------------------
    async def hypothesise(
        self, frame: InvestigationFrame, datasets: list[dict[str, object]]
    ) -> tuple[list[HypothesisDraft], Calls]:
        org = frame.organisation or "the organisation"
        drafts = [
            HypothesisDraft(
                category=key,
                statement=c.statement.format(subject=frame.subject, org=org, segment=""),
                rationale=c.rationale,
                would_support=c.would_support,
                would_contradict=c.would_contradict,
                suggested_source_types=c.source_types,
                priority=c.priority,
            )
            for key, c in self.taxonomy.categories.items()
        ]
        return drafts, Calls()

    # ---------------------------------------------------------------------------------------------
    async def plan(self, ctx: PlanningContext) -> tuple[list[TaskDraft], Calls]:
        roles = {str(d["role"]) for d in ctx.datasets}
        dataset_by_role = {str(d["role"]): str(d["id"]) for d in ctx.datasets}
        org = ctx.frame.organisation or "the organisation"
        tasks: list[TaskDraft] = []
        for h in ctx.hypotheses:
            if h.status != HypothesisStatus.PROPOSED:
                continue
            cat = self.taxonomy.categories.get(h.category)
            if cat is None:
                continue
            seg = h.segment or ""
            fill = {"subject": ctx.frame.subject, "org": org, "segment": seg}
            if cat.requires_dataset_role and cat.requires_dataset_role not in roles:
                tasks.append(
                    TaskDraft(
                        question=f"What {cat.requires_dataset_role.replace('_', ' ')} data shows about: {h.statement}",
                        hypothesis_ids=[h.id],
                        method=ResearchMethod.DATASET_ANALYSIS,
                        required_dataset_role=cat.requires_dataset_role,
                        required_evidence=f"A dataset with role '{cat.requires_dataset_role}'.",
                        priority=h.priority,
                        expected_value=Level.HIGH,
                        expected_value_rationale="Directly tests the hypothesis.",
                        completion_criteria="Dataset analysed, or confirmed unavailable.",
                    )
                )
            if h.segment is None:
                for op in cat.analyses:
                    needed = [r.value for r in OPERATION_ROLES[op]]
                    if not all(r in roles for r in needed):
                        continue
                    params: dict[str, object] = {}
                    if op == "decompose_change":
                        own = next(d for d in ctx.datasets if d["role"] == "own_volume")
                        own_dims = [str(x) for x in own.get("dimensions") or []]  # type: ignore[attr-defined]
                        params = {"by": own_dims[0] if own_dims else None}
                    if op == "funnel_conversion":
                        funnel = next(d for d in ctx.datasets if d["role"] == "funnel")
                        dims = [str(x) for x in funnel.get("dimensions") or [] if x]  # type: ignore[attr-defined]
                        params = {"by": dims[-1] if len(dims) > 1 else None}
                    tasks.append(
                        TaskDraft(
                            question=f"Run {op.replace('_', ' ')} to test: {h.statement}",
                            hypothesis_ids=[h.id],
                            method=ResearchMethod.DATASET_ANALYSIS,
                            analysis=AnalysisRequest(
                                operation=op, dataset_id=dataset_by_role[needed[0]], params=params
                            ),
                            required_evidence="; ".join(cat.would_support + cat.would_contradict),
                            preferred_source_types=[SourceType.INTERNAL_DATASET, SourceType.OFFICIAL_STATISTICS],
                            priority=h.priority,
                            expected_value=Level.HIGH,
                            expected_value_rationale="Deterministic test against complete data.",
                            completion_criteria="Operation completed and patterns recorded.",
                        )
                    )
            if cat.web_queries:
                queries = [q.format(**fill).strip() for q in cat.web_queries]
                if seg:
                    queries = [f"{seg} {q}" for q in queries[:1]]
                tasks.append(
                    TaskDraft(
                        question=f"What external evidence supports or contradicts: {h.statement}",
                        hypothesis_ids=[h.id],
                        method=ResearchMethod.WEB_SEARCH,
                        queries=queries,
                        required_evidence="; ".join(cat.would_support + cat.would_contradict),
                        preferred_source_types=cat.source_types,
                        priority=h.priority,
                        expected_value=h.priority,
                        expected_value_rationale="External evidence needed to test the hypothesis.",
                        completion_criteria="Relevant sources inspected and evidence extracted.",
                    )
                )
            if cat.document_queries and ctx.has_documents:
                tasks.append(
                    TaskDraft(
                        question=f"What do internal documents say about: {h.statement}",
                        hypothesis_ids=[h.id],
                        method=ResearchMethod.INTERNAL_DOCUMENTS,
                        queries=[q.format(**fill) for q in cat.document_queries] + [h.statement],
                        required_evidence="; ".join(cat.would_support),
                        preferred_source_types=[SourceType.INTERNAL_DOCUMENT, SourceType.CRM_RECORD],
                        priority=h.priority,
                        expected_value=Level.MEDIUM,
                        expected_value_rationale="Internal documents may record causes directly.",
                        completion_criteria="Released internal documents searched.",
                    )
                )
        for q in ctx.open_research_questions:
            tasks.append(
                TaskDraft(
                    question=q,
                    hypothesis_ids=[],
                    method=ResearchMethod.WEB_SEARCH,
                    queries=[q],
                    required_evidence="Evidence that resolves the challenge.",
                    preferred_source_types=[
                        SourceType.OFFICIAL_STATISTICS,
                        SourceType.GOVERNMENT_POLICY,
                        SourceType.COMPETITOR_OFFICIAL,
                    ],
                    priority=Level.HIGH,
                    expected_value=Level.MEDIUM,
                    expected_value_rationale="Raised by the challenger or a human reviewer.",
                    completion_criteria="Sources inspected.",
                )
            )
            if ctx.has_documents:
                tasks.append(
                    TaskDraft(
                        question=q,
                        hypothesis_ids=[],
                        method=ResearchMethod.INTERNAL_DOCUMENTS,
                        queries=[q],
                        required_evidence="Evidence that resolves the challenge.",
                        priority=Level.MEDIUM,
                        expected_value=Level.MEDIUM,
                        expected_value_rationale="Raised by the challenger or a human reviewer.",
                        completion_criteria="Released internal documents searched.",
                    )
                )
        return tasks, Calls()

    # ---------------------------------------------------------------------------------------------
    async def extract(
        self, question: str, hypotheses: list[Hypothesis], source: SourceView, passages: list[Passage]
    ) -> tuple[list[EvidenceDraft], Calls]:
        drafts: list[tuple[int, EvidenceDraft]] = []
        for passage in passages:
            units = [passage.text] if source.source_type == SourceType.CRM_RECORD else split_sentences(passage.text)
            for unit in units:
                links: list[LinkDraft] = []
                score = 0
                for h in hypotheses:
                    cat = self.taxonomy.categories.get(h.category)
                    if cat is None or source.source_type not in cat.source_types:
                        continue
                    sup = _phrase_hits(unit, cat.signals.support)
                    con = _phrase_hits(unit, cat.signals.contradict)
                    if con:
                        links.append(
                            LinkDraft(
                                hypothesis_id=h.id, stance=Stance.CONTRADICTS, rationale=f"mentions: {', '.join(con)}"
                            )
                        )
                    elif sup:
                        links.append(
                            LinkDraft(
                                hypothesis_id=h.id, stance=Stance.SUPPORTS, rationale=f"mentions: {', '.join(sup)}"
                            )
                        )
                    score += len(sup) + len(con)
                if not links:
                    continue
                kind = evidence_kind(source.source_type, unit)
                attribution = source.publisher or source.title
                drafts.append(
                    (
                        score,
                        EvidenceDraft(
                            passage_index=passage.index,
                            quote=unit,
                            statement=f"{attribution}: {unit}",
                            kind=kind,
                            relevance=Level.HIGH if score >= 2 else Level.MEDIUM,
                            links=links,
                        ),
                    )
                )
        drafts.sort(key=lambda x: -x[0])
        return [d for _, d in drafts[:10]], Calls()

    # ---------------------------------------------------------------------------------------------
    async def draft_claims(
        self,
        frame: InvestigationFrame,
        hypothesis: Hypothesis,
        evidence: list[EvidenceView],
        blocked_reasons: list[str],
    ) -> tuple[list[ClaimDraft], Calls]:
        usable = [e for e in evidence if "injection_suspected" not in e.flags]
        support = [e for e in usable if e.stance == Stance.SUPPORTS]
        against = [e for e in usable if e.stance == Stance.CONTRADICTS]
        claims: list[ClaimDraft] = []

        for e in usable:  # factual, non-causal claims from computed measurements
            if e.kind == EvidenceKind.MEASUREMENT and e.source_type == SourceType.INTERNAL_DATASET:
                claims.append(
                    ClaimDraft(
                        statement=e.statement,
                        proposed_classification=Classification.KNOWN,
                        causal=False,
                        supporting_evidence_ids=[e.id],
                        contradicting_evidence_ids=[],
                        inferential_step=None,
                        reasoning_summary="Computed directly from the dataset by a deterministic operation.",
                        limitations=["Accuracy depends on the source data."],
                        missing_evidence=[],
                        next_question=None,
                        hypothesis_verdict="none",
                    )
                )

        if blocked_reasons:
            anecdotes = [e for e in support if e.kind == EvidenceKind.ANECDOTE]
            claims.append(
                ClaimDraft(
                    statement=f"It cannot be determined from available evidence whether "
                    f"{hypothesis.statement[0].lower()}{hypothesis.statement[1:].rstrip('.')}.",
                    proposed_classification=Classification.UNKNOWN,
                    causal=False,
                    supporting_evidence_ids=[],
                    contradicting_evidence_ids=[],
                    inferential_step=None,
                    reasoning_summary=(
                        f"{len(anecdotes)} anecdotal item(s) are consistent with the hypothesis, "
                        "but they are not representative and cannot establish the overall pattern."
                        if anecdotes
                        else "No evidence that could test this was available."
                    ),
                    limitations=["Anecdotes are a small, non-random sample."] if anecdotes else [],
                    missing_evidence=blocked_reasons,
                    next_question=f"Obtain: {blocked_reasons[0]}",
                    hypothesis_verdict="unresolved",
                )
            )
            return claims, Calls()

        def weight(items: list[EvidenceView]) -> int:
            """Sum over independent sources of the best item per source. Many sentences from one memo
            count once; stale items count one tier lower; computed measurements count one tier higher
            because they test the hypothesis directly."""
            best: dict[str, int] = {}
            for e in items:
                w = _TIER_RANK.get(e.tier, 1)
                if e.freshness == "stale":
                    w -= 1
                if e.kind == EvidenceKind.MEASUREMENT and e.source_type == SourceType.INTERNAL_DATASET:
                    w += 1
                key = e.publisher or e.source_title
                best[key] = max(best.get(key, 0), w)
            return sum(best.values())

        s, a = weight(support), weight(against)
        stmt = hypothesis.statement.rstrip(".")
        if support and s > a:
            claims.append(
                ClaimDraft(
                    statement=stmt + ".",
                    proposed_classification=Classification.INFERRED,
                    causal=True,
                    supporting_evidence_ids=[e.id for e in support],
                    contradicting_evidence_ids=[e.id for e in against],
                    inferential_step="Causal contribution is inferred from evidence that is consistent with "
                    "the mechanism; it is not directly measured.",
                    reasoning_summary=f"{len(support)} supporting item(s) outweigh {len(against)} contradicting "
                    "item(s) on authority tier.",
                    limitations=["Relative contribution of this driver versus others is not quantified."]
                    + (["Some evidence points the other way."] if against else []),
                    missing_evidence=hypothesis.would_contradict[:1],
                    next_question=None,
                    hypothesis_verdict="supports",
                )
            )
        elif against and a > s:
            claims.append(
                ClaimDraft(
                    statement=f"Not supported by the evidence: {stmt}.",
                    proposed_classification=Classification.INFERRED,
                    causal=False,
                    supporting_evidence_ids=[e.id for e in against],
                    contradicting_evidence_ids=[e.id for e in support],
                    inferential_step="Absence of the expected pattern is taken as evidence against the driver.",
                    reasoning_summary=f"{len(against)} contradicting item(s) outweigh {len(support)} supporting "
                    "item(s) on authority tier.",
                    limitations=["A driver can be real but small; this rejects it as a material explanation."],
                    missing_evidence=[],
                    next_question=None,
                    hypothesis_verdict="contradicts",
                )
            )
        elif support or against:
            claims.append(
                ClaimDraft(
                    statement=stmt + ".",
                    proposed_classification=Classification.HYPOTHESIS,
                    causal=True,
                    supporting_evidence_ids=[e.id for e in support],
                    contradicting_evidence_ids=[e.id for e in against],
                    inferential_step="Evidence is balanced.",
                    reasoning_summary="Supporting and contradicting evidence are of similar weight.",
                    limitations=["Evidence is mixed."],
                    missing_evidence=hypothesis.would_support[:1],
                    next_question=f"What evidence would discriminate for or against: {stmt}?",
                    hypothesis_verdict="unresolved",
                )
            )
        return claims, Calls()

    # ---------------------------------------------------------------------------------------------
    async def challenge(
        self, frame: InvestigationFrame, claims: list[dict[str, object]], evidence: list[EvidenceView]
    ) -> tuple[list[ChallengeDraft], Calls]:
        # The deterministic sceptic (sip.evidence.sceptic) runs in all modes; nothing extra offline.
        return [], Calls()

    # ---------------------------------------------------------------------------------------------
    async def classify_source(
        self, title: str, domain: str | None, excerpt: str
    ) -> tuple[SourceTypeDraft | None, Calls]:
        return None, Calls()  # offline: rely on domain rules only

    async def synthesise(
        self, frame: InvestigationFrame, findings: list[FindingView], unknowns: list[str], caveats: list[str]
    ) -> tuple[list[OptionDraft], Calls]:
        by_cat: dict[str, list[FindingView]] = {}
        for f in findings:
            for c in f.hypothesis_categories:
                if c in self.taxonomy.responses:
                    by_cat.setdefault(c, []).append(f)
        options: list[OptionDraft] = []
        for cat, fs in by_cat.items():
            tmpl = self.taxonomy.responses[cat]
            segments = sorted({s for f in fs for s in f.segments}) or [frame.subject]
            seg_txt = ", ".join(segments)
            weakest = min(fs, key=lambda f: ["very_low", "low", "moderate", "high"].index(f.confidence_band))
            options.append(
                OptionDraft(
                    title=tmpl.title + (f" ({seg_txt})" if segments != [frame.subject] else ""),
                    description=tmpl.description.format(segment=seg_txt),
                    rationale="Responds to: " + " | ".join(f.statement for f in fs[:3]),
                    finding_ids=[f.id for f in fs],
                    expected_benefits=[
                        f"Addresses the {self.taxonomy.categories[cat].label.lower()} driver identified in {seg_txt}."
                    ],
                    risks=[
                        "Causal contribution of this driver is inferred, not measured; "
                        "the response may address a smaller share of the decline than expected.",
                        f"Weakest supporting finding is {weakest.confidence_band} confidence.",
                    ],
                    uncertainties=unknowns[:3] + caveats[:2],
                    dependencies=[
                        "Leadership agreement on investment appetite.",
                        "Customer validation before full commitment.",
                    ],
                    reversibility=tmpl.reversibility,
                    reversibility_note={
                        "high": "Can be stopped or reversed within a planning cycle.",
                        "medium": "Partially reversible; some sunk design cost.",
                        "low": "Hard to reverse once launched (new offer, partnerships).",
                    }[tmpl.reversibility.value],
                    consequence=tmpl.consequence,
                    additional_evidence_needed=unknowns[:2],
                )
            )
        options.append(
            OptionDraft(
                title="Commission targeted research on the unresolved questions",
                description="Before committing to high-consequence options, obtain the evidence the "
                "investigation could not: " + ("; ".join(unknowns[:3]) or "none identified") + ".",
                rationale="Several conclusions remain UNKNOWN or rest on inference.",
                finding_ids=[],
                expected_benefits=["Reduces the risk of acting on an incomplete causal picture."],
                risks=["Delay has an opportunity cost if competitors continue to take share."],
                uncertainties=unknowns[:3],
                dependencies=["Access to customers or third-party data."],
                reversibility=Level.HIGH,
                reversibility_note="Research can be stopped at any time.",
                consequence=Level.LOW,
                additional_evidence_needed=unknowns[:3],
            )
        )
        options.append(
            OptionDraft(
                title="Hold the current portfolio (baseline)",
                description="Make no portfolio change; monitor the indicators identified by the investigation.",
                rationale="Baseline against which the other options should be judged.",
                finding_ids=[],  # a do-nothing baseline does not rest on findings
                expected_benefits=["No investment or disruption."],
                risks=["Findings indicate drivers that are unlikely to reverse without action."],
                uncertainties=unknowns[:2],
                dependencies=[],
                reversibility=Level.HIGH,
                reversibility_note="Fully reversible.",
                consequence=Level.MEDIUM,
                additional_evidence_needed=[],
            )
        )
        return options, Calls()
