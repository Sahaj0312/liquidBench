"""Synthetic upstream document fixture shared by unit and container tests."""

import json
import subprocess

import pytest

from liquidbench.skills import sha256


@pytest.fixture
def skill_spec(tmp_path):
    checkout = tmp_path / "upstream"
    checkout.mkdir()
    entries = [f"skills/{name}/SKILL.md" for name in ("language", "standards", "a11y")]
    files = {name: f"---\nname: {name}\n---\nUnmodified entry: é\r\n" for name in entries}
    files["skills/language/references/long.md"] = "full reference Ω\n" * 1800 + "END_MARKER"
    for name, content in files.items():
        path = checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode())

    def git(*args):
        return subprocess.check_output(["git", "-C", str(checkout), *args], text=True).strip()

    git("init", "-q")
    git("add", "skills")
    git(
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "fixture",
    )
    revision = git("rev-parse", "HEAD")
    manifest = {
        "schema_version": 1,
        "repository": "https://example.invalid/synthetic-skills.git",
        "revision": revision,
        "entries": entries,
        "files": {
            name: {"bytes": len(text.encode()), "sha256": sha256(text.encode())}
            for name, text in files.items()
        },
    }
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(manifest))
    return {"manifest": str(path), "checkout": str(checkout), "revision": revision}
