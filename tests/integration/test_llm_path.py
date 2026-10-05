"""End-to-end test of the LLM reasoner path through the real graph, without a live model.

The scripted model behaves like a plausible but imperfect LLM: it fabricates an evidence ID, paraphrases
a quote instead of copying it, overclaims KNOWN for a causal claim, and cites a non-existent finding.
The deterministic controls must catch all of it, and nothing sensitive may appear in any model input.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from evals.graders.structural import EvalInputs, privacy_leakage
from evals.runner import available
from pydantic import BaseModel

from sip.agents.contracts import (
    ChallengeDraft,
    ChallengeDrafts,
    ClaimDraft,
    ClaimDrafts,
    EvidenceDraft,
    EvidenceDrafts,
    FrameDraft,
    HypothesisDraft,
    HypothesisDrafts,
    LinkDraft,
    OptionDraft,
    OptionDrafts,
)
from sip.agents.llm import AnalysisSpec, LLMReasoner, TaskDraftLLM, TaskDraftsLLM
from sip.config import Settings
from sip.domain import (
    ChallengeKind,
    Classification,
    EvidenceKind,
    Level,
    QuoteVerification,
    ResearchMethod,
    Severity,
    SourceType,
    Stance,
)
from sip.models.fake import ScriptedModel
from sip.models.recording import RecordingModel
from sip.scenarios.loader import Scenario
from sip.services.scripted import run_scenario_to_completion

PASSAGE = re.compile(r'<passage index="(\d+)">(.*?)</passage>', re.S)


def frame(_: str) -> BaseModel:
    return FrameDraft(
        question_types=["diagnostic", "prescriptive"],
        subject="degree-apprenticeship starts",
        direction="declined",
        decision_context="Portfolio planning",
        scope="Portfolio",
        out_of_scope=[],
        objectives=["Separate market from provider effects"],
        assumptions=[],
        ambiguities=[],
        constraints=[],
        needs_clarification=False,
        clarification_questions=[],
    )


def hypothesise(_: str) -> BaseModel:
    def h(cat: str, stmt: str) -> HypothesisDraft:
        return HypothesisDraft(
            category=cat,
            statement=stmt,
            rationale="r",
            would_support=["s"],
            would_contradict=["c"],
            suggested_source_types=[SourceType.OFFICIAL_STATISTICS],
            priority=Level.HIGH,
        )

    return HypothesisDrafts(
        hypotheses=[
            h("market_contraction", "The market has contracted."),
            h("share_loss", "Northstar is losing share."),
            h("offer_format", "Programme duration is uncompetitive."),
            h("not_a_category", "Invalid category."),
        ]
    )


def plan(inp: str) -> BaseModel:
    data = json.loads(inp)
    hyps = [h["id"] for h in data["hypotheses"] if h["status"] == "proposed"]
    if not hyps:
        return TaskDraftsLLM(tasks=[])
    common = {
        "hypothesis_ids": hyps,
        "required_dataset_role": None,
        "required_evidence": "e",
        "preferred_source_types": [],
        "priority": Level.HIGH,
        "expected_value": Level.HIGH,
        "expected_value_rationale": "r",
        "completion_criteria": "c",
    }
    return TaskDraftsLLM(
        tasks=[
            TaskDraftLLM(
                question="Own vs market",
                method=ResearchMethod.DATASET_ANALYSIS,
                queries=[],
                analysis=AnalysisSpec(operation="own_vs_market", dataset_id="northstar_starts"),
                **common,
            ),
            TaskDraftLLM(
                question="Competitor durations",
                method=ResearchMethod.WEB_SEARCH,
                queries=["applied AI engineer apprenticeship duration months"],
                analysis=None,
                **common,
            ),
            TaskDraftLLM(
                question="Lost deal reasons",
                method=ResearchMethod.INTERNAL_DOCUMENTS,
                queries=["too long duration lost"],
                analysis=None,
                **common,
            ),
            TaskDraftLLM(
                question="Bogus op",
                method=ResearchMethod.DATASET_ANALYSIS,
                queries=[],
                analysis=AnalysisSpec(operation="drop_tables", dataset_id="northstar_starts"),
                **common,
            ),
        ]
    )


def extract(inp: str) -> BaseModel:
    hyp_ids = re.findall(r'"id": "(hyp_[0-9a-f]+)"', inp)
    passages = PASSAGE.findall(inp)
    out = []
    for i, (idx, text) in enumerate(passages[:3]):
        sentence = text.split(". ")[0].strip()
        quote = sentence if i != 1 else "A paraphrase that does not appear in the source at all"
        out.append(
            EvidenceDraft(
                passage_index=int(idx),
                quote=quote,
                statement=sentence,
                kind=EvidenceKind.DOCUMENTED_FACT,
                relevance=Level.HIGH,
                links=[LinkDraft(hypothesis_id=h, stance=Stance.SUPPORTS, rationale="r") for h in hyp_ids[:1]],
            )
        )
    return EvidenceDrafts(evidence=out)


def claims(inp: str) -> BaseModel:
    data = json.loads(inp)
    ids = [e["id"] for e in data["evidence"]]
    return ClaimDrafts(
        claims=[
            ClaimDraft(
                statement=f"{data['hypothesis']['statement']} (model view)",
                proposed_classification=Classification.KNOWN,
                causal=True,
                supporting_evidence_ids=[*ids[:3], "evd_fabricated"],
                contradicting_evidence_ids=[],
                inferential_step=None,
                reasoning_summary="r",
                limitations=[],
                missing_evidence=[],
                next_question=None,
                hypothesis_verdict="supports",
            )
        ]
    )


def challenge(inp: str) -> BaseModel:
    data = json.loads(inp)
    target = data["claims"][0]["id"] if data["claims"] else "none"
    return ChallengeDrafts(
        challenges=[
            ChallengeDraft(
                target_id=target,
                kind=ChallengeKind.ALTERNATIVE_EXPLANATION,
                severity=Severity.MINOR,
                argument="Consider substitution.",
                research_question=None,
            )
        ]
    )


def synthesise(inp: str) -> BaseModel:
    data = json.loads(inp)
    fids = [*[f["id"] for f in data["findings"]][:1], "fnd_fabricated"]
    return OptionDrafts(
        options=[
            OptionDraft(
                title="Redesign the programme",
                description="d",
                rationale="r",
                finding_ids=fids,
                expected_benefits=["b"],
                risks=["r"],
                uncertainties=["u"],
                dependencies=[],
                reversibility=Level.LOW,
                reversibility_note="n",
                consequence=Level.HIGH,
                additional_evidence_needed=[],
            )
        ]
    )


RESPONDERS: dict[str, Callable[[str], BaseModel]] = {
    "frame": frame,
    "hypothesise": hypothesise,
    "plan": plan,
    "extract": extract,
    "draft_claims": claims,
    "challenge": challenge,
    "synthesise": synthesise,
}


async def test_llm_path_is_contained_by_deterministic_controls(northstar: Scenario) -> None:
    recorder = RecordingModel(ScriptedModel(responders=RESPONDERS))
    result = await run_scenario_to_completion(northstar, Settings(_env_file=None), reasoner=LLMReasoner(recorder))
    st = result.state

    # Completed with real human checkpoints and usage accounting.
    assert st["decision"] is not None and [i["kind"] for i in result.interrupts][-1] == "decision"
    assert st["usage"].llm_calls == len(recorder.inputs) > 0

    # Hypotheses outside the taxonomy are dropped; invalid operations fail without crashing.
    assert all(h.category != "not_a_category" for h in st["hypotheses"].values())
    assert any(
        t.status.value == "failed" and "drop_tables" in (t.analysis.operation if t.analysis else "")
        for t in st["tasks"].values()
    )

    # Paraphrased quotes are not verified and cannot support claims.
    unverified = [e for e in st["evidence"].values() if e.verification == QuoteVerification.NOT_FOUND]
    assert unverified and all("quote_not_verified" in e.flags for e in unverified)

    # Fabricated evidence IDs are removed; overclaimed causal KNOWN is capped.
    model_claims = [c for c in st["claims"].values() if c.statement.endswith("(model view)")]
    assert model_claims
    for c in model_claims:
        assert "evd_fabricated" not in c.supporting_evidence_ids
        assert c.classification != Classification.KNOWN
        assert any("did not exist" in lim for lim in c.limitations)

    # Options cannot cite findings that do not exist.
    assert all("fnd_fabricated" not in o.finding_ids for o in st["options"].values())

    # Instructions and untrusted data stay in separate channels.
    extract_inputs = [i for i in recorder.inputs if i.startswith("[extract]")]
    assert extract_inputs and all("<untrusted_source" in i for i in extract_inputs)

    # Nothing sensitive reached the model.
    ((_, gt),) = [(s, g) for s, g in available(Settings(_env_file=None)) if s.id == "northstar"]
    leak = privacy_leakage(EvalInputs(state=st, interrupts=[], model_inputs=recorder.inputs), gt)
    assert leak.passed, leak.details
