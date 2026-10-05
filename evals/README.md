# Evaluation harness

See [docs/evaluation.md](../docs/evaluation.md) for what is measured and current results.

```
evals/
  scenarios/<id>/ground_truth.yaml   hidden ground truth (never read by src/sip)
  graders/ground_truth.py            schema
  graders/structural.py              12 deterministic graders + manual strategic-usefulness rubric
  experiments/langsmith_experiment.py optional LangSmith dataset + experiment
  runner.py                          `sip eval run` implementation
  reports/                           output (git-ignored)
```

## Adding a scenario

1. Create `data/synthetic/<id>/` with `scenario.yaml`, datasets (with role manifests), internal documents
   and an offline `corpus/` (fictional publishers on `.test` domains).
2. Write `evals/scenarios/<id>/ground_truth.yaml` **before** running the system on it.
3. `sip eval run --scenario <id>` and record the first (blind) result in docs/evaluation.md.

## Strategic usefulness

Manual: a domain expert scores each option 1–5 on relevance, caveats, actionability and completeness.
