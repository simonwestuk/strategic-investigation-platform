# 0005 — Privacy gateway before the agent boundary

**Context.** Investigations need confidential internal material (CRM notes, board papers). Sending raw
content to the main LLM and asking it to redact puts the data in the model call, the traces and the
provider's logs before any control applies.

**Decision.** All internal content passes a gateway (validate → extract → quarantine raw → detect →
classify on two axes → pseudonymise with a separate encrypted vault / withhold special category) before
it can be released. Release is a governed graph step with human review where policy requires.
Architecture tests forbid agent-side imports of the vault, quarantine, detectors or gateway.

**Consequences.** The model, traces and graph state only ever hold sanitised content; consistent
pseudonyms preserve analytical linkage. Cost: detection quality limits sanitisation (mitigated by human
review and Azure AI Language); some analytical nuance is lost by withholding special-category content.
