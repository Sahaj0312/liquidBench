"""Versioned task loading and content fingerprints."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath


def safe_name(name: str) -> bool:
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and ".." not in p.parts and str(p) == name


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class Task:
    root: Path
    manifest: dict
    initial: dict[str, str]
    cases: list[dict]
    reference: str

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
        }
        if required - manifest.keys():
            raise ValueError(f"Missing task fields: {sorted(required - manifest.keys())}")
        if manifest["split"] != "development":
            raise ValueError("This MVP accepts development tasks only")
        if not manifest["editable_files"] or not all(map(safe_name, manifest["editable_files"])):
            raise ValueError("Invalid editable paths")
        initial = {}
        for path in sorted((root / "initial").rglob("*")):
            if path.is_symlink():
                raise ValueError("Task fixtures cannot contain symlinks")
            if path.is_file():
                initial[str(path.relative_to(root / "initial"))] = path.read_text()
        if any(p not in initial for p in manifest["editable_files"]):
            raise ValueError("Editable files must exist in the starting fixture")
        cases = json.loads((root / "evaluator/cases.json").read_text())
        return cls(
            root, manifest, initial, cases, (root / "evaluator/reference.liquid").read_text()
        )

    @property
    def digest(self):
        return fingerprint(
            {
                "manifest": self.manifest,
                "initial": self.initial,
                "cases": self.cases,
                "reference": self.reference,
            }
        )
