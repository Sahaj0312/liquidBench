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
