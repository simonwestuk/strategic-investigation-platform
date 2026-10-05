# Synthetic scenario packs

Everything here is **fictional**. Organisations, people, publishers, statistics, policies and URLs are
invented. Publisher names carry "(synthetic)" and web sources use reserved `.test` domains so nothing can
be mistaken for, or resolve to, a real record. No real employer data exists in this repository.

| Pack | Question |
|---|---|
| `northstar/` | Why have degree-apprenticeship enrolments declined at Northstar Learning Group? |
| `harbourline/` | Why have subscription renewals fallen at Harbourline Coffee Roasters? |

Each pack: `scenario.yaml` (question, as-of date, dataset role manifests, document list, privacy
allowlist), `datasets/` (regenerate with `generate_datasets.py`), `documents/` (internal, containing
synthetic personal data that must be caught by the privacy gateway) and `corpus/` (offline web).
Hidden ground truth is in `evals/scenarios/`.
