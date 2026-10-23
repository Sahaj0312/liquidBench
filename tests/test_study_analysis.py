import importlib.util
import json
from pathlib import Path
import sys

import pytest

from liquidbench.task import fingerprint
from test_study import setup_plan

ROOT = Path(__file__).resolve().parents[1]
# Scripts are CLI siblings, not installed package modules.
spec = importlib.util.spec_from_file_location("analyze_runs", ROOT / "scripts/analyze_runs.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.modules["analyze_runs"] = module
spec = importlib.util.spec_from_file_location(
    "analyze_loading_study", ROOT / "scripts/analyze_loading_study.py"
)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def test_no_runs_explicit_missing_pairs(tmp_path, skill_spec):
    plan, _ = setup_plan(tmp_path, skill_spec)
    report = analysis.compare(plan, [])
    assert len(report["paired_outcomes"]) == 60
    assert all(counts == {"missing": 60} for counts in report["totals"].values())


def test_failed_grade_and_infrastructure_are_not_dropped(tmp_path, skill_spec):
    plan, _ = setup_plan(tmp_path, skill_spec)
    directory = tmp_path / "block"
    directory.mkdir()
    entries = [
        {
            **r,
            "artifacts": str(i),
            "status": "failed" if i == 0 else "infrastructure_error",
            "termination": "finished" if i == 0 else "infrastructure_error",
        }
        for i, r in enumerate(plan["order"][:2])
    ]
    summary = {"plan_sha256": fingerprint(plan), "runs": entries}
    (directory / "summary.json").write_text(json.dumps(summary))

    def reader(path):
        entry = entries[int(path.name)]
        return {
            **entry,
            "image_id": plan["runtime_image_id"],
            "config": {**plan["configs"][entry["condition"]], "image": plan["runtime_image_id"]},
            "source": {"python_source_digest": plan["python_source_digest"]},
            "skill_accesses": [],
            "context_exposures": [],
            **dict.fromkeys(
                (
                    "grade_passed",
                    "input_tokens",
                    "output_tokens",
                    "elapsed_seconds",
                    "model_calls",
                    "tool_errors",
                    "protocol_errors",
                    "length_stops",
                    "usage_incomplete",
                    "action_counts",
                    "sha256",
                ),
                None,
            ),
        }

    report = analysis.compare(plan, [directory], reader=reader)
    assert report["totals"]["base"] == {"failed": 1, "missing": 59}
    assert report["totals"]["full"] == {"infrastructure_error": 1, "missing": 59}
    with pytest.raises(ValueError, match="duplicate"):
        analysis.compare(plan, [directory, directory], reader=reader)
    summary["plan_sha256"] = "other"
    (directory / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(ValueError, match="Mixed"):
        analysis.compare(plan, [directory], reader=reader)


def test_grouped_win_tie_loss_uses_status_and_preserves_missingness():
    cases = [
        ("passed", "failed", "rendering", "easy"),
        ("failed", "passed", "rendering", "easy"),
        ("passed", "passed", "section-schema", "hard"),
        ("failed", "failed", "section-schema", "hard"),
        ("missing", "failed", "rendering", "medium"),
        ("infrastructure_error", "passed", "section-schema", "hard"),
        ("infrastructure_error", "missing", "section-schema", "hard"),
    ]
    pairs = []
    for i, (left, right, category, difficulty) in enumerate(cases):
        conditions = {
            c: {"status": "failed", "grade_passed": True}
            for c in ("base", "full", "on_demand", "neutral")
        }
        conditions["full"]["status"], conditions["base"]["status"] = left, right
        pairs.append(
            {
                "repetition": 1,
                "task_id": str(i),
                "category": category,
                "domain": analysis.DOMAINS[category],
                "difficulty": difficulty,
                "conditions": conditions,
            }
        )
    counts = analysis.paired_counts(pairs)[0]["by_repetition"][0]
    assert counts["overall"] == {
        "planned_pairs": 7,
        "comparable_pairs": 4,
        "wins": 1,
        "ties": 2,
        "losses": 1,
        "ties_passed": 1,
        "ties_failed": 1,
        "missing_pairs": 2,
        "infrastructure_pairs": 1,
    }
    assert counts["by_category"]["rendering"]["wins"] == 1
    assert counts["by_difficulty"]["hard"]["ties"] == 2
    for field in counts["overall"]:
        assert (
            sum(g[field] for g in counts["by_category_and_difficulty"]) == counts["overall"][field]
        )
    pairs.append({**pairs[0], "repetition": 2})
    report = analysis.paired_counts(pairs)[0]["by_repetition"]
    assert len(report) == 2 and report[1]["overall"]["planned_pairs"] == 1


def test_grouping_retains_frozen_manifest_labels(tmp_path, skill_spec):
    plan, _ = setup_plan(tmp_path, skill_spec)
    metadata = analysis.task_metadata(plan)
    assert metadata["announcement-subtitle"] == {
        "category": "section-modification",
        "difficulty": "easy",
        "domain": "theme-modification",
    }
    assert metadata["blocks-schema"]["difficulty"] == "hard"
    assert len(metadata) == 20
    report = analysis.compare(plan, [])
    assert len(report["paired_win_tie_loss"]) == 6
    assert report["paired_win_tie_loss"][0]["by_repetition"][0]["overall"]["missing_pairs"] == 20
    plan["order"][0]["task_digest"] = "tampered"
    # Every row for the same task must have the same digest in a frozen plan.
    for row in plan["order"]:
        if row["task_id"] == plan["order"][0]["task_id"]:
            row["task_digest"] = "tampered"
    with pytest.raises(ValueError, match="metadata differs"):
        analysis.task_metadata(plan)
