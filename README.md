# Strategic Investigation Platform

A governed, evidence-grounded agentic platform for investigating ambiguous strategic questions using internal and external evidence.

> **Autonomous research. Governed reasoning. Human decisions.**

## Flagship scenario

Why have a fictional provider's degree-apprenticeship enrolments declined, and what should it do?

The scenario is synthetic. It is designed to test whether the system can separate market contraction, market-share loss, proposition weakness, AI-programme substitution, policy/funding effects and internal funnel problems without inventing certainty.

## What is implemented in the first scaffold

- Pydantic domain model for investigations, hypotheses, sources, evidence, claims, research tasks, options and human reviews.
- LangGraph state and an executable investigation graph with a research loop.
- Explicit governance policy layer.
- Pre-agent privacy gateway baseline.
- Azure/OpenAI and LangSmith environment contract.
- Tests and a runnable synthetic flagship investigation.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m sip.main
pytest
```

## Next implementation slice

1. Azure OpenAI/Foundry model provider with structured outputs.
2. External research tool adapter and source-quality policy.
3. Evidence extraction and claim-to-evidence provenance.
4. LangSmith tracing/evaluation dataset.
5. Azure AI Language PII adapter and pseudonymisation store.
6. Persistent LangGraph checkpointing and human interrupts.

See `docs/architecture.md`.
