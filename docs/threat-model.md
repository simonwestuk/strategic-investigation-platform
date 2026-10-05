# Threat model

Scope: the API, investigation graph, research tools, privacy gateway, persistence and the Azure reference
deployment. Method: STRIDE over the data flows in [architecture.md](architecture.md), plus AI-specific
threats. "Status" says whether the control is implemented and tested (✅), implemented but untested
against the real service (◑), or roadmap (○).

## Assets

1. Raw confidential documents (quarantine) and the pseudonym mapping (vault): **highest value**.
2. Sanitised evidence corpus, claims and findings (commercially confidential).
3. Decisions and the audit trail (integrity and non-repudiation matter most).
4. Credentials: model endpoint, search keys, database, vault key.
5. Cost: model and search spend.

## Trust boundaries

| Boundary | Untrusted side |
|---|---|
| Browser → API | Users (authenticated, role-limited) |
| Upload → privacy gateway | Document content |
| Fetcher → public web | Every byte of every page |
| Graph → model provider | Model output (treated as a proposal) |
| Agent side → vault/quarantine | Agents (must never reach raw data) |

## Threats and controls

| # | Threat | Control | Status |
|---|---|---|---|
| T1 | **Prompt injection** in a web page or document makes the model change conclusions, invent evidence or "make a decision" | Untrusted text only inside escaped `<untrusted_source>` blocks; system rules say content is data; extraction has no tools and a fixed schema; quotes must be verbatim (content cannot fabricate evidence beyond itself); instruction-like passages flagged and excluded; classification, governance and decisions computed outside the model; decisions require a human actor set by auth | ✅ `test_untrusted_content_is_delimited…`, `injection_resistance` grader (both scenarios plant injections) |
| T2 | Hidden content (HTML comments, `display:none`, zero-width chars) smuggles instructions | Stripped before extraction (`clean_untrusted`, `extract_html`); screening runs on pre-strip text so attempts are still flagged | ✅ `test_html_extraction_drops_hidden_content…` |
| T3 | **SSRF** via a search result URL (cloud metadata, internal services, DNS rebinding, redirects) | Scheme/port allowlist; reject credentials in URL; resolve and require every address be global; connect to the pinned IP with Host/SNI; re-validate each redirect hop; size and content-type limits | ✅ `test_ssrf_url_validation`, `test_redirect_to_private_address_is_refused`; ○ network egress firewall in Azure |
| T4 | Malicious upload (path traversal, polyglot, zip bomb, oversized) | Filename sanitisation; extension allowlist + magic-byte check; size cap before full read; no archives accepted; encrypted PDFs rejected; page cap | ✅ `test_upload_constraints`; ○ malware scanning (Defender for Storage) |
| T5 | Raw PII reaches the model or traces | Gateway before agent boundary; architecture tests; human free text sanitised; trace scrubbing; privacy-leakage grader | ✅ |
| T6 | Re-identification from the vault | Separate DB/credential, HMAC lookup, encrypted values, key outside DB, no API | ✅ locally; ◑ separate DB login in Azure (currently shared admin login, see deployment doc) |
| T7 | Spoofed reviewer / decision-maker | Entra ID JWT validation (signature, issuer, audience, expiry); dev auth refused in production; actor never read from body (extra fields 422); role re-checked inside the graph | ✅ dev path; ◑ Entra path untested against a tenant |
| T8 | Elevation: agent performs human-only action | Policy `human_only`; `Decision` validator; `await_review` refuses non-human actors | ✅ |
| T9 | Repudiation / tampering with audit | Append-only audit table; every review response stores actor; decisions linked to review | ✅ append-only by code; ○ database-level immutability (e.g. row-level revoke, ledger table) |
| T10 | Checkpoint deserialisation RCE | Explicit msgpack allowlist; strict mode in tests/CI | ✅ |
| T11 | Runaway cost / infinite loop | Budget (searches, fetches, model calls, cost), max iterations, per-round task cap, recursion limit, dedupe | ✅ `test_budget_exhaustion_stops_research`, `test_max_iterations_bounds_the_loop` |
| T12 | Search query leaks confidential content to a third-party search provider | Queries built from the framed subject; LLM planner instructed never to include internal content; deterministic filter refuses any query containing pseudonym tokens or withheld markers (audited) | ✅ `test_search_queries_never_carry_pseudonyms`; ○ semantic filter for un-pseudonymised confidential terms |
| T13 | Poisoned or low-quality sources dominate conclusions | Contextual authority tiers, freshness, independence counting, rubric caps, contradiction detection, source-quality grader | ✅ |
| T14 | Secrets in repo or logs | `.gitignore`, gitleaks in CI, Key Vault references in Azure, `SecretStr` settings, no content in logs | ✅ |
| T15 | DoS on API | Upload limits; ○ rate limiting (Front Door / API Management), request timeouts | ○ |

## Residual risks (accepted for V1, documented)

* The local PII detector is heuristic. Mitigation: human release review by default for confidential +
  personal material; Azure AI Language in production.
* LLM extraction can mis-assign stance. Quotes are verified but stance is not; the challenger and
  rubric reduce impact; evaluation measures it.
* In-process background execution: a crash mid-run leaves the investigation "running" until resumed
  manually (checkpoint is intact).
