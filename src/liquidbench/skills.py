"""Pinned, read-only documents; no host paths are accepted from agent actions."""

import hashlib
import json
from pathlib import Path
import re
import subprocess

from .sandbox import ToolError
from .task import safe_name


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def validate_skill_config(spec):
    if spec is None:
        return
    if not isinstance(spec, dict) or set(spec) != {"manifest", "checkout", "revision"}:
        raise ValueError("skills requires manifest, checkout and revision, or null")
    if any(not isinstance(value, str) or not value for value in spec.values()):
        raise ValueError("Skill configuration values must be nonempty strings")
    if not re.fullmatch(r"[0-9a-f]{40}", spec["revision"]):
        raise ValueError("Skill revision must be a full Git commit SHA")


def validate_loading(config):
    mode = config.get("skill_loading", "full")
    if mode not in {"full", "on_demand"}:
        raise ValueError("skill_loading must be full or on_demand")
    if mode == "on_demand" and config.get("skills") is None:
        raise ValueError("on_demand requires a skill bundle")
    spec = config.get("neutral_context")
    if spec is not None:
        if config.get("skills") is not None:
            raise ValueError("Neutral context cannot expose skills")
        if (
            not isinstance(spec, dict)
            or set(spec) != {"path", "sha256"}
            or not isinstance(spec["path"], str)
            or not spec["path"]
            or not isinstance(spec["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", spec["sha256"])
        ):
            raise ValueError("neutral_context requires a path and SHA-256")


def load_neutral(config):
    validate_loading(config)
    spec = config.get("neutral_context")
    if spec is None:
        return None
    path = Path(spec["path"])
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
        raise ValueError("Invalid neutral context file")
    data = path.read_bytes()
    if sha256(data) != spec["sha256"]:
        raise ValueError("Neutral context hash mismatch")
    return data.decode("utf-8")


class SkillBundle:
    def __init__(self, manifest, documents, manifest_sha256):
        self.manifest = manifest
        self.documents = documents
        self.manifest_sha256 = manifest_sha256

    @classmethod
    def load(cls, spec):
        validate_skill_config(spec)
        raw = Path(spec["manifest"]).read_bytes()
        manifest = json.loads(raw)
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema_version") != 1
            or manifest.get("revision") != spec["revision"]
            or not isinstance(manifest.get("repository"), str)
        ):
            raise ValueError("Skill manifest revision/schema mismatch")
        entries, files = manifest.get("entries"), manifest.get("files")
        if not isinstance(files, dict) or not files or len(files) > 128:
            raise ValueError("Invalid skill file inventory")
        if (
            not isinstance(entries, list)
            or len(entries) != 3
            or any(not isinstance(name, str) for name in entries)
            or len(set(entries)) != 3
            or set(entries) != {name for name in files if name.endswith("/SKILL.md")}
        ):
            raise ValueError("Skill manifest must include exactly all three entry files")
        root = Path(spec["checkout"]).resolve(strict=True)

        def git(*args):
            result = subprocess.run(
                ["git", "-C", str(root), *args], capture_output=True, timeout=10, check=True
            )
            return result.stdout.decode()

        if git("rev-parse", "HEAD").strip() != spec["revision"]:
            raise ValueError("Skill checkout does not match pinned revision")
        tree = git("ls-tree", "-r", "--name-only", "HEAD", "--", "skills").splitlines()
        if set(tree) != set(files):
            raise ValueError("Skill manifest omits or adds files from the pinned skills tree")
        documents = {}
        total = 0
        for name, expected in sorted(files.items()):
            if not safe_name(name) or not name.startswith("skills/") or not name.endswith(".md"):
                raise ValueError("Unsafe skill document path")
            path = root / name
            current = path
            while current != root:
                if current.is_symlink():
                    raise ValueError("Skill symlinks are forbidden")
                current = current.parent
            if not path.is_file() or path.stat().st_size > 1_000_000:
                raise ValueError("Invalid skill file size/type")
            data = path.read_bytes()
            total += len(data)
            if total > 4_000_000 or expected != {"bytes": len(data), "sha256": sha256(data)}:
                raise ValueError(f"Skill document hash/size mismatch: {name}")
            if data != git("show", f"HEAD:{name}").encode("utf-8"):
                raise ValueError(f"Skill bytes differ from pinned Git object: {name}")
            documents[name] = data.decode("utf-8")
        return cls(manifest, documents, sha256(raw))

    def metadata(self):
        return {
            "revision": self.manifest["revision"],
            "repository": self.manifest["repository"],
            "manifest_sha256": self.manifest_sha256,
            "files": self.manifest["files"],
            "entries": self.manifest["entries"],
        }

    def entry_message(self):
        # Original UTF-8 contents, including front matter and trailing newlines.
        parts = [
            "Optional skill documents follow in full. Their relative reference links resolve "
            "from each document's directory. Use read_file with the listed skills/ paths.\n"
            "Available documents:\n" + "\n".join(sorted(self.documents))
        ]
        for name in self.manifest["entries"]:
            parts.extend(
                [f"\n--- BEGIN {name} ---\n", self.documents[name], f"--- END {name} ---\n"]
            )
        return "\n".join(parts)

    def read(self, name):
        if name not in self.documents:
            raise ToolError("Unknown skill document; use an exact listed skills/ path")
        return {"content": self.documents[name]}

    def index_message(self):
        # Fixed for every task: paths only, no solution-based selection or hints.
        return (
            "Optional skill entry documents are available on demand through read_file:\n"
            + "\n".join(self.manifest["entries"])
            + "\nUse exact skills/ paths. Relative links resolve from the document's directory. "
            "list_files also lists the reference documents. Reading documents uses the same "
            "turn and token budgets as other tools."
        )


def initial_messages(system, task_prompt, bundle=None, *, loading="full", neutral=None):
    messages = [{"role": "system", "content": system}]
    if bundle is not None:
        messages.append(
            {
                "role": "user",
                "content": (
                    bundle.entry_message() if loading == "full" else bundle.index_message()
                ),
            }
        )
    elif neutral is not None:
        messages.append({"role": "user", "content": neutral})
    messages.append({"role": "user", "content": task_prompt})
    return messages


def skill_path(name):
    # Normalize only for namespace protection, never for document lookup.
    return isinstance(name, str) and name.lstrip("./").split("/", 1)[0] == "skills"
