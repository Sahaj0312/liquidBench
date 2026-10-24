import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_heldout import clopper_pearson, compare, mcnemar_p  # noqa: E402


def test_exact_mcnemar_matches_known_values():
    assert mcnemar_p(3, 1) == pytest.approx(0.625)
    assert mcnemar_p(6, 0) == pytest.approx(0.03125)
    assert mcnemar_p(5, 0) == pytest.approx(0.0625)
    assert mcnemar_p(0, 0) == 1.0


def test_clopper_pearson_matches_reference_values():
    lo, hi = clopper_pearson(5, 10)
    assert lo == pytest.approx(0.1871, abs=1e-4) and hi == pytest.approx(0.8129, abs=1e-4)
    assert clopper_pearson(0, 10)[0] == 0.0 and clopper_pearson(10, 10)[1] == 1.0


def test_paired_comparison_counts_discordant_tasks():
    outcomes = {
        "tuned": {"a": True, "b": True, "c": False, "d": True},
        "base": {"a": True, "b": False, "c": True, "d": False},
    }
    result = compare(outcomes, "tuned", "base", ["a", "b", "c", "d"])
    assert (result["treated_only"], result["control_only"]) == (2, 1)
    assert result["difference"] == pytest.approx(0.25)
    lo, hi = result["interval95"]
    assert lo < result["difference"] < hi
