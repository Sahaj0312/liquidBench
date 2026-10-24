from collections import Counter
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from liquidbench.diagnostic import (
    CLARIFICATION,
    CONDITIONS,
    EXCLUDED,
    build_plan,
    context_message,
    execute_block,
    messages,
    reference_index,
    select_reference,
    select_tasks,
    treatment,
)
from liquidbench.runner import SYSTEM, load_config, run
from liquidbench.skills import SkillBundle, sha256
from liquidbench.task import discover_tasks, fingerprint
from test_runner import MemorySandbox, ScriptedProvider

ROOT = Path(__file__).resolve().parents[1]
SELECTED = [
    "announcement-subtitle",
    "customer-name",
    "eligibility-branch",
    "locale-references",
    "select-schema",
]


@pytest.fixture(scope="module")
def tasks():
    return discover_tasks(ROOT / "tasks/dev")


@pytest.fixture(scope="module")
def bundle():
    try:
        return SkillBundle.load(load_config(ROOT / "configs/m6-full.json")["skills"])
    except (OSError, ValueError) as exc:
        pytest.skip(f"Pinned skill checkout unavailable: {exc}")


def make_plan(tmp_path, tasks, bundle):
    config = load_config(ROOT / "configs/diagnostic-v1.json")
    index = reference_index(bundle)
    selections, measurements, controls = {}, {}, {}
    for task in tasks:
        task_id, prompt = task.manifest["id"], task.manifest["prompt"]
        if task_id not in SELECTED:
            continue
        selections[task_id] = select_reference(prompt, index)
        reference = context_message(bundle.documents[selections[task_id]["path"]])
        neutral = context_message(f"Neutral records for {task_id}.")
        path = tmp_path / f"{task_id}.txt"
        path.write_text(neutral)
        controls[task_id] = {"path": str(path), "sha256": sha256(neutral.encode())}
        content = {"reference": reference, "neutral": neutral}
        measurements[task_id] = {
            c: {
                "initial_tokens": 0,
                "messages_sha256": fingerprint(messages(prompt, c, content.get(c))),
            }
            for c in CONDITIONS
        }
    return build_plan(tasks, config, bundle, selections, measurements, controls)


def test_selection_is_balanced_public_and_order_independent(tasks):
    public = [{k: t.manifest[k] for k in ("id", "category", "difficulty")} for t in tasks]
    assert select_tasks(public) == SELECTED
    assert select_tasks(list(reversed(public))) == SELECTED
    by_id = {t.manifest["id"]: t.manifest for t in tasks}
    assert sorted(by_id[i]["difficulty"] for i in SELECTED) == [
        "easy",
        "easy",
        "hard",
        "medium",
        "medium",
    ]
    assert not set(SELECTED) & set(EXCLUDED)


def test_reference_index_ignores_fenced_headings():
    fake = SimpleNamespace(
        documents={
            "skills/x/references/a.md": "# Real\n```liquid\n# Fake\n```\n## `if` tag\n",
            "skills/x/SKILL.md": "# Entry\n",
        },
        manifest={
            "files": {
                "skills/x/references/a.md": {"bytes": 1, "sha256": "0"},
                "skills/x/SKILL.md": {"bytes": 1, "sha256": "0"},
            }
        },
    )
    index = reference_index(fake)
    assert list(index) == ["skills/x/references/a.md"]
    assert index["skills/x/references/a.md"]["headings"] == ["Real", "`if` tag"]
    assert index["skills/x/references/a.md"]["identifiers"] == ["if"]


def test_reference_routes_and_blocks_without_fallback(tasks, bundle):
    index = reference_index(bundle)
    expected = {
        "announcement-subtitle": "string-processing",
        "customer-name": "string-processing",
        "eligibility-branch": "conditional-control",
        "locale-references": "translation-reference",
        "select-schema": "schema-repair",
    }
    for task in tasks:
        if task.manifest["id"] in expected:
            choice = select_reference(task.manifest["prompt"], index)
            assert choice["rule"] == expected[task.manifest["id"]]
            assert choice["path"] in bundle.documents
    with pytest.raises(ValueError, match="Unrecognized"):
        select_reference("Write a haiku about storefronts.", index)
    with pytest.raises(ValueError, match="uniquely"):
        select_reference("Repair the schema.", {"a": {"headings": []}})
    with pytest.raises(ValueError, match="indexed platform operation"):
        select_reference("Repair the references in a file.", index)


def test_condition_messages_share_everything_but_treatment():
    prompt = "Repair snippets/x.liquid."
    original, clarified = messages(prompt, "original"), messages(prompt, "clarified")
    reference = messages(prompt, "reference", context_message("ref"))
    neutral = messages(prompt, "neutral", context_message("noise"))
    assert original[0]["content"] == SYSTEM
    assert {m[0]["content"] for m in (clarified, reference, neutral)} == {SYSTEM + CLARIFICATION}
    assert original[-1] == clarified[-1] == reference[-1] == neutral[-1]
    assert reference[1]["role"] == neutral[1]["role"] == "user"
    for condition, content in (("original", "x"), ("reference", None), ("unknown", None)):
        with pytest.raises(ValueError):
            messages(prompt, condition, content)


def test_order_is_complete_and_position_balanced(tmp_path, tasks, bundle):
    plan = make_plan(tmp_path, tasks, bundle)
    order = plan["order"]
    assert len(order) == 80
    assert set(
        Counter((r["repetition"], r["task_id"], r["condition"]) for r in order).values()
    ) == {1}
    assert set(Counter((r["task_id"], r["condition"], r["position"]) for r in order).values()) == {
        1
    }
    for block in range(20):
        selected = [r for r in order if r["block"] == block]
        assert len({r["task_id"] for r in selected}) == 1
        assert sorted(r["condition"] for r in selected) == sorted(CONDITIONS)
    assert plan["inference_performed"] is False
    assert plan == make_plan(tmp_path, list(reversed(tasks)), bundle)


def test_treatment_verifies_frozen_context(tmp_path, tasks, bundle):
    plan = make_plan(tmp_path, tasks, bundle)
    task = next(t for t in tasks if t.manifest["id"] == "select-schema")
    assert treatment(plan, task, "original") == {"system_appendix": "", "injected_context": None}
    ref = treatment(plan, task, "reference", bundle)["injected_context"]
    assert ref["metadata"]["path"].endswith("schema-and-settings.md")
    assert ref["content"] == context_message(bundle.documents[ref["metadata"]["path"]])
    with pytest.raises(ValueError, match="Pinned bundle"):
        treatment(plan, task, "reference")
    Path(plan["controls"]["select-schema"]["path"]).write_text("edited")
    with pytest.raises(ValueError, match="Neutral content changed"):
        treatment(plan, task, "neutral")
    changed = copy.deepcopy(plan)
    changed["measurements"]["select-schema"]["clarified"]["messages_sha256"] = "0"
    with pytest.raises(ValueError, match="differ from frozen plan"):
        treatment(changed, task, "clarified")
    other = next(t for t in tasks if t.manifest["id"] not in SELECTED)
    with pytest.raises(ValueError, match="Unknown"):
        treatment(plan, other, "original")


def run_delivery(tmp_path, task, **kwargs):
    config = {**load_config(ROOT / "configs/diagnostic-v1.json"), "max_turns": 1}
    provider = ScriptedProvider(['{"tool":"finish","args":{}}'])
    _, result = run(
        task,
        config,
        tmp_path,
        provider=provider,
        sandbox_factory=MemorySandbox,
        resolve_image=lambda _: "sha256:test",
        grader=lambda *_: {"passed": False, "checks": []},
        **kwargs,
    )
    return provider, result


def test_runner_delivers_exact_frozen_reference(tmp_path, tasks, bundle):
    plan = make_plan(tmp_path, tasks, bundle)
    for task in tasks:
        task_id = task.manifest["id"]
        if task_id not in SELECTED:
            continue
        for condition in CONDITIONS:
            kwargs = treatment(plan, task, condition, bundle)
            provider, result = run_delivery(tmp_path / task_id / condition, task, **kwargs)
            assert (
                result["initial_context_sha256"]
                == (plan["measurements"][task_id][condition]["messages_sha256"])
            )
            sent = json.loads(provider.contexts[0])
            if condition == "reference":
                path = plan["references"][task_id]["path"]
                assert sent[1]["content"] == context_message(bundle.documents[path])
                [access] = result["skill_accesses"]
                assert access["path"] == path and access["mode"] == "injected"
                assert access["message_sha256"] == sha256(sent[1]["content"].encode())
            else:
                assert result["skill_accesses"] == []
            assert len(result["context_exposures"]) == (condition == "neutral")


def test_runner_rejects_mixed_or_malformed_diagnostic_context(tmp_path, tasks, bundle):
    task = next(t for t in tasks if t.manifest["id"] == "select-schema")
    bad = {"content": "x", "metadata": {"kind": "other"}}
    _, result = run_delivery(tmp_path / "bad", task, injected_context=bad)
    assert result["status"] == "infrastructure_error"
    config = load_config(ROOT / "configs/diagnostic-v1.json")
    mixed = {**config, "skills": load_config(ROOT / "configs/m6-full.json")["skills"]}
    provider = ScriptedProvider(['{"tool":"finish","args":{}}'])
    _, result = run(
        task,
        mixed,
        tmp_path / "mixed",
        provider=provider,
        sandbox_factory=MemorySandbox,
        resolve_image=lambda _: "sha256:test",
        grader=lambda *_: {"passed": False, "checks": []},
        system_appendix=CLARIFICATION,
    )
    assert result["status"] == "infrastructure_error"
    assert provider.contexts == []


def test_block_runs_in_order_without_retry(tmp_path, tasks, bundle):
    plan = make_plan(tmp_path, tasks, bundle)
    calls = []

    def runner(task, config, destination, **kwargs):
        calls.append(destination.name)
        destination.mkdir(parents=True)
        status = "infrastructure_error" if len(calls) == 2 else "failed"
        return destination, {"status": status, "termination": "fixture"}

    with pytest.raises(ValueError):
        execute_block(plan, tasks, 20, tmp_path / "x", runner=runner, resolve_image=str)
    code = execute_block(
        plan,
        tasks,
        3,
        tmp_path / "b3",
        runner=runner,
        resolve_image=lambda _: plan["runtime_image_id"],
        bundle=bundle,
    )
    planned = [r["condition"] for r in plan["order"] if r["block"] == 3]
    summary = json.loads((tmp_path / "b3/summary.json").read_text())
    assert code == 2 and calls == planned[:2]
    assert summary["complete"] is False and len(summary["runs"]) == 2
    with pytest.raises(FileExistsError):
        execute_block(plan, tasks, 3, tmp_path / "b3", runner=runner, resolve_image=str)


def test_frozen_plan_counts_and_controls_are_consistent(tasks):
    plan = json.loads((ROOT / "experiments/diagnostic-v1-plan.json").read_text())
    m6 = json.loads((ROOT / "docs/calibration/milestone-6-feasibility.json").read_text())["tasks"]
    assert plan["selected_tasks"] == SELECTED and len(plan["order"]) == 80
    for task_id, counts in plan["measurements"].items():
        tokens = {c: counts[c]["initial_tokens"] for c in CONDITIONS}
        # Endpoint-verified Milestone 6 baseline counts use the identical system/task prompt.
        assert tokens["original"] == m6[task_id]["base"]["initial_tokens"]
        assert tokens["original"] < tokens["clarified"] < tokens["reference"]
        assert tokens["reference"] == tokens["neutral"]
        control = plan["controls"][task_id]
        assert sha256((ROOT / control["path"]).read_bytes()) == control["sha256"]
        assert control["message_tokens"] == plan["references"][task_id]["message_tokens"]
