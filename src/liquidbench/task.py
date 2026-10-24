"""Versioned task fixtures and host-only evaluation assets."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath

from .evaluators import get_evaluator


# Held-out tasks evaluate final models only; never use them to author training data.
SPLITS = {"development", "heldout"}


def safe_name(name: str) -> bool:
    if not isinstance(name, str):
        return False
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and ".." not in p.parts and str(p) == name


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_tree(root):
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"Expected a regular fixture directory: {root}")
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Task fixtures cannot contain symlinks")
        if path.is_file():
            files[str(path.relative_to(root))] = path.read_text()
    return files


@dataclass(frozen=True)
class Task:
    root: Path
    manifest: dict
    initial: dict[str, str]
    cases: list[dict]
    reference_files: dict[str, str]
    validation: list[dict]

    @classmethod
    def load(cls, root: Path):
        root = root.resolve()
        manifest = json.loads((root / "task.json").read_text())
        required = {
            "id",
            "version",
            "split",
            "category",
            "difficulty",
            "family",
            "provenance",
            "runtime_subset",
            "editable_files",
            "prompt",
            "evaluator",
        }
        if required - manifest.keys():
            raise ValueError(f"Missing task fields: {sorted(required - manifest.keys())}")
        if manifest["split"] not in SPLITS:
            raise ValueError(f"Unknown task split: {manifest['split']!r}")
        get_evaluator(manifest["evaluator"])
        editable = manifest["editable_files"]
        if (
            not isinstance(editable, list)
            or not editable
            or not all(map(safe_name, editable))
            or len(set(editable)) != len(editable)
        ):
            raise ValueError("Invalid editable paths")
        initial = read_tree(root / "initial")
        if any(p not in initial for p in editable):
            raise ValueError("Editable files must exist in the starting fixture")
        reference = read_tree(root / "evaluator/reference")
        if not reference or not set(reference) <= set(editable):
            raise ValueError("Reference must modify only editable files")
        cases = json.loads((root / "evaluator/cases.json").read_text())
        if not isinstance(cases, list) or not cases:
            raise ValueError("At least one evaluation case is required")
        ids = [c["id"] for c in cases]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate evaluation case IDs")
        validation = json.loads((root / "evaluator/validation.json").read_text())
        names = {"starter", "reference"}
        for candidate in validation:
            name = candidate["name"]
            if not isinstance(name, str) or not name or name in names:
                raise ValueError("Invalid or duplicate validation candidate name")
            names.add(name)
            if type(candidate["expected_pass"]) is not bool:
                raise ValueError("Candidate verdict must be boolean")
            if not isinstance(candidate["changes"], dict) or not candidate["changes"]:
                raise ValueError("Candidate changes must be a nonempty file map")
            for path, content in candidate["changes"].items():
                if not safe_name(path) or not (content is None or isinstance(content, str)):
                    raise ValueError("Candidate changes require safe paths and text or null")
        if sum(c["expected_pass"] is False for c in validation) < 2:
            raise ValueError("At least two deliberately incorrect solutions are required")
        return cls(root, manifest, initial, cases, {**initial, **reference}, validation)

    @property
    def reference(self):
        """Convenience for callers of the original single-file task API."""
        if len(self.manifest["editable_files"]) != 1:
            raise ValueError("Use reference_files for multi-file tasks")
        return self.reference_files[self.manifest["editable_files"][0]]

    @property
    def digest(self):
        return fingerprint(
            {
                "manifest": self.manifest,
                "initial": self.initial,
                "cases": self.cases,
                "reference": self.reference_files,
                "validation": self.validation,
            }
        )


def discover_tasks(root: Path):
    tasks = [Task.load(p.parent) for p in sorted(root.glob("*/task.json"))]
    if not tasks:
        raise ValueError(f"No tasks found under {root}")
    if len({t.manifest["id"] for t in tasks}) != len(tasks):
        raise ValueError("Duplicate task IDs in suite")
    return tasks
