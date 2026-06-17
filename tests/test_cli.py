"""CLI selector resolution: --parameter name/index translation to indices."""

from fluvilog.cli import resolve_parameters
from fluvilog.constants import PARAMETERS

_ALL = list(range(len(PARAMETERS)))


def test_absent_selectors_mean_all() -> None:
    assert resolve_parameters(None) == _ALL
    assert resolve_parameters([]) == _ALL


def test_name_resolves_case_insensitively() -> None:
    assert resolve_parameters(["pH-Wert"]) == [PARAMETERS.index("pH-Wert")]
    assert resolve_parameters(["ph-wert"]) == [PARAMETERS.index("pH-Wert")]


def test_numeric_index_passes_through() -> None:
    assert resolve_parameters(["1", "4"]) == [1, 4]


def test_selector_order_is_preserved() -> None:
    assert resolve_parameters(["4", "Trübung"]) == [4, PARAMETERS.index("Trübung")]


def test_unknown_selectors_are_dropped() -> None:
    # Out-of-range index and bogus name skipped; the valid one survives.
    assert resolve_parameters(["99", "bogus", "1"]) == [1]


def test_all_unknown_yields_empty() -> None:
    assert resolve_parameters(["bogus"]) == []
