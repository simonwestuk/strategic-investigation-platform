"""Investigation Lead (framing), privacy release (intake) and Hypothesis Generator nodes."""

from __future__ import annotations

from typing import Any

from langgraph.runtime import Runtime

from sip.domain import (
    Actor,
    AuditAction,
    HumanReview,
    Hypothesis,
    InvestigationFrame,
    QuestionType,
    ReviewAction,
    ReviewKind,
    Role,
)
from sip.domain.sources import RetrievalMethod, Source, SourceOrigin
from sip.evidence.ledger import stable_id
from sip.graph.context import InvestigationContext
from sip.graph.helpers import audit, policy_event, usage_from
from sip.graph.state import InvestigationState
from sip.privacy.models import IntakeDocument, IntakeKind, IntakeStatus

LEAD = Actor.agent("investigation_lead")
GATEWAY = Actor.agent("privacy_release")
HYPOTHESISER = Actor.agent("hypothesis_generator")


async def frame(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    draft, calls = await ctx.reasoner.frame(state["question"], state.get("organisation"),
                                            state.get("context", ""))
    fr = InvestigationFrame(
        question=state["question"], question_types=[QuestionType(t) for t in draft.question_types],
        subject=draft.subject, organisation=state.get("organisation"), direction=draft.direction,
        decision_context=draft.decision_context, scope=draft.scope, out_of_scope=draft.out_of_scope,
        objectives=draft.objectives, assumptions=draft.assumptions, ambiguities=draft.ambiguities,
        constraints=draft.constraints, needs_clarification=draft.needs_clarification,
        clarification_questions=draft.clarification_questions, as_of=state["as_of"])
    decision = ctx.governance.evaluate("frame_question", needs_clarification=fr.needs_clarification)
    events = [policy_event(LEAD, decision),
              audit(LEAD, AuditAction.QUESTION_FRAMED, f"Framed question; subject '{fr.subject}'.")]
    update: dict[str, Any] = {"frame": fr, "usage": usage_from(calls), "audit": events,
                              "pending_review_id": None}
    if decision.requires_human_approval:
        review = HumanReview(
            kind=ReviewKind.CLARIFICATION, title="Clarify the strategic question", reason=decision.reason,
            required_role=decision.required_role or Role.INVESTIGATOR, policy_rule_ids=[decision.rule_id],
            allowed_actions=[ReviewAction.APPROVE, ReviewAction.MODIFY, ReviewAction.REJECT],
            context={"questions": fr.clarification_questions, "subject": fr.subject})
        update |= {"reviews": {review.id: review}, "pending_review_id": review.id,
                   "audit": [*events, audit(LEAD, AuditAction.REVIEW_REQUESTED, review.title,
                                            subject_type="review", subject_id=review.id)]}
    return update


def route_after_frame(state: InvestigationState) -> str:
    return "await_review" if state.get("pending_review_id") else "intake"


# --------------------------------------------------------------------------------------------------
def release(doc: IntakeDocument, ctx: InvestigationContext, state: InvestigationState
            ) -> dict[str, Any]:
    """Create the agent-side Source for a released intake item. Only sanitised text crosses."""
    if doc.kind == IntakeKind.DATASET and doc.dataset_id:
        m = ctx.catalog.get(doc.dataset_id).manifest
        src = Source(id=stable_id("src", "dataset", doc.dataset_id), origin=SourceOrigin.INTERNAL
                     if m.classification.confidentiality.value != "public" else SourceOrigin.EXTERNAL_WEB,
                     source_type=m.source_type, title=m.title, publisher=m.publisher, canonical_url=m.url,
                     published_on=m.published_on, content_hash=doc.sha256, classification=m.classification,
                     retrieval_method=RetrievalMethod.DATASET_QUERY, retrieval_provider="dataset_catalog",
                     synthetic=state.get("scenario_id") is not None, privacy_document_id=doc.id)
        return {"sources": {src.id: src}, "released_dataset_ids": {doc.dataset_id: src.id}}
    src = Source(id=stable_id("src", "doc", doc.id), origin=SourceOrigin.INTERNAL,
                 source_type=doc.source_type, title=doc.title,
                 publisher=state.get("organisation") or "internal", content_hash=doc.sha256,
                 published_on=doc.published_on, classification=doc.scan.classification,
                 retrieval_method=RetrievalMethod.UPLOAD, retrieval_provider="privacy_gateway",
                 synthetic=state.get("scenario_id") is not None, privacy_document_id=doc.id)
    return {"sources": {src.id: src}, "documents": {src.id: doc.sanitised_text}}


def _merge(into: dict[str, Any], add: dict[str, Any]) -> None:
    for k, v in add.items():
        into.setdefault(k, {}).update(v)


def scan_card(doc: IntakeDocument) -> dict[str, Any]:
    """What a privacy reviewer sees: classification, counts and a sanitised preview. Never raw values."""
    return {"id": doc.id, "title": doc.title, "kind": doc.kind.value, "filename": doc.filename,
            "classification": doc.scan.classification.model_dump(mode="json"),
            "entity_counts": [c.model_dump(mode="json") for c in doc.scan.entity_counts],
            "low_confidence_detections": doc.scan.low_confidence_detections,
            "special_category_types": doc.scan.special_category_types,
            "confidentiality_markers": doc.scan.confidentiality_markers,
            "sanitised_preview": doc.sanitised_text[:1200]}


async def intake(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    known = state.get("intake_status") or {}
    docs = await ctx.intake.list_for(state["investigation_id"])
    out: dict[str, Any] = {}
    statuses: dict[str, str] = {}
    events = []
    needs_review: list[tuple[IntakeDocument, Any]] = []
    for doc in docs:
        if known.get(doc.id) in {IntakeStatus.RELEASED, IntakeStatus.WITHHELD, IntakeStatus.REJECTED}:
            continue
        cls = doc.scan.classification
        if doc.kind == IntakeKind.DATASET:
            decision = ctx.governance.evaluate(
                "analyse_internal_dataset", personal_data=cls.personal_data.value,
                confidentiality=cls.confidentiality.value)
        else:
            decision = ctx.governance.evaluate(
                "release_document_to_agents", confidentiality=cls.confidentiality.value,
                personal_data=cls.personal_data.value,
                low_confidence_detections=doc.scan.low_confidence_detections)
        events.append(policy_event(GATEWAY, decision, "intake_document", doc.id))
        if decision.agent_may_proceed:
            _merge(out, release(doc, ctx, state))
            statuses[doc.id] = IntakeStatus.RELEASED
            events.append(audit(GATEWAY, AuditAction.DOCUMENT_RELEASED,
                                f"Released sanitised '{doc.title}' ({cls.label}).", subject_type="intake_document",
                                subject_id=doc.id, policy=decision))
        elif decision.requires_human_approval:
            needs_review.append((doc, decision))
            statuses[doc.id] = IntakeStatus.PENDING_RELEASE
        else:
            statuses[doc.id] = IntakeStatus.WITHHELD
            events.append(audit(GATEWAY, AuditAction.DOCUMENT_WITHHELD,
                                f"Withheld '{doc.title}': {decision.reason}", subject_type="intake_document",
                                subject_id=doc.id, policy=decision))
    out |= {"intake_status": statuses, "audit": events, "pending_review_id": None}
    if needs_review:
        review = HumanReview(
            kind=ReviewKind.PRIVACY_RELEASE,
            title=f"Privacy review: {len(needs_review)} document(s) awaiting release",
            reason=" ".join(sorted({d.reason for _, d in needs_review})),
            subject_ids=[doc.id for doc, _ in needs_review],
            policy_rule_ids=sorted({d.rule_id for _, d in needs_review}),
            required_role=Role.PRIVACY_REVIEWER,
            allowed_actions=[ReviewAction.APPROVE, ReviewAction.REJECT, ReviewAction.MODIFY],
            context={"documents": [scan_card(doc) | {"policy_rule": d.rule_id, "policy_reason": d.reason}
                                   for doc, d in needs_review]})
        out["reviews"] = {review.id: review}
        out["pending_review_id"] = review.id
        out["audit"] = [*events, audit(GATEWAY, AuditAction.REVIEW_REQUESTED, review.title,
                                       subject_type="review", subject_id=review.id)]
    return out


def route_after_intake(state: InvestigationState) -> str:
    if state.get("pending_review_id"):
        return "await_review"
    return "plan" if state.get("hypotheses") else "hypothesise"


# --------------------------------------------------------------------------------------------------
async def hypothesise(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    fr = state["frame"]
    assert fr is not None
    decision = ctx.governance.evaluate("generate_hypotheses")
    datasets = [d for d in ctx.catalog.describe() if d["id"] in (state.get("released_dataset_ids") or {})]
    drafts, calls = await ctx.reasoner.hypothesise(fr, datasets)
    hyps: dict[str, Hypothesis] = {}
    events = [policy_event(HYPOTHESISER, decision)]
    for d in drafts:
        if d.category not in ctx.taxonomy.categories:
            events.append(audit(HYPOTHESISER, AuditAction.ACTION_REFUSED,
                                f"Dropped hypothesis with unknown category '{d.category}'."))
            continue
        h = Hypothesis(statement=d.statement, rationale=d.rationale, category=d.category,
                       segment=d.segment, would_support=d.would_support,
                       would_contradict=d.would_contradict, suggested_source_types=d.suggested_source_types,
                       priority=d.priority)
        hyps[h.id] = h
        events.append(audit(HYPOTHESISER, AuditAction.HYPOTHESIS_CREATED, h.statement,
                            subject_type="hypothesis", subject_id=h.id, category=h.category))
    return {"hypotheses": hyps, "audit": events, "usage": usage_from(calls)}
