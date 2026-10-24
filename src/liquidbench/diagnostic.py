"""Diagnostic v1: public-input selection and forced, unmodified reference delivery.

No result, hidden case or solution enters either selection function. Historical
Milestone 6 plans and default runner behavior are not rewritten.
"""

from itertools import product
import json
from pathlib import Path
import re

from .runner import SYSTEM, source_version
from .skills import sha256
from .study import RUNTIME_IMAGE
from .task import fingerprint

CONDITIONS = ("original", "clarified", "reference", "neutral")
DOMAINS = {
    "section-schema": "schema",
    "theme-references": "references",
    "conditional-logic": "syntax",
    "liquid-syntax": "syntax",
    "liquid-rendering": "rendering",
    "rendering": "rendering",
    "section-modification": "modification",
    "theme-modification": "modification",
}
EXCLUDED = {
    "optional-caption": "Undefined 'enabled' and unclear input nesting",
    "notice-link": "Input nesting not fully specified in public description",
    "visible-list-limit": "Input nesting not fully specified in public description",
}
REPETITIONS = 4  # Each task occupies every condition position exactly once.
CLARIFICATION = """

Public-tool interpretation for this isolated task:
- render executes strict core Liquid with only the variables you supply. It does
  not emulate Shopify objects, defaults, includes, or platform-specific filters.
  For a file that requires unsupported platform behavior, use read_file, analyze
  and check for static inspection; repeating an unsupported render is not a test
  of the platform's behavior. A successful render covers only your supplied data.
- check reports static diagnostics for a partial theme. Severity 0 is an error;
  severity 1 is a warning. A warning alone does not establish a failed task.
  An orphaned snippet or unknown externally supplied variable may be expected in
  an isolated fixture. Use the public task contract and source to interpret it.
  Do not add callers, invent schema settings, rename supplied variables, edit
  protected resources, or suppress checks merely to remove such a warning.
- analyze returns structure and metadata, not a complete replacement source file.
  Preserve source outside the requested edit. When only literal operands may
  change, keep all other syntax, attributes and their ordering. When a schema or
  surrounding source is declared byte-preserved, retain those exact bytes.
- A clean public check is not proof of all required behavior. Inspect the task's
  declared cases and use supported tools with your own representative input.
  Do not infer hidden acceptance criteria or expand the editable scope.
"""
CONTEXT_HEADER = (
    "Supplementary reference material follows. The task and tool protocol take priority.\n"
)


def select_tasks(manifests):
    """One/domain, 2 easy + 2 medium + 1 hard; lexicographically smallest set hash."""
    groups = [
        [m for m in manifests if DOMAINS[m["category"]] == domain and m["id"] not in EXCLUDED]
        for domain in sorted(set(DOMAINS.values()))
    ]
    candidates = [
        group
        for group in product(*groups)
        if sorted(m["difficulty"] for m in group) == ["easy", "easy", "hard", "medium", "medium"]
    ]
    if not candidates:
        raise ValueError("No balanced public task selection")
    selected = min(
        candidates,
        key=lambda group: sha256(
            ("diagnostic-v1:" + ",".join(sorted(m["id"] for m in group))).encode()
        ),
    )
    return sorted(m["id"] for m in selected)


def reference_index(bundle):
    """Paths and Markdown headings outside code fences; no body examples indexed."""
    index = {}
    for path, content in sorted(bundle.documents.items()):
        if "/references/" not in path:
            continue
        headings = []
        fence = None
        for line in content.splitlines():
            mark = re.match(r"^\s*(`{3,}|~{3,})", line)
            if mark:
                symbol = mark[1][0]
                fence = symbol if fence is None else None if fence == symbol else fence
            elif fence is None and re.match(r"^#{1,6} ", line):
                headings.append(line.lstrip("# "))
        identifiers = sorted(set(re.findall(r"`([a-z_][a-z0-9_]*)`", "\n".join(headings))))
        index[path] = {
            "headings": headings,
            "identifiers": identifiers,
            **bundle.manifest["files"][path],
        }
    if not index:
        raise ValueError("No indexed reference documents")
    return index


def select_reference(public_prompt, index):
    """Ordered public-intent rules, resolved against the pinned heading index.

    No task IDs, outcomes, code, evaluation assets or solution bodies are inputs.
    Unrecognized intent or nonunique index matches block preparation for review.
    """
    first = public_prompt.split(". ", 1)[0].lower()
    prompt = public_prompt.lower()
    if re.search(r"\b(schema|presets?)\b", first):
        rule, heading = "schema-repair", "Schema & Settings Reference"
    elif re.search(r"\breferences?\b", first):
        if re.search(r"\btranslate\b|\bthrough t\b", prompt):
            rule, heading = "translation-reference", "Localization"
        elif "asset_url" in prompt:
            rule, heading = "asset-reference", "Hosted file"
        else:
            raise ValueError("Reference intent lacks an indexed platform operation")
    elif re.search(r"\b(trim|trimmed|trimming|join)\b", prompt):
        rule, heading = "string-processing", "String"
    elif re.search(r"\b(if|when|otherwise|boolean|booleans|priority)\b", prompt):
        rule, heading = "conditional-control", "Conditional"
    else:
        raise ValueError("Unrecognized public intent; no fallback or per-task override")
    candidates = [path for path, entry in index.items() if heading in entry["headings"]]
    if len(candidates) != 1:
        raise ValueError("Reference heading must resolve uniquely in pinned index")
    return {
        "path": candidates[0],
        "rule": rule,
        "index_heading": heading,
        "public_prompt_sha256": sha256(public_prompt.encode()),
    }


def context_message(body):
    # Identical wrapper/role/position in reference and neutral conditions.
    return CONTEXT_HEADER + body


def messages(prompt, condition, content=None):
    if condition not in CONDITIONS or (
        (condition in {"reference", "neutral"}) != (content is not None)
    ):
        raise ValueError("Condition/context mismatch")
    system = SYSTEM + ("" if condition == "original" else CLARIFICATION)
    history = [{"role": "system", "content": system}]
    if content is not None:
        history.append({"role": "user", "content": content})
    return history + [{"role": "user", "content": prompt}]


def build_plan(tasks, config, bundle, selections, measurements, controls):
    selected = select_tasks([t.manifest for t in tasks])
    by_id = {t.manifest["id"]: t for t in tasks}
    if set(selections) != set(selected) or set(controls) != set(selected):
        raise ValueError("Selection/control task mismatch")
    order = []
    for rep in range(REPETITIONS):
        rotated = selected[rep:] + selected[:rep]
        for i, task_id in enumerate(rotated):
            shift = (selected.index(task_id) + rep) % 4
            for position, condition in enumerate(CONDITIONS[shift:] + CONDITIONS[:shift]):
                order.append(
                    {
                        "repetition": rep + 1,
                        "seed": config["seed"],
                        "block": rep * 5 + i,
                        "task_id": task_id,
                        "task_digest": by_id[task_id].digest,
                        "condition": condition,
                        "position": position,
                    }
                )
    return {
        "schema_version": 1,
        "study": "diagnostic-v1",
        "development_only": True,
        "research_result": False,
        "inference_performed": False,
        "repetition_policy": "4 seed-42 repeats; position-balanced reproducibility checks, not independent samples",
        "selection_policy": "minimum SHA256 diagnostic-v1:sorted-ids; one/domain; 2 easy, 2 medium, 1 hard; audited exclusions",
        "excluded_tasks": EXCLUDED,
        "selected_tasks": selected,
        "public_selection_inputs": [
            {k: t.manifest[k] for k in ("id", "category", "difficulty", "prompt")}
            for t in sorted(tasks, key=lambda t: t.manifest["id"])
        ],
        "system_sha256": sha256(SYSTEM.encode()),
        "clarification_sha256": sha256(CLARIFICATION.encode()),
        "python_source_digest": source_version()["python_source_digest"],
        "runtime_image_id": RUNTIME_IMAGE,
        "config": config,
        "skills": bundle.metadata(),
        "reference_index_sha256": fingerprint(reference_index(bundle)),
        "reference_policy": "Ordered public-intent routes: schema/preset in first sentence, literal references (translation before asset), string processing, conditional control; unique indexed heading; full file; no fallback or per-task override",
        "references": selections,
        "measurements": measurements,
        "controls": controls,
        "order": order,
    }


def treatment(plan, task, condition, bundle=None):
    """Reconstruct verified treatment; no skill read tool is enabled in any arm."""
    task_id = task.manifest["id"]
    if task_id not in plan["selected_tasks"] or condition not in CONDITIONS:
        raise ValueError("Unknown diagnostic task/condition")
    appendix = "" if condition == "original" else CLARIFICATION
    injected = None
    if condition == "reference":
        if bundle is None or bundle.metadata() != plan["skills"]:
            raise ValueError("Pinned bundle required for reference delivery")
        name = plan["references"][task_id]["path"]
        body = bundle.documents[name]
        injected = {
            "content": context_message(body),
            "metadata": {
                "kind": "skill_reference",
                "path": name,
                "mode": "injected",
                "revision": bundle.manifest["revision"],
                **bundle.manifest["files"][name],
            },
        }
    elif condition == "neutral":
        spec = plan["controls"][task_id]
        path = Path(spec["path"])
        if path.is_symlink():
            raise ValueError("Neutral symlink forbidden")
        content = path.read_text()
        if sha256(content.encode()) != spec["sha256"]:
            raise ValueError("Neutral content changed")
        injected = {"content": content, "metadata": {"kind": "matched_neutral"}}
    history = messages(
        task.manifest["prompt"], condition, injected["content"] if injected else None
    )
    expected = plan["measurements"][task_id][condition]
    if fingerprint(history) != expected["messages_sha256"]:
        raise ValueError("Treatment messages differ from frozen plan")
    return {"system_appendix": appendix, "injected_context": injected}


def execute_block(plan, tasks, block, directory, *, runner, resolve_image, bundle=None):
    """Four ordered arms for one task/repetition; no resume, retry or score stopping."""
    if type(block) is not int or block not in range(20):
        raise ValueError("Block must be 0..19")
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    selected = [x for x in plan["order"] if x["block"] == block]
    summary = {"plan_sha256": fingerprint(plan), "planned": selected, "runs": [], "complete": False}
    path = directory / "summary.json"

    def save():
        path.write_text(json.dumps(summary, indent=2) + "\n")

    save()
    image = resolve_image(plan["config"]["image"])
    if image != plan["runtime_image_id"]:
        raise ValueError("Runtime changed")
    by_id = {t.manifest["id"]: t for t in tasks}
    for item in selected:
        task = by_id[item["task_id"]]
        if task.digest != item["task_digest"]:
            raise ValueError("Task changed")
        kwargs = treatment(plan, task, item["condition"], bundle)
        dest, result = runner(
            task, {**plan["config"], "image": image}, directory / item["condition"], **kwargs
        )
        summary["runs"].append(
            {
                **item,
                "artifacts": str(dest.relative_to(directory)),
                "status": result["status"],
                "termination": result["termination"],
            }
        )
        save()
        if result["status"] == "infrastructure_error":
            return 2
    summary["complete"] = True
    save()
    return int(any(r["status"] == "failed" for r in summary["runs"]))
