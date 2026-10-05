"""Investigation API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from sip.api.auth import CurrentActor, require
from sip.api.schemas import (
    AuditOut,
    ClaimChain,
    CreateInvestigation,
    DocumentOut,
    IntakeOut,
    InvestigationDetail,
    InvestigationSummary,
    ReviewResponseIn,
    ScenarioOut,
    SourceOut,
)
from sip.domain import (
    Actor,
    Confidentiality,
    DataClassification,
    InvestigationStatus,
    ResearchBudget,
    ReviewKind,
    Role,
    RoutingDecision,
    SourceType,
    Usage,
)
from sip.domain.investigation import InvestigationFrame
from sip.privacy.extraction import UnsupportedFile
from sip.privacy.gateway import UploadTooLarge
from sip.privacy.models import IntakeDocument
from sip.services.investigations import Conflict, InvestigationService, NotFound
from sip.tools.datasets import Dataset, DatasetCatalog

router = APIRouter(prefix="/api")


def service(request: Request) -> InvestigationService:
    svc: InvestigationService = request.app.state.service
    return svc


Service = Annotated[InvestigationService, Depends(service)]


def _summary(row: dict[str, Any]) -> InvestigationSummary:
    return InvestigationSummary(**{k: row[k] for k in InvestigationSummary.model_fields})


def _intake(doc: IntakeDocument) -> IntakeOut:
    return IntakeOut(
        id=doc.id,
        kind=doc.kind.value,
        title=doc.title,
        filename=doc.filename,
        source_type=doc.source_type.value,
        status=str(doc.status),
        scan=doc.scan,
        uploaded_by=doc.uploaded_by,
        uploaded_at=doc.uploaded_at,
        sanitised_preview=doc.sanitised_text[:1500],
    )


async def _get(svc: InvestigationService, investigation_id: str) -> dict[str, Any]:
    row = await svc.repo.get_investigation(investigation_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation not found")
    return row


@router.get("/me")
async def me(actor: CurrentActor) -> Actor:
    return actor


@router.get("/scenarios", response_model=list[ScenarioOut])
async def scenarios(svc: Service, _: CurrentActor, request: Request) -> list[ScenarioOut]:
    if not request.app.state.settings.sip_show_scenarios:
        return []
    return [
        ScenarioOut(
            id=s.id,
            title=s.title,
            organisation=s.organisation,
            question=s.question,
            datasets=len(s.datasets),
            documents=len(s.documents),
        )
        for s in svc.scenarios()
    ]


@router.post("/investigations", response_model=InvestigationSummary, status_code=201)
async def create(
    body: CreateInvestigation,
    svc: Service,
    actor: Annotated[Actor, Depends(require(Role.INVESTIGATOR))],
    request: Request,
) -> InvestigationSummary:
    if body.scenario_id and not request.app.state.settings.sip_show_scenarios:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Example scenarios are hidden (SIP_SHOW_SCENARIOS=false).")
    try:
        inv_id = await svc.create(
            actor=actor,
            question=body.question,
            scenario_id=body.scenario_id,
            organisation=body.organisation,
            context=body.context,
            budget=body.budget,
        )
    except (NotFound, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _summary(await _get(svc, inv_id))


@router.get("/investigations", response_model=list[InvestigationSummary])
async def list_investigations(svc: Service, _: CurrentActor) -> list[InvestigationSummary]:
    return [_summary(r) for r in await svc.repo.list_investigations()]


@router.get("/investigations/{investigation_id}", response_model=InvestigationDetail)
async def get_investigation(investigation_id: str, svc: Service, _: CurrentActor) -> InvestigationDetail:
    row = await _get(svc, investigation_id)
    p = row["payload"]
    repo = svc.repo
    ents = {
        k: await repo.entities(investigation_id, k)
        for k in (
            "hypotheses",
            "tasks",
            "sources",
            "evidence",
            "claims",
            "findings",
            "contradictions",
            "challenges",
            "options",
            "reviews",
        )
    }
    return InvestigationDetail(
        summary=_summary(row),
        frame=InvestigationFrame.model_validate(p["frame"]) if p.get("frame") else None,
        budget=ResearchBudget.model_validate(p["budget"]) if p.get("budget") else None,
        usage=Usage.model_validate(p["usage"]) if p.get("usage") else None,
        iteration=p.get("iteration", 0),
        routing=[RoutingDecision.model_validate(r) for r in p.get("routing", [])],
        pending_review_id=p.get("pending_review_id"),
        decision=await repo.decision(investigation_id),
        intake=[_intake(d) for d, _ in await repo.intake_for(investigation_id)],
        audit_count=await repo.audit_count(investigation_id),
        segment_names=await _segment_names(svc, investigation_id),
        **ents,
    )


async def _segment_names(svc: InvestigationService, investigation_id: str) -> dict[str, str]:
    datasets = [
        Dataset.from_csv(m, d.sanitised_text) for d, m in await svc.repo.intake_for(investigation_id) if m is not None
    ]
    return DatasetCatalog(datasets).display_names()


@router.post("/investigations/{investigation_id}/start", response_model=InvestigationSummary)
async def start(
    investigation_id: str, svc: Service, actor: Annotated[Actor, Depends(require(Role.INVESTIGATOR))]
) -> InvestigationSummary:
    try:
        await svc.start(investigation_id, actor)
    except NotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _summary(await _get(svc, investigation_id))


@router.post("/investigations/{investigation_id}/documents", response_model=IntakeOut, status_code=201)
async def upload(
    investigation_id: str,
    svc: Service,
    request: Request,
    actor: Annotated[Actor, Depends(require(Role.INVESTIGATOR))],
    file: Annotated[UploadFile, File()],
    title: Annotated[str | None, Form(max_length=300)] = None,
    source_type: Annotated[SourceType, Form()] = SourceType.INTERNAL_DOCUMENT,
    confidentiality: Annotated[Confidentiality, Form()] = Confidentiality.INTERNAL,
) -> IntakeOut:
    await _get(svc, investigation_id)
    limit = request.app.state.settings.sip_upload_max_bytes
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File too large.")
    try:
        doc = await svc.upload(
            investigation_id=investigation_id,
            actor=actor,
            filename=file.filename or "upload",
            content=content,
            title=title,
            source_type=source_type,
            declared=DataClassification(confidentiality=confidentiality),
        )
    except (UnsupportedFile, UploadTooLarge) as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    return _intake(doc)


@router.get("/investigations/{investigation_id}/documents", response_model=list[IntakeOut])
async def documents(investigation_id: str, svc: Service, _: CurrentActor) -> list[IntakeOut]:
    await _get(svc, investigation_id)
    return [_intake(d) for d, _ in await svc.repo.intake_for(investigation_id)]


@router.get("/investigations/{investigation_id}/documents/{document_id}", response_model=DocumentOut)
async def document(investigation_id: str, document_id: str, svc: Service, _: CurrentActor) -> DocumentOut:
    """Privacy scan inspection: sanitised text and scan summary. Raw content is never served."""
    for d, _m in await svc.repo.intake_for(investigation_id):
        if d.id == document_id:
            return DocumentOut(
                id=d.id, title=d.title, status=str(d.status), scan=d.scan, sanitised_text=d.sanitised_text
            )
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")


@router.get("/investigations/{investigation_id}/claims/{claim_id}", response_model=ClaimChain)
async def claim_chain(investigation_id: str, claim_id: str, svc: Service, _: CurrentActor) -> ClaimChain:
    repo = svc.repo
    claim = await repo.entity(investigation_id, "claims", claim_id)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    ids = set(claim.supporting_evidence_ids) | set(claim.contradicting_evidence_ids)
    evidence = [e for e in await repo.entities(investigation_id, "evidence") if e.id in ids]
    src_ids = {e.source_id for e in evidence}
    sources = [s for s in await repo.entities(investigation_id, "sources") if s.id in src_ids]
    findings = [f for f in await repo.entities(investigation_id, "findings") if claim.id in f.claim_ids]
    fids = {f.id for f in findings}
    options = [
        o
        for o in await repo.entities(investigation_id, "options")
        if claim.id in o.claim_ids or fids & set(o.finding_ids)
    ]
    challenges = [c for c in await repo.entities(investigation_id, "challenges") if c.target_id == claim.id]
    return ClaimChain(
        claim=claim, evidence=evidence, sources=sources, findings=findings, options=options, challenges=challenges
    )


@router.get("/investigations/{investigation_id}/sources/{source_id}", response_model=SourceOut)
async def source(investigation_id: str, source_id: str, svc: Service, _: CurrentActor) -> SourceOut:
    s = await svc.repo.entity(investigation_id, "sources", source_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    content = await svc.repo.source_content(investigation_id, source_id)
    return SourceOut(**s.model_dump(), content=content)


@router.get("/investigations/{investigation_id}/audit", response_model=list[AuditOut])
async def audit_trail(investigation_id: str, svc: Service, _: CurrentActor, limit: int = 500) -> list[AuditOut]:
    """Most recent events first. ``limit`` is capped at 2000; ``audit_count`` on the detail gives the total."""
    await _get(svc, investigation_id)
    return [AuditOut(**r) for r in await svc.repo.audit(investigation_id, limit=max(1, min(limit, 2000)))]


@router.get("/investigations/{investigation_id}/{collection}")
async def collection(investigation_id: str, collection: str, svc: Service, _: CurrentActor) -> list[Any]:
    mapping = {
        "hypotheses": "hypotheses",
        "tasks": "tasks",
        "claims": "claims",
        "evidence": "evidence",
        "sources": "sources",
        "findings": "findings",
        "contradictions": "contradictions",
        "challenges": "challenges",
        "options": "options",
        "reviews": "reviews",
    }
    if collection not in mapping:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown collection")
    await _get(svc, investigation_id)
    return await svc.repo.entities(investigation_id, mapping[collection])


@router.post("/investigations/{investigation_id}/reviews/{review_id}/respond", response_model=InvestigationSummary)
async def respond(
    investigation_id: str, review_id: str, body: ReviewResponseIn, svc: Service, actor: CurrentActor, request: Request
) -> InvestigationSummary:
    review = await svc.repo.entity(investigation_id, "reviews", review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found")
    if not actor.has_role(review.required_role):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role '{review.required_role.value}'.")
    if body.action not in review.allowed_actions:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Action '{body.action.value}' not allowed.")
    if review.kind == ReviewKind.DECISION and body.action.value == "decide" and body.decision is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A decision payload is required.")
    payload = await _sanitise_free_text(body, request)
    # The actor is ALWAYS the authenticated principal; it is never read from the request body.
    payload["actor"] = actor.model_dump(mode="json")
    try:
        await svc.respond(investigation_id, review_id, payload)
    except Conflict as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return _summary(await _get(svc, investigation_id))


async def _sanitise_free_text(body: ReviewResponseIn, request: Request) -> dict[str, Any]:
    """Human free text enters graph state (and therefore model context), so it crosses the privacy
    gateway too: names/emails a reviewer types are pseudonymised before the agents see them."""
    gw = request.app.state.gateway_factory(None)
    data = body.model_dump(mode="json")
    if data.get("note"):
        data["note"] = await gw.sanitise_text(data["note"])
    data["research_requests"] = [await gw.sanitise_text(q) for q in data["research_requests"]]
    for ch in data["challenges"]:
        ch["argument"] = await gw.sanitise_text(ch["argument"])
    for o in data["classification_overrides"]:
        o["reason"] = await gw.sanitise_text(o["reason"])
    if data.get("decision"):
        for k in ("statement", "rationale"):
            data["decision"][k] = await gw.sanitise_text(data["decision"][k])
    return data


__all__ = ["InvestigationStatus", "router"]
