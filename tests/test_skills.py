"""Synthetic skill content only: upstream redistribution is not required by CI."""

import json
from pathlib import Path

import pytest

from liquidbench.provider import Completion
from liquidbench.runner import SYSTEM, load_config, run
from liquidbench.skills import SkillBundle, initial_messages
from liquidbench.task import Task
from test_runner import MemorySandbox, ScriptedProvider

ROOT = Path(__file__).resolve().parents[1]


def execute(tmp_path, spec, replies, **overrides):
    config = load_config(ROOT / "configs/qwen-ab-base.json")
    config.update(skills=spec, **overrides)
    provider = ScriptedProvider(replies)
    seen = []

    def grade(task, files, image):
        seen.append(dict(files))
        return {"passed": True}

    destination, result = run(
        Task.load(ROOT / "tasks/dev/product-card"),
        config,
        tmp_path / "runs",
        provider=provider,
        sandbox_factory=MemorySandbox,
        grader=grade,
        resolve_image=lambda _: "sha256:synthetic",
    )
    return provider, destination, result, seen


def test_all_entries_preserve_original_bytes_and_references_are_lazy(skill_spec):
    bundle = SkillBundle.load(skill_spec)
    messages = initial_messages(SYSTEM, "unchanged task", bundle)
    assert messages[0] == {"role": "system", "content": SYSTEM}
    assert messages[-1] == {"role": "user", "content": "unchanged task"}
    for name in bundle.manifest["entries"]:
        assert bundle.documents[name] in messages[1]["content"]
    assert "END_MARKER" not in messages[1]["content"]
    assert "skills/language/references/long.md" in messages[1]["content"]


@pytest.mark.parametrize(
    "mutation",
    [
        "modified",
        "missing",
        "omitted",
        "wrong_revision",
        "symlink",
        "parent_symlink",
        "duplicate_entry",
    ],
)
def test_pin_and_inventory_fail_closed(skill_spec, mutation, tmp_path):
    manifest_path = Path(skill_spec["manifest"])
    manifest = json.loads(manifest_path.read_text())
    name = manifest["entries"][0]
    path = Path(skill_spec["checkout"]) / name
    if mutation == "modified":
        path.write_text("different bytes")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "omitted":
        del manifest["files"]["skills/language/references/long.md"]
    elif mutation == "wrong_revision":
        skill_spec["revision"] = "a" * 40
        manifest["revision"] = "a" * 40
    elif mutation == "symlink":
        saved = path.read_bytes()
        path.unlink()
        target = tmp_path / "external.md"
        target.write_bytes(saved)
        path.symlink_to(target)
    elif mutation == "parent_symlink":
        parent = path.parent
        external = tmp_path / "external-directory"
        parent.rename(external)
        parent.symlink_to(external, target_is_directory=True)
    else:
        manifest["entries"][1] = name
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises((ValueError, OSError)):
        SkillBundle.load(skill_spec)


def test_full_reference_read_is_logged_not_truncated_or_graded(skill_spec, tmp_path):
    name = "skills/language/references/long.md"
    provider, directory, result, seen = execute(
        tmp_path,
        skill_spec,
        [
            json.dumps({"tool": "read_file", "args": {"path": name}}),
            '{"tool":"finish","args":{}}',
        ],
    )
    assert result["status"] == "passed"
    assert "END_MARKER" in provider.contexts[1]
    assert "truncated" not in provider.contexts[1]
    assert [a["mode"] for a in result["skill_accesses"]] == ["injected"] * 3 + ["read_file"]
    assert result["skill_accesses"][-1]["path"] == name
    assert result["skill_accesses"][-1]["first_model_turn"] == 1
    assert result["skills"]["revision"] == skill_spec["revision"]
    assert result["input_tokens"] == 200  # All repeated context is charged by provider usage.
    assert all(not name.startswith("skills/") for name in seen[0])
    assert not (directory / "final/skills").exists()
    assert "skill_access" in (directory / "trace.jsonl").read_text()


def test_baseline_does_not_load_or_expose_checkout(skill_spec, tmp_path, monkeypatch):
    def forbidden(*args):
        pytest.fail("Baseline must not load the skill checkout")

    monkeypatch.setattr(SkillBundle, "load", forbidden)
    provider, _, result, _ = execute(
        tmp_path,
        None,
        [
            '{"tool":"read_file","args":{"path":"skills/language/SKILL.md"}}',
            '{"tool":"finish","args":{}}',
        ],
    )
    assert "Unmodified entry" not in "".join(provider.contexts)
    assert "END_MARKER" not in "".join(provider.contexts)
    assert "unavailable" in provider.contexts[1]
    assert result["tool_errors"] == 1
    assert result["skills"] is None and result["skill_accesses"] == []


@pytest.mark.parametrize(
    "tool,path",
    [
        ("write_file", "skills/language/SKILL.md"),
        ("analyze", "skills/language/SKILL.md"),
        ("read_file", "skills/../secret"),
        ("read_file", "/skills/language/SKILL.md"),
        ("read_file", "skills/language/references/missing.md"),
    ],
)
def test_skill_namespace_is_read_only_exact_allowlist(skill_spec, tmp_path, tool, path):
    args = {"path": path}
    if tool == "write_file":
        args["content"] = "tamper"
    _, _, result, _ = execute(
        tmp_path,
        skill_spec,
        [
            json.dumps({"tool": tool, "args": args}),
            '{"tool":"finish","args":{}}',
        ],
    )
    assert result["tool_errors"] == 1
    assert len(result["skill_accesses"]) == 3
    SkillBundle.load(skill_spec)  # Original bytes remain intact.


def test_invalid_bundle_stops_before_container_or_model(skill_spec, tmp_path, monkeypatch):
    Path(skill_spec["checkout"], "skills/language/SKILL.md").write_text("tampered")
    provider, _, result, seen = execute(tmp_path, skill_spec, [])
    assert result["status"] == "infrastructure_error"
    assert "verification failed" in result["error"]
    assert "image_id" not in result and not seen and not provider.contexts


def test_modified_content_cannot_be_relabelled_as_original_revision(skill_spec):
    from liquidbench.skills import sha256

    path = Path(skill_spec["checkout"], "skills/language/SKILL.md")
    path.write_text("altered content")
    lock = Path(skill_spec["manifest"])
    manifest = json.loads(lock.read_text())
    manifest["files"]["skills/language/SKILL.md"] = {
        "bytes": path.stat().st_size,
        "sha256": sha256(path.read_bytes()),
    }
    lock.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="pinned Git object"):
        SkillBundle.load(skill_spec)


def test_same_configs_except_skill_availability():
    base = load_config(ROOT / "configs/qwen-ab-base.json")
    treatment = load_config(ROOT / "configs/qwen-ab-skills.json")
    assert base.pop("skills") is None
    assert treatment.pop("skills")["revision"] == "483f969bed623c87c9e26ac34324d8d7d8fe68c3"
    assert base == treatment
    assert load_config(ROOT / "configs/qwen-base.json")["max_context_tokens"] == 8192


def test_skill_text_counts_against_context_and_total_budget(skill_spec, tmp_path, monkeypatch):
    class CountingProvider(ScriptedProvider):
        def count_prompt(self, messages, timeout):
            # Synthetic measured counts with a large reference; no free side channel.
            return 4000 if "END_MARKER" in json.dumps(messages) else 1000

        def complete(self, messages, max_tokens, timeout):
            reply = super().complete(messages, max_tokens, timeout)
            return Completion(reply.content, self.count_prompt(messages, timeout), 20, {})

    monkeypatch.setattr("test_skills.ScriptedProvider", CountingProvider)
    read = '{"tool":"read_file","args":{"path":"skills/language/references/long.md"}}'
    provider, _, result, _ = execute(tmp_path, skill_spec, [read], max_context_tokens=4096)
    assert result["termination"] == "context_budget"
    assert len(provider.contexts) == 1 and result["input_tokens"] == 1000
    assert result["skill_accesses"][-1]["first_model_turn"] is None
    provider, _, result, _ = execute(tmp_path, skill_spec, [read], max_total_tokens=4500)
    assert result["termination"] == "token_budget"
    assert len(provider.contexts) == 1


def test_list_and_search_have_explicit_document_scope(skill_spec, tmp_path, monkeypatch):
    class ListingSandbox(MemorySandbox):
        def call(self, tool, args):
            if tool == "list_files":
                return {"files": sorted(self.files)}
            if tool == "search":
                return {"matches": [], "truncated": False}
            return super().call(tool, args)

    monkeypatch.setattr("test_skills.MemorySandbox", ListingSandbox)
    provider, _, result, _ = execute(
        tmp_path,
        skill_spec,
        [
            '{"tool":"list_files","args":{}}',
            '{"tool":"search","args":{"text":"END_MARKER"}}',
            '{"tool":"finish","args":{}}',
        ],
    )
    history = json.loads(provider.contexts[2])
    assert "skills/language/references/long.md" in history[-3]["content"]
    assert '"matches": []' in history[-1]["content"]
    assert len(result["skill_accesses"]) == 3  # Listing paths is not reading contents.


def test_exact_measurement_uses_templated_text_not_encoding_dictionary(skill_spec):
    import runpy

    measure = runpy.run_path(str(ROOT / "scripts/measure_skills.py"))["measure"]

    class Tokenizer:
        def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
            assert tokenize is False and add_generation_prompt is True
            return "TEMPLATE" + "".join(message["content"] for message in messages)

        def encode(self, text, *, add_special_tokens):
            assert add_special_tokens is False
            return list(text.encode())

    base = load_config(ROOT / "configs/qwen-ab-base.json")
    bundle = SkillBundle.load(skill_spec)
    measured = measure(Tokenizer(), bundle, {"task": "public prompt"}, base, base)
    expected = len(("TEMPLATE" + SYSTEM + "public prompt").encode())
    assert measured["tasks"]["task"]["baseline_initial_prompt_tokens"] == expected
    assert measured["tasks"]["task"]["skills_initial_prompt_tokens"] > expected
