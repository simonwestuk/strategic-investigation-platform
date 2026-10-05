"""Deterministically generate the Harbourline synthetic datasets (fictional).

Hidden truth (evals/scenarios/harbourline/ground_truth.yaml): Espresso Club lost share in a growing market
after an 18% price rise; Filter Club declined with its market; capsule subscriptions are an emerging
segment Harbourline does not offer. Regional splits are constant: the Scotland packaging change is a
planted non-causal correlation.
"""

from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).parent / "datasets"
YEARS = ["2023", "2024", "2025"]
PLANS = {"ESP": ("Espresso Club", [9000, 7600, 6100]), "FIL": ("Filter Club", [6000, 5600, 5200]),
         "OFF": ("Office Plan", [1500, 1550, 1580])}
REGIONS = {"Scotland": 0.2, "North England": 0.35, "South England": 0.45}
MARKET = {"ESP": ("Espresso Club", [120000, 124000, 128000]), "FIL": ("Filter Club", [80000, 75000, 70000]),
          "OFF": ("Office Plan", [30000, 31000, 32000]), "PODS": ("Capsule subscription", [40000, 62000, 90000])}
# plan, channel -> due for renewal per year, renewal rate per year
FUNNEL = {("ESP", "App"): ([6000, 5600, 5200], [0.82, 0.75, 0.64]),
          ("ESP", "Web"): ([5200, 4700, 4300], [0.80, 0.75, 0.70]),
          ("FIL", "App"): ([3600, 3400, 3200], [0.78, 0.78, 0.77]),
          ("FIL", "Web"): ([4100, 3800, 3500], [0.79, 0.78, 0.78]),
          ("OFF", "Web"): ([1700, 1720, 1750], [0.90, 0.90, 0.91])}


def main() -> None:
    HERE.mkdir(exist_ok=True)
    with (HERE / "harbourline_renewals.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["year", "plan_code", "plan", "region", "renewals"])
        for code, (name, values) in PLANS.items():
            for y, total in zip(YEARS, values, strict=True):
                parts = {r: round(total * s) for r, s in REGIONS.items()}
                parts["South England"] += total - sum(parts.values())
                for r, n in parts.items():
                    w.writerow([y, code, name, r, n])
    with (HERE / "market_subscriptions.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["year", "plan_code", "plan_type", "renewals"])
        for code, (name, values) in MARKET.items():
            for y, n in zip(YEARS, values, strict=True):
                w.writerow([y, code, name, n])
    with (HERE / "harbourline_renewal_funnel.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["year", "plan_code", "channel", "due_for_renewal", "renewed"])
        for (code, ch), (due, rates) in FUNNEL.items():
            for i, y in enumerate(YEARS):
                w.writerow([y, code, ch, due[i], round(due[i] * rates[i])])


if __name__ == "__main__":
    main()
