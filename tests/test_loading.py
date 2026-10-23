"""Condition isolation, exact exposure, and shared accounting with synthetic documents."""

import json
from pathlib import Path

import pytest

from liquidbench.skills import SkillBundle, initial_messages, load_neutral, sha256, validate_loading
from liquidbench.runner import SYSTEM
from test_skills import execute
from test_runner import ScriptedProvider
from liquidbench.provider import Completion


def neutral_spec(tmp_path):
    path = tmp_path / "neutral.txt"
    path.write_text("Neutral museum inventory. Blue vase, shelf 14.\n")
    return {"path": str(path), "sha256": sha256(path.read_bytes())}


def test_on_demand_index_has_paths_without_any_document_body(skill_spec, tmp_path):
    bundle = SkillBundle.load(skill_spec)
    messages = initial_messages(SYSTEM, "same task", bundle, loading="on_demand")
    assert messages[0]["content"] == SYSTEM and messages[-1]["content"] == "same task"
    assert all(name in messages[1]["content"] for name in bundle.manifest["entries"])
    assert all(content not in messages[1]["content"] for content in bundle.documents.values())
    name = bundle.manifest["entries"][0]
    provider, directory, result, seen = execute(
        tmp_path,
        skill_spec,
        [
            json.dumps({"tool": "read_file", "args": {"path": name}}),
            '{"tool":"finish","args":{}}',
        ],
        skill_loading="on_demand",
    )
    assert result["status"] == "passed"
    response = json.loads(
        json.loads(provider.contexts[1])[-1]["content"].removeprefix("Tool result: ")
    )
    assert bundle.documents[name] == response["result"]["content"]
    assert [a["mode"] for a in result["skill_accesses"]] == ["read_file"]
    assert result["skill_accesses"][0]["first_model_turn"] == 1
    assert result["context_exposures"][0]["kind"] == "skill_index"
    assert result["context_exposures"][0]["first_model_turn"] == 0
    assert result["input_tokens"] == 200
    assert not any(p.startswith("skills/") for p in seen[0])
    assert "context_delivery" in (directory / "trace.jsonl").read_text()


def test_on_demand_no_read_is_not_document_exposure(skill_spec, tmp_path):
    _, _, result, _ = execute(
        tmp_path, skill_spec, ['{"tool":"finish","args":{}}'], skill_loading="on_demand"
    )
    assert result["skill_accesses"] == []
    assert result["context_exposures"][0]["kind"] == "skill_index"


def test_neutral_is_counted_and_cannot_read_skills(tmp_path, monkeypatch):
    spec = neutral_spec(tmp_path)
    monkeypatch.setattr(SkillBundle, "load", lambda *_: pytest.fail("No skills in neutral"))
    provider, _, result, seen = execute(
        tmp_path,
        None,
        [
            '{"tool":"read_file","args":{"path":"skills/language/SKILL.md"}}',
            '{"tool":"finish","args":{}}',
        ],
        neutral_context=spec,
    )
    assert result["tool_errors"] == 1 and result["input_tokens"] == 200
    assert result["skills"] is None and result["skill_accesses"] == []
    assert "Neutral museum inventory" in provider.contexts[0]
    assert result["context_exposures"] == [
        {
            "kind": "neutral",
            "bytes": Path(spec["path"]).stat().st_size,
            "sha256": spec["sha256"],
            "first_model_turn": 0,
        }
    ]
    assert not any("neutral" in p for p in seen[0])


@pytest.mark.parametrize("mode", ["neutral", "on_demand"])
def test_injected_context_is_subject_to_context_limit(mode, tmp_path, skill_spec, monkeypatch):
    class CountingProvider(ScriptedProvider):
        def count_prompt(self, messages, timeout):
            assert len(messages) == 3
            return 4000

        def complete(self, *args):
            pytest.fail("Context must block before generation")

    monkeypatch.setattr("test_skills.ScriptedProvider", CountingProvider)
    kwargs = (
        {"neutral_context": neutral_spec(tmp_path)}
        if mode == "neutral"
        else {"skill_loading": "on_demand"}
    )
    _, _, result, _ = execute(
        tmp_path, None if mode == "neutral" else skill_spec, [], max_context_tokens=4096, **kwargs
    )
    assert result["termination"] == "context_budget"
    assert result["context_exposures"][0]["first_model_turn"] is None


def test_on_demand_read_subject_to_total_budget(tmp_path, skill_spec, monkeypatch):
    class CountingProvider(ScriptedProvider):
        def count_prompt(self, messages, timeout):
            return 4000 if "END_MARKER" in json.dumps(messages) else 1000

        def complete(self, messages, max_tokens, timeout):
            reply = super().complete(messages, max_tokens, timeout)
            return Completion(reply.content, self.count_prompt(messages, timeout), 20, {})

    monkeypatch.setattr("test_skills.ScriptedProvider", CountingProvider)
    _, _, result, _ = execute(
        tmp_path,
        skill_spec,
        ['{"tool":"read_file","args":{"path":"skills/language/references/long.md"}}'],
        skill_loading="on_demand",
        max_total_tokens=4500,
    )
    assert result["termination"] == "token_budget"
    assert result["skill_accesses"][0]["first_model_turn"] is None


@pytest.mark.parametrize(
    "bad",
    [
        {"skill_loading": "summary"},
        {"skill_loading": "on_demand"},
        {"neutral_context": {"path": "x", "sha256": "bad"}},
        {"skills": {}, "neutral_context": {"path": "x", "sha256": "a" * 64}},
    ],
)
def test_invalid_loading_rejected(bad):
    with pytest.raises(ValueError):
        validate_loading(bad)


def test_neutral_tamper_fails_before_inference(tmp_path):
    spec = neutral_spec(tmp_path)
    Path(spec["path"]).write_text("different")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_neutral({"neutral_context": spec})
    provider, _, result, seen = execute(tmp_path, None, [], neutral_context=spec)
    assert result["status"] == "infrastructure_error"
    assert not provider.contexts and not seen and "image_id" not in result


def test_all_study_configs_preserve_historical_execution_settings():
    from liquidbench.runner import load_config
    from liquidbench.study import CONDITIONS, TREATMENT_KEYS

    root = Path(__file__).resolve().parents[1]
    original = load_config(root / "configs/qwen-ab-base.json")

    def shared(cfg):
        return {k: v for k, v in cfg.items() if k not in TREATMENT_KEYS | {"purpose"}}

    for condition in CONDITIONS:
        assert shared(load_config(root / f"configs/m6-{condition}.json")) == shared(original)
