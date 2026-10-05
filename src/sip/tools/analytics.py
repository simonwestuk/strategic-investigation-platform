"""Deterministic analytical operations.

Each operation returns an ``AnalysisResult`` with a human-readable summary, a small table, and a list
of ``Pattern``s: generic, coded observations ("own_underperforms_market" for entity DTS6, ...). The
driver taxonomy maps pattern codes to hypothesis categories, so neither this module nor the taxonomy
knows anything about a particular industry.

Thresholds are explicit module constants so reviewers can see (and challenge) them.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from pydantic import BaseModel, Field

from sip.tools.datasets import Dataset, DatasetCatalog, DatasetRole

MATERIAL_CHANGE = 0.10  # 10% change in a measure is "material"
SHARE_GAP_PP = 10.0  # own vs market growth gap (percentage points) that indicates share movement
CONVERSION_GAP_PP = 8.0  # change in final-stage conversion (pp) that is material
GROUP_GAP_PP = 8.0  # difference-in-change between groups (pp) that is material
EMERGING_GROWTH = 0.5  # +50% (or from zero) marks an emerging market entity


class Pattern(BaseModel):
    code: str
    statement: str
    entity: str | None = None  # entity key value (e.g. a product code)
    dimension: str | None = None
    value: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    operation: str
    dataset_ids: list[str]
    params: dict[str, Any]
    summary: str
    table: list[dict[str, Any]]
    patterns: list[Pattern]


class AnalysisError(ValueError):
    pass


def _pct(a: float, b: float) -> float | None:
    return None if a == 0 else (b - a) / a


def _fmt_pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:+.0f}%"


def _sum_by(
    ds: Dataset, measure: str, keys: Iterable[str], where: dict[str, str] | None = None
) -> dict[tuple[str, ...], float]:
    keys = list(keys)
    out: dict[tuple[str, ...], float] = defaultdict(float)
    for r in ds.rows:
        if where and any(r.get(k) != v for k, v in where.items()):
            continue
        out[tuple(r[k] for k in keys)] += float(r[measure])
    return dict(out)


def _require(ds: Dataset | None, role: DatasetRole) -> Dataset:
    if ds is None:
        raise AnalysisError(f"No dataset with role '{role.value}' is available.")
    return ds


# ------------------------------------------------------------------------------------------------
def trend(
    catalog: DatasetCatalog, dataset_id: str, by: str | None = None, where: dict[str, str] | None = None
) -> AnalysisResult:
    ds = catalog.get(dataset_id)
    m = ds.manifest
    if not m.measure:
        raise AnalysisError("trend requires a dataset with a measure")
    periods = ds.periods
    first, last = periods[0], periods[-1]
    keys = [m.period] + ([by] if by else [])
    sums = _sum_by(ds, m.measure, keys, where)
    groups = sorted({k[1] for k in sums}) if by else [None]
    table, patterns = [], []
    for g in groups:
        series = [sums.get((p, g) if g else (p,), 0.0) for p in periods]
        change = _pct(series[0], series[-1])
        row = {"group": g or "total", **{p: series[i] for i, p in enumerate(periods)}, "change": change}
        table.append(row)
        label = g or "total"
        if change is not None and change <= -MATERIAL_CHANGE:
            code = "decline"
        elif change is not None and change >= MATERIAL_CHANGE:
            code = "growth"
        else:
            code = "stable"
        patterns.append(
            Pattern(
                code=code,
                entity=g if by == m.entity_key else None,
                dimension=by,
                value=g,
                statement=f"{m.title}: {label} {m.measure} went from {series[0]:,.0f} in {first} to "
                f"{series[-1]:,.0f} in {last} ({_fmt_pct(change)}).",
                metrics={"first": series[0], "last": series[-1], "change_pct": round((change or 0) * 100, 1)},
            )
        )
    total = next((p for p in patterns if p.value is None), patterns[0])
    return AnalysisResult(
        operation="trend",
        dataset_ids=[dataset_id],
        params={"by": by, "where": where or {}},
        summary=total.statement if not by else f"Trend of {m.measure} by {by}, {first}–{last}.",
        table=table,
        patterns=patterns,
    )


def decompose_change(catalog: DatasetCatalog, dataset_id: str, by: str) -> AnalysisResult:
    ds = catalog.get(dataset_id)
    m = ds.manifest
    assert m.measure
    periods = ds.periods
    first, last = periods[0], periods[-1]
    sums = _sum_by(ds, m.measure, [m.period, by])
    groups = sorted({k[1] for k in sums})
    total_change = sum(sums.get((last, g), 0) - sums.get((first, g), 0) for g in groups)
    table, patterns = [], []
    names = ds.entity_names() if by == m.entity_key else {}
    for g in groups:
        delta = sums.get((last, g), 0) - sums.get((first, g), 0)
        share = delta / total_change if total_change else 0.0
        table.append({"group": g, "change": delta, "share_of_total_change": round(share, 3)})
        if total_change < 0 and share >= 0.25:
            patterns.append(
                Pattern(
                    code="major_contributor_to_decline",
                    entity=g if by == m.entity_key else None,
                    dimension=by,
                    value=g,
                    statement=f"{names.get(g, g)} accounts for {share * 100:.0f}% of the total change in "
                    f"{m.measure} ({delta:+,.0f} of {total_change:+,.0f}) between {first} and {last}.",
                    metrics={"delta": delta, "share_of_change_pct": round(share * 100, 1)},
                )
            )
    summary = (
        f"Total {m.measure} changed by {total_change:+,.0f} between {first} and {last}; "
        + "; ".join(f"{names.get(str(r['group']), r['group'])} {r['change']:+,.0f}" for r in table)
        + "."
    )
    return AnalysisResult(
        operation="decompose_change",
        dataset_ids=[dataset_id],
        params={"by": by},
        summary=summary,
        table=table,
        patterns=patterns,
    )


def own_vs_market(catalog: DatasetCatalog) -> AnalysisResult:
    own = _require(catalog.by_role(DatasetRole.OWN_VOLUME), DatasetRole.OWN_VOLUME)
    market = _require(catalog.by_role(DatasetRole.MARKET_VOLUME), DatasetRole.MARKET_VOLUME)
    om, mm = own.manifest, market.manifest
    assert om.measure and mm.measure and om.entity_key and mm.entity_key
    periods = [p for p in own.periods if p in set(market.periods)]
    if len(periods) < 2:
        raise AnalysisError("own and market datasets share fewer than two periods")
    first, last = periods[0], periods[-1]
    o = _sum_by(own, om.measure, [om.period, om.entity_key])
    mk = _sum_by(market, mm.measure, [mm.period, mm.entity_key])
    names = {**market.entity_names(), **own.entity_names()}
    own_entities = {k[1] for k in o}
    table, patterns = [], []
    for ent in sorted({k[1] for k in mk}):
        m0, m1 = mk.get((first, ent), 0), mk.get((last, ent), 0)
        mchg = _pct(m0, m1)
        name = names.get(ent, ent)
        if ent not in own_entities:
            if m1 > 0 and (m0 == 0 or (mchg is not None and mchg >= EMERGING_GROWTH)):
                patterns.append(
                    Pattern(
                        code="emerging_market_segment_not_offered",
                        entity=ent,
                        statement=f"The market for {name} grew from {m0:,.0f} to {m1:,.0f} between {first} and "
                        f"{last}; the organisation does not offer {name}.",
                        metrics={"market_first": m0, "market_last": m1},
                    )
                )
            table.append(
                {
                    "entity": ent,
                    "name": name,
                    "market_first": m0,
                    "market_last": m1,
                    "market_change": mchg,
                    "offered": False,
                }
            )
            continue
        o0, o1 = o.get((first, ent), 0), o.get((last, ent), 0)
        ochg = _pct(o0, o1)
        s0 = o0 / m0 if m0 else None
        s1 = o1 / m1 if m1 else None
        gap = None if ochg is None or mchg is None else (ochg - mchg) * 100
        table.append(
            {
                "entity": ent,
                "name": name,
                "own_first": o0,
                "own_last": o1,
                "own_change": ochg,
                "market_first": m0,
                "market_last": m1,
                "market_change": mchg,
                "share_first": s0,
                "share_last": s1,
                "gap_pp": gap,
                "offered": True,
            }
        )
        metrics = {
            "own_first": o0,
            "own_last": o1,
            "market_first": m0,
            "market_last": m1,
            "own_change_pct": round((ochg or 0) * 100, 1),
            "market_change_pct": round((mchg or 0) * 100, 1),
        }
        if s0 is not None and s1 is not None:
            metrics |= {"share_first_pct": round(s0 * 100, 1), "share_last_pct": round(s1 * 100, 1)}
        base = (
            f"{name}: own {om.measure} {o0:,.0f}→{o1:,.0f} ({_fmt_pct(ochg)}) vs market "
            f"{m0:,.0f}→{m1:,.0f} ({_fmt_pct(mchg)}), {first}–{last}"
        )
        share_txt = f"; share {s0 * 100:.1f}%→{s1 * 100:.1f}%" if s0 is not None and s1 is not None else ""
        if mchg is not None and mchg <= -MATERIAL_CHANGE:
            patterns.append(
                Pattern(
                    code="market_decline",
                    entity=ent,
                    metrics=metrics,
                    statement=f"{base}: the market itself declined{share_txt}.",
                )
            )
        elif mchg is not None and mchg >= 0.03:
            patterns.append(
                Pattern(
                    code="market_growth", entity=ent, metrics=metrics, statement=f"{base}: the market grew{share_txt}."
                )
            )
        else:
            patterns.append(
                Pattern(
                    code="market_stable",
                    entity=ent,
                    metrics=metrics,
                    statement=f"{base}: the market was broadly stable{share_txt}.",
                )
            )
        if gap is not None and gap <= -SHARE_GAP_PP:
            patterns.append(
                Pattern(
                    code="own_underperforms_market",
                    entity=ent,
                    metrics=metrics,
                    statement=f"{base}: the organisation under-performed the market by "
                    f"{abs(gap):.0f} percentage points{share_txt}.",
                )
            )
        elif gap is not None and gap >= SHARE_GAP_PP:
            patterns.append(
                Pattern(
                    code="own_outperforms_market",
                    entity=ent,
                    metrics=metrics,
                    statement=f"{base}: the organisation out-performed the market by "
                    f"{gap:.0f} percentage points{share_txt}.",
                )
            )
        else:
            patterns.append(
                Pattern(
                    code="own_tracks_market",
                    entity=ent,
                    metrics=metrics,
                    statement=f"{base}: the organisation moved in line with the market{share_txt}.",
                )
            )
    return AnalysisResult(
        operation="own_vs_market",
        dataset_ids=[om.id, mm.id],
        params={},
        summary=f"Own vs market comparison by {om.entity_key}, {first}–{last}.",
        table=table,
        patterns=patterns,
    )


def funnel_conversion(catalog: DatasetCatalog, by: str | None = None) -> AnalysisResult:
    ds = _require(catalog.by_role(DatasetRole.FUNNEL), DatasetRole.FUNNEL)
    m = ds.manifest
    if len(m.stages) < 2:
        raise AnalysisError("funnel requires at least two stages")
    periods = ds.periods
    first, last = periods[0], periods[-1]
    top, penult, final = m.stages[0], m.stages[-2], m.stages[-1]
    keys: list[str] = [k for k in [m.entity_key, by if by != m.entity_key else None] if k]
    names = {}
    own = catalog.by_role(DatasetRole.OWN_VOLUME)
    if own:
        names = own.entity_names()
    groups: dict[tuple[str, ...], dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for r in ds.rows:
        g = tuple(r[k] for k in keys)
        for s in m.stages:
            groups[g][r[m.period]][s] = groups[g][r[m.period]].get(s, 0) + float(r[s])
    table, patterns = [], []
    for g, per in sorted(groups.items()):
        label = " / ".join(names.get(x, x) for x in g)
        c0 = per[first][final] / per[first][penult] if per[first][penult] else 0
        c1 = per[last][final] / per[last][penult] if per[last][penult] else 0
        t0, t1 = per[first][top], per[last][top]
        tchg = _pct(t0, t1)
        dpp = (c1 - c0) * 100
        table.append(
            {
                "group": label,
                f"{penult}_to_{final}_{first}": round(c0, 3),
                f"{penult}_to_{final}_{last}": round(c1, 3),
                "conversion_change_pp": round(dpp, 1),
                f"{top}_change": tchg,
            }
        )
        ent = g[0] if keys and keys[0] == m.entity_key else None
        seg_dim = keys[1] if len(keys) > 1 else None
        seg_val = g[1] if len(g) > 1 else None
        metrics = {
            "conversion_first_pct": round(c0 * 100, 1),
            "conversion_last_pct": round(c1 * 100, 1),
            "conversion_change_pp": round(dpp, 1),
            "top_first": t0,
            "top_last": t1,
        }
        conv_txt = (
            f"{label}: {penult}→{final} conversion went from {c0 * 100:.0f}% in {first} to "
            f"{c1 * 100:.0f}% in {last} ({dpp:+.0f} pp)"
        )
        if dpp <= -CONVERSION_GAP_PP:
            patterns.append(
                Pattern(
                    code="conversion_decline",
                    entity=ent,
                    dimension=seg_dim,
                    value=seg_val,
                    metrics=metrics,
                    statement=conv_txt + ".",
                )
            )
        else:
            patterns.append(
                Pattern(
                    code="conversion_stable",
                    entity=ent,
                    dimension=seg_dim,
                    value=seg_val,
                    metrics=metrics,
                    statement=conv_txt + ", which is not a material change.",
                )
            )
        if tchg is not None and tchg <= -0.15:
            patterns.append(
                Pattern(
                    code="top_of_funnel_decline",
                    entity=ent,
                    dimension=seg_dim,
                    value=seg_val,
                    metrics=metrics,
                    statement=f"{label}: {top} fell from {t0:,.0f} to {t1:,.0f} ({_fmt_pct(tchg)}).",
                )
            )
    return AnalysisResult(
        operation="funnel_conversion",
        dataset_ids=[m.id],
        params={"by": by},
        summary=f"Funnel conversion ({penult}→{final}) by {', '.join(keys)}, {first}–{last}.",
        table=table,
        patterns=patterns,
    )


def compare_groups(
    catalog: DatasetCatalog, dimension: str, group: str, dataset_id: str | None = None, entity: str | None = None
) -> AnalysisResult:
    """Difference-in-change test: did the measure change differently in `group` than elsewhere?

    Used by the challenger to test claims that an event affecting one group (a region, a segment)
    caused the decline. If the change is similar everywhere, the group-specific event is unlikely to
    be the cause.
    """
    ds = catalog.get(dataset_id) if dataset_id else catalog.by_role(DatasetRole.OWN_VOLUME)
    ds = _require(ds, DatasetRole.OWN_VOLUME)
    m = ds.manifest
    assert m.measure
    if dimension not in m.dimensions:
        raise AnalysisError(f"dataset {m.id} has no dimension '{dimension}'")
    if group not in ds.values(dimension):
        raise AnalysisError(f"'{group}' is not a value of {dimension}")
    periods = ds.periods
    first, last = periods[0], periods[-1]
    where = {m.entity_key: entity} if entity and m.entity_key else None
    sums = _sum_by(ds, m.measure, [m.period, dimension], where)
    g0, g1 = sums.get((first, group), 0), sums.get((last, group), 0)
    r0 = sum(v for (p, d), v in sums.items() if p == first and d != group)
    r1 = sum(v for (p, d), v in sums.items() if p == last and d != group)
    gc, rc = _pct(g0, g1), _pct(r0, r1)
    diff = None if gc is None or rc is None else (gc - rc) * 100
    scope = f" for {ds.entity_names().get(entity, entity)}" if entity else ""
    metrics = {
        "group_change_pct": round((gc or 0) * 100, 1),
        "rest_change_pct": round((rc or 0) * 100, 1),
        "difference_pp": round(diff or 0, 1),
    }
    stmt = (
        f"{m.measure.capitalize()}{scope} changed by {_fmt_pct(gc)} in {dimension} '{group}' and by "
        f"{_fmt_pct(rc)} in all other {dimension} values between {first} and {last}"
    )
    target = entity or (group if dimension == m.entity_key else None)
    if diff is not None and abs(diff) < GROUP_GAP_PP:
        pattern = Pattern(
            code="no_group_difference",
            dimension=dimension,
            value=group,
            entity=target,
            metrics=metrics,
            statement=stmt + f" — a difference of {abs(diff):.0f} pp, so a factor specific to "
            f"'{group}' does not explain the change.",
        )
    else:
        pattern = Pattern(
            code="group_difference",
            dimension=dimension,
            value=group,
            entity=target,
            metrics=metrics,
            statement=stmt + f" — a difference of {diff or 0:+.0f} pp.",
        )
    return AnalysisResult(
        operation="compare_groups",
        dataset_ids=[m.id],
        params={"dimension": dimension, "group": group, "entity": entity},
        summary=pattern.statement,
        table=[{"group": group, "change": gc}, {"group": "rest", "change": rc}],
        patterns=[pattern],
    )


OPERATIONS: dict[str, Callable[..., AnalysisResult]] = {
    "trend": trend,
    "decompose_change": decompose_change,
    "own_vs_market": own_vs_market,
    "funnel_conversion": funnel_conversion,
    "compare_groups": compare_groups,
}

# Which dataset roles each operation needs (used by planners to detect unavailable evidence).
OPERATION_ROLES: dict[str, list[DatasetRole]] = {
    "trend": [DatasetRole.OWN_VOLUME],
    "decompose_change": [DatasetRole.OWN_VOLUME],
    "own_vs_market": [DatasetRole.OWN_VOLUME, DatasetRole.MARKET_VOLUME],
    "funnel_conversion": [DatasetRole.FUNNEL],
    "compare_groups": [DatasetRole.OWN_VOLUME],
}


def run_operation(
    catalog: DatasetCatalog, operation: str, dataset_id: str | None, params: dict[str, Any]
) -> AnalysisResult:
    if operation not in OPERATIONS:
        raise AnalysisError(f"Unknown operation '{operation}'. Allowed: {sorted(OPERATIONS)}")
    fn = OPERATIONS[operation]
    allowed = set(fn.__code__.co_varnames[1 : fn.__code__.co_argcount])
    clean = {k: v for k, v in params.items() if k in allowed}
    if "dataset_id" in allowed and dataset_id:
        clean["dataset_id"] = dataset_id
    try:
        return fn(catalog, **clean)
    except (KeyError, TypeError) as exc:
        raise AnalysisError(f"Invalid parameters for {operation}: {exc}") from exc
