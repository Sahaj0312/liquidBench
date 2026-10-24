import os
from pathlib import Path

import pytest

from liquidbench.grading import grade, validation_candidates
from liquidbench.sandbox import Sandbox, ToolError, docker, image_id
from liquidbench.task import Task

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("LIQUIDBENCH_INTEGRATION") != "1", reason="Set LIQUIDBENCH_INTEGRATION=1"
    ),
]
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def image():
    return image_id("liquidbench-runtime:0.1")


@pytest.mark.parametrize(
    "candidate",
    [
        "starter",
        "reference",
        "unescaped",
        "always_in_stock",
        "missing_fallback",
        "hardcoded",
        "suppressed",
        "grader_config",
    ],
)
def test_reference_and_mutants(image, candidate):
    task = Task.load(ROOT / "tasks/dev/product-card")
    files, expected = validation_candidates(task)[candidate]
    result = grade(task, files, image)
    assert result["passed"] == expected, result


def test_container_boundary(image):
    with Sandbox(image, {"test.txt": "hello"}) as sandbox:
        assert sandbox.call("read_file", {"path": "test.txt"}) == {"content": "hello"}
        for path in ["/etc/passwd", "../etc/passwd", "/opt/liquidbench/tool.py"]:
            with pytest.raises(ToolError):
                sandbox.call("read_file", {"path": path})
        config = docker("inspect", "--format", "{{json .HostConfig}}", sandbox.name)
        import json

        config = json.loads(config)
        assert config["NetworkMode"] == "none"
        assert config["ReadonlyRootfs"] is True
        assert config["CapDrop"] == ["ALL"]
        assert not config["Binds"]
        # Direct test-only exec verifies permissions beyond the model-facing tools.
        output = docker(
            "exec",
            sandbox.name,
            "python3",
            "-c",
            "from pathlib import Path; "
            'print(Path("/opt/liquidbench/evaluator").exists()); '
            'print(Path("/var/run/docker.sock").exists())',
        )
        assert output.splitlines() == ["False", "False"]
        docker("exec", sandbox.name, "ln", "-s", "/etc/passwd", "/workspace/link")
        with pytest.raises(ToolError):
            sandbox.call("read_file", {"path": "link"})
        with pytest.raises(ToolError):
            sandbox.snapshot()
    assert sandbox.name not in docker("ps", "-a", "--format", "{{.Names}}")


def test_strict_renderer_rejects_unknown_filters(image):
    with Sandbox(image, {"bad.liquid": "{{ product.title | invented_filter }}"}) as sandbox:
        result = sandbox.call(
            "render", {"path": "bad.liquid", "variables": {"product": {"title": "A"}}}
        )
        assert not result["ok"]
        assert "UndefinedFilter" in result["error"]


TASK_PATHS = sorted(
    [*(ROOT / "tasks/dev").glob("*/task.json"), *(ROOT / "tasks/heldout").glob("*/task.json")]
)
NEW_TASKS = [Task.load(path.parent) for path in TASK_PATHS if path.parent.name != "product-card"]
NEW_CANDIDATES = [(task, name) for task in NEW_TASKS for name in validation_candidates(task)]


@pytest.mark.parametrize(
    "task,candidate",
    NEW_CANDIDATES,
    ids=[f"{t.manifest['id']}/{name}" for t, name in NEW_CANDIDATES],
)
def test_new_task_references_and_adversarial_solutions(image, task, candidate):
    files, expected = validation_candidates(task)[candidate]
    result = grade(task, files, image)
    assert result["passed"] == expected, result


ALL_TASKS = [Task.load(path.parent) for path in TASK_PATHS]


@pytest.mark.parametrize("task", ALL_TASKS, ids=lambda t: t.manifest["id"])
def test_agent_container_contains_only_initial_workspace(image, task):
    with Sandbox(image, task.initial) as sandbox:
        assert sandbox.snapshot() == task.initial
        assert sandbox.call("list_files")["files"] == sorted(task.initial)
        for path in ["evaluator/cases.json", "evaluator/validation.json", "task.json"]:
            with pytest.raises(ToolError):
                sandbox.call("read_file", {"path": path})


@pytest.mark.parametrize("task", ALL_TASKS, ids=lambda t: t.manifest["id"])
def test_full_pipeline_with_reference_fixture_provider(image, task, tmp_path):
    # Synthetic integration evidence only; this is deliberately not a model score.
    import json
    from liquidbench.runner import load_config, run
    from test_runner import ScriptedProvider

    replies = [
        json.dumps({"tool": "write_file", "args": {"path": path, "content": content}})
        for path, content in task.reference_files.items()
        if task.initial[path] != content
    ]
    replies.append('{"tool":"finish","args":{}}')
    config = load_config(ROOT / "configs/local-smoke.json")
    config.update(image=image, purpose="synthetic reference-fixture integration test")
    destination, result = run(task, config, tmp_path, provider=ScriptedProvider(replies))
    assert result["status"] == "passed", result
    assert result["snapshot_captured"]
    assert (destination / "changes.patch").read_text()
    assert (destination / "trace.jsonl").exists()


def test_analysis_distinguishes_real_and_commented_schema(image):
    files = {
        "comment.liquid": "{% comment %}{% schema %}{}{% endschema %}{% endcomment %}",
        "valid.liquid": 'before{% schema %}{"name":"é"}{% endschema %}after',
        "nested.liquid": "{% if true %}{% schema %}{}{% endschema %}{% endif %}",
    }
    with Sandbox(image, files) as sandbox:
        assert sandbox.call("analyze", {"path": "comment.liquid"})["schemas"] == []
        parsed = sandbox.call("analyze", {"path": "valid.liquid"})
        assert parsed["body_source"] == "beforeafter"
        assert parsed["schemas"][0]["top_level"]
        assert not sandbox.call("analyze", {"path": "nested.liquid"})["schemas"][0]["top_level"]
        with pytest.raises(ToolError):
            sandbox.call(
                "render", {"path": "comment.liquid", "variables": {}, "strip_schema": True}
            )
        with pytest.raises(ToolError):
            sandbox.call("analyze", {"path": "../evaluator/cases.json"})


def test_schema_extraction_does_not_enable_shopify_filters(image):
    files = {"section.liquid": '{{ "file.css" | asset_url }}{% schema %}{}{% endschema %}'}
    with Sandbox(image, files) as sandbox:
        result = sandbox.call(
            "render", {"path": "section.liquid", "variables": {}, "strip_schema": True}
        )
        assert not result["ok"]
        assert "UndefinedFilter" in result["error"]


@pytest.mark.parametrize("loading", ["full", "on_demand"])
def test_skills_never_enter_agent_or_evaluator_container(image, skill_spec, tmp_path, loading):
    import json
    from liquidbench.runner import load_config, run
    from test_runner import ScriptedProvider

    task = Task.load(ROOT / "tasks/dev/product-card")
    config = load_config(ROOT / "configs/qwen-ab-skills.json")
    config.update(skills=skill_spec, image=image, skill_loading=loading)
    reference_path = "skills/language/references/long.md"
    provider = ScriptedProvider(
        [
            json.dumps({"tool": "read_file", "args": {"path": reference_path}}),
            json.dumps(
                {
                    "tool": "write_file",
                    "args": {
                        "path": "snippets/product-card.liquid",
                        "content": task.reference,
                    },
                }
            ),
            '{"tool":"check","args":{}}',
            '{"tool":"finish","args":{}}',
        ]
    )

    class InspectedSandbox(Sandbox):
        def __enter__(self):
            super().__enter__()
            assert self.snapshot() == task.initial
            with pytest.raises(ToolError):
                self.call("read_file", {"path": reference_path})
            return self

    def inspected_grade(task, files, image):
        assert set(files) == set(task.initial)
        return grade(task, files, image)

    _, result = run(
        task,
        config,
        tmp_path,
        provider=provider,
        sandbox_factory=InspectedSandbox,
        grader=inspected_grade,
    )
    assert result["status"] == "passed"
    assert "END_MARKER" in provider.contexts[1]
    assert result["tool_errors"] == 0
