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
