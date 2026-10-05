"""Deterministically generate the Northstar synthetic datasets.

Run: python data/synthetic/northstar/generate_datasets.py

The numbers encode the scenario's hidden ground truth (see evals/scenarios/northstar/ground_truth.yaml).
They are fictional. Regional and segment splits are held (near-)constant across years on purpose: the
North-region sales restructure in 2023 is a *planted non-causal correlation*.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

HERE = Path(__file__).parent / "datasets"
YEARS = ["2022/23", "2023/24", "2024/25", "2025/26"]

PROGRAMMES = {
    # code: (name, level, duration_months, yearly starts)
    "DTS6": ("Digital & Technology Solutions Professional", 6, 36, [620, 560, 450, 350]),
    "DSP6": ("Data Science Professional", 6, 36, [180, 172, 160, 150]),
    "CMDA6": ("Chartered Manager Degree Apprenticeship", 6, 36, [300, 305, 296, 290]),
    "SL7": ("Senior Leader (MBA)", 7, 24, [400, 385, 300, 170]),
}
REGIONS = {"North": 0.30, "Midlands": 0.30, "South": 0.40}
SEGMENTS = {"Large employer": 0.70, "SME": 0.30}

NATIONAL = {
    # standard_code: (standard, level, yearly national starts)
    "DTS6": ("Digital & Technology Solutions Professional", 6, [7800, 8000, 8150, 8250]),
    "DSP6": ("Data Science Professional", 6, [3100, 2950, 2650, 2350]),
    "CMDA6": ("Chartered Manager Degree Apprenticeship", 6, [9800, 9900, 9850, 9950]),
    "SL7": ("Senior Leader (MBA)", 7, [14000, 13300, 9900, 5300]),
    "AIE6": ("Applied AI Engineer", 6, [0, 0, 1100, 2600]),
    "AIP4": ("AI & Automation Practitioner", 4, [1200, 3400, 5900, 7800]),
    "DA4": ("Data Analyst", 4, [11000, 10400, 9600, 9100]),
}

# Funnel: (programme, segment) -> per-year (enquiries, proposals, win rate, learners per won employer)
FUNNEL = {
    ("DTS6", "Large employer"): ([140, 142, 145, 141], [60, 62, 64, 61], [0.45, 0.40, 0.31, 0.26], 16),
    ("DTS6", "SME"): ([220, 205, 182, 160], [70, 65, 58, 52], [0.40, 0.40, 0.38, 0.37], 2),
    ("DSP6", "Large employer"): ([60, 58, 55, 52], [24, 23, 21, 20], [0.42, 0.42, 0.43, 0.42], 9),
    ("DSP6", "SME"): ([40, 38, 36, 34], [14, 13, 12, 12], [0.36, 0.38, 0.37, 0.36], 2),
    ("CMDA6", "Large employer"): ([90, 92, 91, 90], [35, 36, 35, 35], [0.47, 0.46, 0.47, 0.46], 12),
    ("CMDA6", "SME"): ([70, 71, 70, 69], [22, 22, 22, 21], [0.40, 0.41, 0.40, 0.40], 2),
    ("SL7", "Large employer"): ([120, 116, 92, 60], [50, 48, 40, 28], [0.50, 0.50, 0.51, 0.49], 9),
    ("SL7", "SME"): ([70, 66, 44, 20], [30, 28, 18, 8], [0.40, 0.41, 0.39, 0.40], 2),
}


def _split(total: int, weights: dict[str, float], rng: random.Random) -> dict[str, int]:
    jittered = {k: w * (1 + rng.uniform(-0.03, 0.03)) for k, w in weights.items()}
    norm = sum(jittered.values())
    parts = {k: round(total * w / norm) for k, w in jittered.items()}
    drift = total - sum(parts.values())
    parts[max(parts, key=lambda k: parts[k])] += drift
    return parts


def main() -> None:
    rng = random.Random(20260930)  # noqa: S311 - deterministic synthetic data
    HERE.mkdir(exist_ok=True)

    with (HERE / "northstar_starts.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["year", "programme_code", "programme", "level", "region", "employer_segment", "starts"])
        for code, (name, level, _dur, starts) in PROGRAMMES.items():
            for year, total in zip(YEARS, starts, strict=True):
                for region, r_total in _split(total, REGIONS, rng).items():
                    for segment, n in _split(r_total, SEGMENTS, rng).items():
                        w.writerow([year, code, name, level, region, segment, n])

    with (HERE / "national_starts.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["year", "standard_code", "standard", "level", "starts"])
        for code, (name, level, starts) in NATIONAL.items():
            for year, n in zip(YEARS, starts, strict=True):
                w.writerow([year, code, name, level, n])

    with (HERE / "northstar_pipeline.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["year", "programme_code", "employer_segment", "enquiries", "proposals", "won"])
        for (code, segment), (enq, props, rates, _lpe) in FUNNEL.items():
            for i, year in enumerate(YEARS):
                w.writerow([year, code, segment, enq[i], props[i], round(props[i] * rates[i])])


if __name__ == "__main__":
    main()
