# Governance and human-in-the-loop

Governance here is executable. The policy pack is YAML (`src/sip/governance/policies/default.yaml`),
evaluated by a small engine (`src/sip/governance/policy.py`), called by graph nodes and API handlers,
and recorded in the audit trail with the rule that fired. Prompts restate the rules for the model, but
nothing depends on the model obeying them.

## Policy model

Each **activity** has ordered rules. A rule matches activity **attributes** (`when`) and yields:

| Field | Meaning |
|---|---|
| `autonomy` | `autonomous` · `autonomous_with_audit` · `human_approval` · `human_only` · `prohibited` |
| `required_role` | RBAC role needed to approve or perform |
| `risk`, `consequence` | Recorded on the decision and in audit |
| `reason` | Shown to reviewers and in audit |

First match wins. **No match means deny** (`deny.no_matching_rule`).

## Activities in the default pack

| Activity | Default behaviour | Escalation |
|---|---|---|
| `frame_question` | autonomous | human approval (investigator) if the question needs clarification |
| `generate_hypotheses`, `plan_research`, `search_public_web`, `fetch_public_url`, `read_sanitised_document` | autonomous | — |
| `analyse_internal_dataset` | autonomous with audit | **prohibited** for row-level personal data |
| `release_document_to_agents` | autonomous with audit | **prohibited** if restricted; **privacy_reviewer** approval for special-category data, low-confidence detections, or confidential + personal |
| `classify_claim` | autonomous with audit (rubric-bound) | — |
| `override_classification` | **human only** (governance_reviewer) | — |
| `publish_findings` | autonomous with audit | **governance_reviewer** approval if research stopped with blocking challenges open |
| `generate_strategic_options` | autonomous with audit | — |
| `present_recommendation` | autonomous with audit | **governance_reviewer** approval if any option is high-consequence, or evidenced options rest on low-confidence findings |
| `record_decision` | **human only** (decision_maker) | — |
| `take_external_action` | **prohibited** | — |

## Human-in-the-loop as graph execution

Every human checkpoint is a real LangGraph `interrupt()` in `await_review`, persisted by the
checkpointer, resumed with `Command(resume=...)`. A review can wait indefinitely; the run resumes from
the checkpoint.

| Review | Raised by | Allowed actions |
|---|---|---|
| Clarification | `frame` | approve, modify (with note), reject (ends the investigation) |
| Privacy release | `intake` | approve / reject / modify **per document** |
| Findings | `findings_gate` | approve (blocking challenges become stated limitations), request further investigation |
| Options | `options_gate` | approve / modify / reject **per option**, edit title/description/risks, request further investigation |
| Decision | `decision_room` | decide (human-only Decision), request further investigation |

Every review also accepts (through the API and the full working view; the briefing keeps only the essential
choices): a **note**, **human challenges** (to a claim or an assumption; they become
`HUMAN_CHALLENGE` challenges with research questions), **research requests** (become `HUMAN`-origin
tasks), **classification overrides** (require governance_reviewer; recorded as `HumanOverride` with
actor, previous value and reason; never silently recomputed away), and **additional iterations** (≤3).
Supplying missing evidence = upload through the gateway, then respond with
`request_further_investigation`; the graph routes through `intake` before planning.

## Recommendation ≠ Decision

* `StrategicOption.requires_human_decision` is a constant `True`.
* `Decision` validates that `decided_by.kind == human`, the actor has `decision_maker`, uncertainties
  were acknowledged, and adopting requires option IDs.
* The only code path that constructs a `Decision` is `await_review` handling a `DECISION` review, with
  an actor that the **API sets from the authenticated principal**. Request bodies with an `actor` field
  are rejected (422).
* `await_review` re-checks actor kind, role and allowed action; refusals are audited and the review
  stays pending.
* Tests: `test_only_a_human_decision_maker_can_create_a_decision`,
  `test_non_human_and_wrong_role_responses_are_refused`, `test_end_to_end_review_flow_with_rbac`,
  `test_invalid_decision_is_refused_and_review_stays_pending`.

## Operating modes

**Single operator (default).** One person directs the agents and holds every approval: privacy release,
findings, options and the decision. The checkpoints are unchanged — the agents still stop and wait — but
there is no hand-off between people. In dev auth the default identity is `Operator` with every approval
role; the web app hides role switching (`NEXT_PUBLIC_TEAM_MODE=false`).

**Team mode.** The same checkpoints, split across roles (below), for organisations that want separation of
duties — e.g. a privacy officer releasing data and an executive making the decision. Roles come from
Entra ID app roles in deployment; the web app shows a persona switcher in dev (`NEXT_PUBLIC_TEAM_MODE=true`).
The backend enforces roles identically in both modes; single-operator is simply one person holding all of them.

## RBAC

| Role | Can |
|---|---|
| viewer | read |
| investigator | create/start investigations, upload evidence, answer clarification |
| privacy_reviewer | resolve privacy release reviews |
| governance_reviewer | resolve findings/options reviews, override classifications |
| decision_maker | record decisions |
| admin | everything |

Roles map from Entra ID app roles (`roles` claim) in deployed environments; dev mode reads trusted
headers and refuses to start when `SIP_ENV=production`.

## Audit

`AuditEvent` records actor (human/agent/system), action, subject, policy rule, and scalar details.
Raw content is never written to audit (`_safe_attributes` drops non-scalars). Events are projected to
the append-only `audit_events` table. The Northstar run produces ~270 events, ~45 of them policy
evaluations.

## Changing policy

Edit or replace the YAML pack; the engine validates it with Pydantic on load. Tests in
`tests/unit/test_governance.py` document the expected behaviour of every rule and should be updated
with any policy change.
