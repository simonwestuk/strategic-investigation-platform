import pytest

from sip.scenarios.loader import Scenario
from sip.tools.analytics import (
    AnalysisError,
    compare_groups,
    decompose_change,
    funnel_conversion,
    own_vs_market,
    run_operation,
)
from sip.tools.datasets import Dataset, DatasetCatalog


@pytest.fixture(scope="module")
def catalog(northstar: Scenario) -> DatasetCatalog:
    return DatasetCatalog([Dataset.from_csv(m, northstar.path(m.file).read_text()) for m in northstar.datasets])


def codes(result, entity=None):  # type: ignore[no-untyped-def]
    return {p.code for p in result.patterns if entity is None or p.entity == entity}


def test_own_vs_market_separates_share_loss_from_market_decline(catalog: DatasetCatalog) -> None:
    r = own_vs_market(catalog)
    assert {"market_growth", "own_underperforms_market"} <= codes(r, "DTS6")
    assert {"market_decline", "own_tracks_market"} <= codes(r, "SL7")
    assert "emerging_market_segment_not_offered" in codes(r, "AIE6")


def test_decomposition_and_funnel(catalog: DatasetCatalog) -> None:
    d = decompose_change(catalog, "northstar_starts", "programme_code")
    assert {p.entity for p in d.patterns} == {"DTS6", "SL7"}
    f = funnel_conversion(catalog, by="employer_segment")
    decline = [p for p in f.patterns if p.code == "conversion_decline"]
    assert [(p.entity, p.value) for p in decline] == [("DTS6", "Large employer")]


def test_difference_in_change_rejects_regional_explanation(catalog: DatasetCatalog) -> None:
    r = compare_groups(catalog, dimension="region", group="North")
    assert r.patterns[0].code == "no_group_difference"
    r2 = compare_groups(catalog, dimension="programme_code", group="SL7")
    assert r2.patterns[0].code == "group_difference" and r2.patterns[0].entity == "SL7"


def test_operations_validate_inputs(catalog: DatasetCatalog) -> None:
    with pytest.raises(AnalysisError):
        run_operation(catalog, "drop_table", None, {})
    with pytest.raises(AnalysisError):
        run_operation(catalog, "compare_groups", None, {"dimension": "region", "group": "Atlantis"})


def test_entity_mentions_resolve_aliases_and_levels(catalog: DatasetCatalog) -> None:
    ents, dims = catalog.resolve_mentions("DTS wins in the North fell; Level 7 funding changed for Senior Leader")
    assert {"DTS6", "SL7"} <= ents and ("region", "North") in dims
