# 0002 — The model proposes; deterministic rules dispose

**Context.** LLMs are good at reading, framing and arguing, and unreliable at arithmetic, calibrated
confidence and following rules embedded in prompts.

**Decision.** Every cognitive step goes through a typed `Reasoner` contract whose outputs are drafts.
Code validates IDs and categories, verifies quotes, does arithmetic, computes confidence and caps
classification, runs a deterministic sceptic, and applies governance. Two implementations satisfy the
contract: `LLMReasoner` (Azure OpenAI structured outputs) and `OfflineReasoner` (deterministic).

**Consequences.** Trust properties hold regardless of model behaviour; the system runs and is tested
without credentials; evaluation has a reproducible floor. Cost: maintaining two reasoners, and the
offline one must not be mistaken for intelligence (documented in README and evaluation). Rejected:
model-reported confidence; governance in system prompts only.
