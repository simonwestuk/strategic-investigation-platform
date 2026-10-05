"""Findings gate, Strategy Synthesiser, options gate, Decision Room and the human-review node.

Pattern: a *gate* node evaluates policy and, if a human is required, writes a pending ``HumanReview``
into state and routes to ``await_review``. ``await_review`` is the only node that calls
``interrupt()``. Splitting the two matters: LangGraph re-runs an interrupted node from the start on
resume, so anything written before ``interrupt()`` in the same node would be lost.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import ValidationError

from sip.agents.contracts import FindingView
from sip.domain import (
    Actor,
    ActorKind,
    AuditAction,
    Challenge,
    ChallengeKind,
    ChallengeStatus,
    Classification,
    ConfidenceBand,
    Decision,
    DecisionType,
    Finding,
    FindingStatus,
    HumanOverride,
    HumanReview,
    HypothesisStatus,
    OptionReviewStatus,
    ReviewAction,
    ReviewKind,
    ReviewResponse,
    ReviewState,
    ReviewStatus,
    Role,
    Severity,
    StrategicOption,
    utcnow,
)
from sip.evidence.confidence import FINDING_CRITERIA, meets_finding_criteria
from sip.evidence.ledger import stable_id
from sip.graph.context import InvestigationContext
from sip.graph.helpers import audit, policy_event, usage_from
from sip.graph.nodes.framing import release
from sip.graph.state import InvestigationState
from sip.privacy.models import IntakeStatus

GATE = Actor.agent("governance_gate")
SYNTH = Actor.agent("strategy_synthesiser")
_BAND_RANK = {ConfidenceBand.VERY_LOW: 0, ConfidenceBand.LOW: 1, ConfidenceBand.MODERATE: 2, ConfidenceBand.HIGH: 3}


def _request(review: HumanReview, actor: Actor = GATE) -> dict[str, Any]:
    return {"reviews": {review.id: review}, "pending_review_id": review.id,
            "audit": [audit(actor, AuditAction.REVIEW_REQUESTED, review.title, subject_type="review",
                            subject_id=review.id, kind=review.kind.value)]}


# ---- findings ------------------------------------------------------------------------------------
async def findings_gate(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    claims = state.get("claims") or {}
    evidence = state.get("evidence") or {}
    challenges = list((state.get("challenges") or {}).values())
    findings: dict[str, Finding] = {}
    events = []
    for c in claims.values():
        if not c.active or not meets_finding_criteria(c, evidence, challenges):
            continue
        fid = stable_id("fnd", c.id)
        prior = (state.get("findings") or {}).get(fid)
        findings[fid] = Finding(
            id=fid, title=c.statement[:110] + ("…" if len(c.statement) > 110 else ""), statement=c.statement,
            claim_ids=[c.id], hypothesis_ids=c.related_hypothesis_ids, classification=c.classification,
            confidence_band=c.confidence.band if c.confidence else ConfidenceBand.LOW,
            criteria_met=list(FINDING_CRITERIA), status=prior.status if prior else FindingStatus.DRAFT)
        if prior is None:
            events.append(audit(GATE, AuditAction.FINDING_PROMOTED, c.statement[:160], subject_type="finding",
                                subject_id=fid))
    hyp_updates = {}
    for h in (state.get("hypotheses") or {}).values():
        if h.status in {HypothesisStatus.PROPOSED, HypothesisStatus.INVESTIGATING}:
            hyp_updates[h.id] = h.model_copy(update={
                "status": HypothesisStatus.UNRESOLVED, "updated_at": utcnow(),
                "status_reason": "Research stopped without evidence that discriminates for or against it."})
    open_blocking = [c for c in challenges if c.status == ChallengeStatus.OPEN and c.severity == Severity.BLOCKING]
    decision = ctx.governance.evaluate("publish_findings", open_blocking_challenges=len(open_blocking))
    events.append(policy_event(GATE, decision))
    out: dict[str, Any] = {"findings": findings, "hypotheses": hyp_updates, "audit": events,
                           "pending_review_id": None}
    if decision.requires_human_approval:
        review = HumanReview(
            kind=ReviewKind.FINDINGS, title="Findings review: research stopped with blocking challenges open",
            reason=decision.reason, subject_ids=[c.id for c in open_blocking], policy_rule_ids=[decision.rule_id],
            required_role=decision.required_role or Role.GOVERNANCE_REVIEWER,
            allowed_actions=[ReviewAction.APPROVE, ReviewAction.REQUEST_FURTHER_INVESTIGATION],
            context={"open_blocking_challenges": [{"id": c.id, "kind": c.kind.value, "target_id": c.target_id,
                                                   "argument": c.argument} for c in open_blocking],
                     "findings": [{"id": f.id, "statement": f.statement} for f in findings.values()],
                     "stop_reason": (state.get("routing") or [None])[-1].rationale  # type: ignore[union-attr]
                     if state.get("routing") else None})
        req = _request(review)
        out |= {"reviews": req["reviews"], "pending_review_id": review.id, "audit": events + req["audit"]}
    return out


def route_after_findings(state: InvestigationState) -> str:
    return "await_review" if state.get("pending_review_id") else "synthesise"


# ---- synthesis -----------------------------------------------------------------------------------
async def synthesise(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    fr = state["frame"]
    assert fr is not None
    hyps = state.get("hypotheses") or {}
    claims = state.get("claims") or {}
    findings = {k: f for k, f in (state.get("findings") or {}).items() if f.status != FindingStatus.REJECTED}
    names = ctx.catalog.display_names()
    views = []
    for f in findings.values():
        hs = [hyps[h] for h in f.hypothesis_ids if h in hyps and hyps[h].status in
              {HypothesisStatus.SUPPORTED, HypothesisStatus.SPLIT}]
        if not any(claims[c].causal for c in f.claim_ids if c in claims):
            continue  # options respond to causal findings; factual findings are context
        views.append(FindingView(id=f.id, statement=f.statement, classification=f.classification,
                                 confidence_band=f.confidence_band.value,
                                 hypothesis_categories=sorted({h.category for h in hs}),
                                 segments=sorted({names.get(h.segment, h.segment) for h in hs if h.segment})))
    unknowns = [c.statement for c in claims.values() if c.active and c.classification == Classification.UNKNOWN]
    caveats = [c.argument for c in (state.get("challenges") or {}).values()
               if c.kind == ChallengeKind.ALTERNATIVE_EXPLANATION and c.status == ChallengeStatus.OPEN]
    drafts, calls = await ctx.reasoner.synthesise(fr, views, unknowns, caveats)
    options: dict[str, StrategicOption] = {}
    events = [policy_event(SYNTH, ctx.governance.evaluate("generate_strategic_options"))]
    for d in drafts:
        fids = [f for f in d.finding_ids if f in findings]
        bands = [findings[f].confidence_band for f in fids]
        band = min(bands, key=lambda b: _BAND_RANK[b]) if bands else ConfidenceBand.LOW
        opt = StrategicOption(
            id=stable_id("opt", d.title), title=d.title, description=d.description, rationale=d.rationale,
            finding_ids=fids, claim_ids=sorted({c for f in fids for c in findings[f].claim_ids}),
            expected_benefits=d.expected_benefits, risks=d.risks, uncertainties=d.uncertainties,
            dependencies=d.dependencies, reversibility=d.reversibility, reversibility_note=d.reversibility_note,
            consequence=d.consequence, additional_evidence_needed=d.additional_evidence_needed,
            confidence_band=band, created_by=SYNTH)
        options[opt.id] = opt
        events.append(audit(SYNTH, AuditAction.OPTION_GENERATED, opt.title, subject_type="option",
                            subject_id=opt.id, consequence=opt.consequence.value))
    return {"options": options, "audit": events, "usage": usage_from(calls)}


async def options_gate(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    options = [o for o in (state.get("options") or {}).values() if o.review_status == OptionReviewStatus.DRAFT]
    if not options:
        return {"pending_review_id": None}
    max_cons = max((o.consequence for o in options), key=lambda lv: lv.rank)
    evidenced = [o for o in options if o.finding_ids]
    min_conf = min((_BAND_RANK[o.confidence_band] for o in evidenced), default=0)
    decision = ctx.governance.evaluate("present_recommendation", max_consequence=max_cons.value,
                                       min_confidence_rank=min_conf)
    events = [policy_event(GATE, decision)]
    if decision.requires_human_approval:
        review = HumanReview(
            kind=ReviewKind.OPTIONS, title="Review strategic options before they reach decision-makers",
            reason=decision.reason, subject_ids=[o.id for o in options], policy_rule_ids=[decision.rule_id],
            required_role=decision.required_role or Role.GOVERNANCE_REVIEWER,
            allowed_actions=[ReviewAction.APPROVE, ReviewAction.MODIFY, ReviewAction.REJECT,
                             ReviewAction.REQUEST_FURTHER_INVESTIGATION],
            context={"options": [{"id": o.id, "title": o.title, "consequence": o.consequence.value,
                                  "confidence_band": o.confidence_band.value} for o in options]})
        updates = {o.id: o.model_copy(update={"review_status": OptionReviewStatus.PENDING_REVIEW}) for o in options}
        req = _request(review)
        return {"options": updates, "reviews": req["reviews"], "pending_review_id": review.id,
                "audit": events + req["audit"]}
    updates = {o.id: o.model_copy(update={"review_status": OptionReviewStatus.APPROVED_FOR_DECISION})
               for o in options}
    return {"options": updates, "audit": events, "pending_review_id": None}


def route_after_options(state: InvestigationState) -> str:
    return "await_review" if state.get("pending_review_id") else "decision_room"


async def decision_room(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    decision = ctx.governance.evaluate("record_decision")
    claims = state.get("claims") or {}
    unknown = [c for c in claims.values() if c.active and c.classification == Classification.UNKNOWN]
    options = [o for o in (state.get("options") or {}).values()
               if o.review_status in {OptionReviewStatus.APPROVED_FOR_DECISION, OptionReviewStatus.MODIFIED}]
    review = HumanReview(
        kind=ReviewKind.DECISION, title="Decision required", reason=decision.reason,
        subject_ids=[o.id for o in options], policy_rule_ids=[decision.rule_id],
        required_role=decision.required_role or Role.DECISION_MAKER,
        allowed_actions=[ReviewAction.DECIDE, ReviewAction.REQUEST_FURTHER_INVESTIGATION],
        context={"options": [{"id": o.id, "title": o.title} for o in options],
                 "unknowns_to_acknowledge": [{"id": c.id, "statement": c.statement} for c in unknown],
                 "decision_types": [t.value for t in DecisionType]})
    req = _request(review)
    req["audit"].insert(0, policy_event(GATE, decision))
    return req


# ---- the human review node -----------------------------------------------------------------------
async def await_review(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    review = state["reviews"][state["pending_review_id"]]  # type: ignore[index]
    raw = interrupt({"review_id": review.id, "kind": review.kind.value, "title": review.title,
                     "required_role": review.required_role.value,
                     "allowed_actions": [a.value for a in review.allowed_actions]})
    try:
        response = ReviewResponse.model_validate(raw)
    except ValidationError as exc:
        return _refuse(review, f"Malformed review response: {exc.error_count()} error(s).")
    actor = response.actor
    if actor.kind != ActorKind.HUMAN:
        return _refuse(review, "Reviews can only be resolved by a human.")
    if not actor.has_role(review.required_role):
        return _refuse(review, f"{actor.display_name} lacks the {review.required_role.value} role.")
    if response.action not in review.allowed_actions:
        return _refuse(review, f"Action '{response.action.value}' is not allowed for this review.")

    out: dict[str, Any] = {}
    events = []
    for k, v in _apply_common(state, response, ctx, events).items():
        out[k] = v
    handler = {ReviewKind.CLARIFICATION: _clarification, ReviewKind.PRIVACY_RELEASE: _privacy,
               ReviewKind.FINDINGS: _findings, ReviewKind.OPTIONS: _options, ReviewKind.DECISION: _decision}
    result = await handler[review.kind](state, review, response, ctx, events)
    if result is None:  # handler refused (e.g. invalid decision)
        return {"audit": events, "next_after_review": "await_review"}
    for k, v in result.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    resolved = review.model_copy(update={"status": ReviewStatus.RESOLVED, "response": response})
    out["reviews"] = {**out.get("reviews", {}), review.id: resolved}
    out["pending_review_id"] = None
    events.append(audit(actor, AuditAction.REVIEW_RESOLVED, f"{review.kind.value}: {response.action.value}",
                        subject_type="review", subject_id=review.id, note_present=bool(response.note)))
    out["audit"] = events
    return out


def _refuse(review: HumanReview, reason: str) -> dict[str, Any]:
    return {"audit": [audit(Actor.system(), AuditAction.ACTION_REFUSED, reason, subject_type="review",
                            subject_id=review.id)], "next_after_review": "await_review"}


def _apply_common(state: InvestigationState, r: ReviewResponse, ctx: InvestigationContext,
                  events: list[Any]) -> dict[str, Any]:
    """Overrides, human challenges, research requests and extra iterations - valid on any review."""
    out: dict[str, Any] = {}
    claims = state.get("claims") or {}
    if r.classification_overrides:
        policy = ctx.governance.evaluate("override_classification")
        if policy.permits(ActorKind.HUMAN, r.actor.roles):
            updates = {}
            for o in r.classification_overrides:
                c = claims.get(o.claim_id)
                if c is None:
                    continue
                updates[c.id] = c.model_copy(update={
                    "classification": o.classification, "review_state": ReviewState.OVERRIDDEN,
                    "human_override": HumanOverride(actor=r.actor, previous=c.classification,
                                                    new=o.classification, reason=o.reason)})
                events.append(audit(r.actor, AuditAction.CLAIM_OVERRIDDEN,
                                    f"{c.classification.value} -> {o.classification.value}: {o.reason[:120]}",
                                    subject_type="claim", subject_id=c.id, policy=policy))
            out["claims"] = updates
        else:
            events.append(audit(r.actor, AuditAction.ACTION_REFUSED,
                                f"Classification override requires {policy.required_role}.", policy=policy))
    if r.challenges:
        out["challenges"] = {}
        for hc in r.challenges:
            ch = Challenge(target_type="claim" if hc.target_id in claims else "investigation",
                           target_id=hc.target_id, kind=ChallengeKind.HUMAN_CHALLENGE, severity=Severity.MAJOR,
                           argument=hc.argument, research_question=hc.argument, raised_by=r.actor,
                           iteration=state.get("iteration", 0))
            out["challenges"][ch.id] = ch
            events.append(audit(r.actor, AuditAction.CHALLENGE_RAISED, hc.argument[:160],
                                subject_type="challenge", subject_id=ch.id))
    if r.research_requests:
        out["research_requests"] = [*(state.get("research_requests") or []), *r.research_requests]
    if r.additional_iterations:
        budget = state["budget"]
        out["budget"] = budget.model_copy(update={"max_iterations": budget.max_iterations + r.additional_iterations})
    return out


async def _clarification(state, review, r, ctx, events):  # type: ignore[no-untyped-def]
    fr = state["frame"]
    if r.action == ReviewAction.REJECT:
        return {"next_after_review": END}
    note = f" Clarification from {r.actor.display_name}: {r.note}" if r.note else ""
    return {"frame": fr.model_copy(update={"needs_clarification": False,
                                           "decision_context": fr.decision_context + note}),
            "next_after_review": "intake"}


async def _privacy(state, review, r, ctx, events):  # type: ignore[no-untyped-def]
    docs = {d.id: d for d in await ctx.intake.list_for(state["investigation_id"])}
    per_item = {i.item_id: i.action for i in r.items}
    out: dict[str, Any] = {"intake_status": {}}
    for doc_id in review.subject_ids:
        action = per_item.get(doc_id, r.action)
        doc = docs.get(doc_id)
        if doc is not None and action in {ReviewAction.APPROVE, ReviewAction.MODIFY}:
            for k, v in release(doc, ctx, state).items():
                out.setdefault(k, {}).update(v)
            out["intake_status"][doc_id] = IntakeStatus.RELEASED
            events.append(audit(r.actor, AuditAction.DOCUMENT_RELEASED, f"Approved release of '{doc.title}'.",
                                subject_type="intake_document", subject_id=doc_id))
        else:
            out["intake_status"][doc_id] = IntakeStatus.REJECTED
            events.append(audit(r.actor, AuditAction.DOCUMENT_WITHHELD, "Release rejected by privacy reviewer.",
                                subject_type="intake_document", subject_id=doc_id))
    out["next_after_review"] = "intake"
    return out


async def _findings(state, review, r, ctx, events):  # type: ignore[no-untyped-def]
    if r.action == ReviewAction.REQUEST_FURTHER_INVESTIGATION:
        return {"next_after_review": "intake"}
    chls = {c.id: c.model_copy(update={"status": ChallengeStatus.ACCEPTED_AS_LIMITATION,
                                       "resolution_note": f"Accepted as a limitation by {r.actor.display_name}."})
            for c in (state.get("challenges") or {}).values()
            if c.status == ChallengeStatus.OPEN and c.severity == Severity.BLOCKING}
    fnds = {f.id: f.model_copy(update={"status": FindingStatus.ACCEPTED})
            for f in (state.get("findings") or {}).values()}
    return {"challenges": chls, "findings": fnds, "next_after_review": "synthesise"}


_EDITABLE = {"title", "description", "risks", "uncertainties", "dependencies", "additional_evidence_needed"}


async def _options(state, review, r, ctx, events):  # type: ignore[no-untyped-def]
    if r.action == ReviewAction.REQUEST_FURTHER_INVESTIGATION:
        reset = {o.id: o.model_copy(update={"review_status": OptionReviewStatus.REJECTED,
                                            "reviewer_note": "Superseded: further investigation requested."})
                 for o in (state.get("options") or {}).values() if o.id in review.subject_ids}
        return {"options": reset, "next_after_review": "intake"}
    per_item = {i.item_id: i for i in r.items}
    updates = {}
    for oid in review.subject_ids:
        o = state["options"][oid]
        item = per_item.get(oid)
        action = item.action if item else r.action
        edits = {k: v for k, v in r.option_edits.get(oid, {}).items() if k in _EDITABLE}
        if action == ReviewAction.REJECT:
            status = OptionReviewStatus.REJECTED
        elif edits or action == ReviewAction.MODIFY:
            status = OptionReviewStatus.MODIFIED
        else:
            status = OptionReviewStatus.APPROVED_FOR_DECISION
        updates[oid] = o.model_copy(update={**edits, "review_status": status,
                                            "reviewer_note": (item.note if item else None) or r.note})
    return {"options": updates, "next_after_review": "decision_room"}


async def _decision(state, review, r, ctx, events):  # type: ignore[no-untyped-def]
    if r.action == ReviewAction.REQUEST_FURTHER_INVESTIGATION:
        return {"next_after_review": "intake"}
    policy = ctx.governance.evaluate("record_decision")
    if not policy.permits(ActorKind.HUMAN, r.actor.roles) or r.decision is None:
        events.append(audit(r.actor, AuditAction.ACTION_REFUSED, "Decision payload missing or not permitted.",
                            policy=policy))
        return None
    valid = set(review.subject_ids)
    try:
        decision = Decision(
            decision_type=DecisionType(r.decision.decision_type), statement=r.decision.statement,
            rationale=r.decision.rationale, option_ids=[o for o in r.decision.option_ids if o in valid],
            conditions=r.decision.conditions, uncertainties_acknowledged=r.decision.uncertainties_acknowledged,
            acknowledged_unknown_claim_ids=r.decision.acknowledged_unknown_claim_ids,
            decided_by=r.actor, review_id=review.id)
    except (ValidationError, ValueError) as exc:
        events.append(audit(r.actor, AuditAction.ACTION_REFUSED, f"Decision rejected: {str(exc)[:200]}",
                            policy=policy))
        return None
    events.append(audit(r.actor, AuditAction.DECISION_RECORDED, decision.statement[:160], subject_type="decision",
                        subject_id=decision.id, policy=policy, decision_type=decision.decision_type.value))
    out: dict[str, Any] = {"decision": decision, "next_after_review": END}
    if decision.decision_type == DecisionType.COMMISSION_FURTHER_INVESTIGATION:
        out["research_requests"] = [decision.statement]
    return out


def route_after_review(state: InvestigationState) -> str:
    return state.get("next_after_review") or END

