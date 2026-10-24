# Diagnostic v1 benchmark audit

This audit covers the 20 development tasks. It looks for cases where unsupported renderer
behavior, misleading static warnings, or unclear preservation requirements could distract
from the intended task. It is **documentation only**. No task, prompt, grader, case or
Milestone 6 artifact was changed. The proposed corrections below would apply only to a
future, separately versioned benchmark revision.

Raw checker output for every starter and reference solution is in
[`benchmark-audit.json`](benchmark-audit.json). It was produced by
`scripts/audit_diagnostic.py` on runtime image
`sha256:ffd88aa28203d5582a880a59727f5e4700f1bf225387a381b60cb60bbadc9638`.

## 1. Static warnings on correct solutions

None of the 20 reference solutions has a severity-0 (error) offense. Several **correct**
reference solutions still report severity-1 warnings:

| Warning | Tasks (reference solution) | Cause |
| --- | --- | --- |
| `OrphanedSnippet` | asset-references, cart-arithmetic, customer-name, eligibility-branch, icon-reference, locale-references, option-list, product-card, shipping-message, status-priority, stylesheet-pair, tag-membership | Isolated fixtures contain a snippet with no caller |
| `UndefinedObject` | notice-link (`body`), optional-caption (`footer`), visible-list-limit (`rows`) | Inputs supplied by the harness as top-level variables |

A model that treats any warning as failure may add callers, rename supplied variables or
invent schema settings to make the warning disappear. Graders already ignore warnings.
The tool descriptions do not say so.

**Proposed correction (future revision):** state in the tool protocol that severity 1 is
a warning, and that orphaned-snippet and unknown-supplied-variable warnings are expected in
isolated fixtures. Diagnostic v1 tests exactly this wording as the `clarified` condition
(see `CLARIFICATION` in `src/liquidbench/diagnostic.py`).

## 2. Renderer limitations

`render` runs strict core Liquid with only the variables the agent supplies. It does not
emulate Shopify objects, `t`/`asset_url` and other platform filters, defaults or includes.
The reference-type tasks already say "do not use the core renderer for…". The general
tool protocol does not say that repeating an unsupported render is not a meaningful test.

**Proposed correction:** add that sentence to the tool protocol. Diagnostic v1 also tests
this as part of the `clarified` condition.

## 3. Ambiguous input nesting (excluded from diagnostic v1)

Three theme-modification prompts mix bare input names with `section.settings.*` values.
They do not say which inputs are top-level and which are nested settings. The starters
read `footer`, `body` and `rows` at top level. The schema-backed toggles and values
(`show_caption`, `caption`, `show_link`, `url`, `label`, `limit`) are left unspecified.

| Task | Ambiguity | Proposed wording |
| --- | --- | --- |
| optional-caption | "only if **enabled**" refers to an undefined input (presumably `show_caption`); nesting of `footer`, `show_caption` and `caption` unstated | "`footer` is a top-level string. `section.settings.show_caption` is a boolean and `section.settings.caption` is null or a string. Show the caption only if `show_caption` is true and…" |
| notice-link | Nesting of `body`, `show_link`, `url` and `label` unstated | "`body` is a top-level string. `section.settings.show_link` is a boolean; `section.settings.url` and `section.settings.label` are null or strings." |
| visible-list-limit | `rows` vs `section.settings.limit` nesting unstated | "`rows` is a top-level ordered array…; `section.settings.limit` is an integer 1..3." |

The proposed nesting matches each task's `evaluator/cases.json` inputs, which were read
only to check this documentation. Task selection did not use them. These three tasks are **excluded** from diagnostic v1 (`EXCLUDED` in
`diagnostic.py`). They remain unchanged in the Milestone 6 record.

## 4. Preservation requirements

Two preservation patterns look sound but are easy to violate with whole-file rewrites,
especially after `analyze` returns structure rather than source:

- "Only literal operands may change" (asset-references, icon-reference, locale-references,
  stylesheet-pair)
- "Preserve the entire schema block byte-for-byte" (section modification tasks)

No wording change is proposed. The `clarified` condition reminds the agent that `analyze`
is not a replacement source file, and that declared byte-preserved regions must be kept
exactly.

## Not changed

- Milestone 6 tasks, prompts, graders, plans, results and evidence
- Grader severity handling and checker output
- Upstream skill documents
