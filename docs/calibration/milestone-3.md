# Milestone 3: agent calibration and failure analysis

The final harness completed all five local tasks with zero protocol, tool or
infrastructure errors for both Qwen 1.5B and 3B. Both still passed 0/5 because
their code was wrong. The next step is a frozen 7B development pilot, not the
four-configuration research comparison. Graders and resource budgets were not
relaxed. The final comparison and readiness recommendation appear below; all
intermediate calibration attempts are retained.

These are five synthetic **development** tasks, used to debug the harness. None of the
results below are held-out measurements or evidence of research effectiveness. Raw
traces, result files and patches remain in ignored `runs/`; the companion metrics
file records their paths, SHA-256 hashes, source/config fingerprints and trace line
numbers. No evaluator cases or reference solutions were sent to the models.

## Baseline: what actually failed

Suite: `runs/suite-20261023T001559Z-b132dee1`. Each row identifies the attempt directory
within that suite. Line numbers refer to its `trace.jsonl`.

| Task / attempt | Trace and patch evidence | Attribution |
| --- | --- | --- |
| announcement-subtitle / `20261023T001559Z-48bbc8e0` | L3 calls `render` without reading. It puts heading/body/subtitle under `section`, although the prompt requires `section.settings`. L4 reports `Liquid::UndefinedVariable: ... heading`. L6 submits `finish`. Empty patch. | Model supplies the wrong variable nesting, then submits without editing. Harness limitation: the failure is misleadingly wrapped in outer `ok:true`, inner `ok:false`. No turn/token exhaustion. |
| asset-references / `20261023T001612Z-dd83a45f` | L3,6,…,36 repeat the identical `render` action with `strip_schema:true` on a snippet. L4,7,…,37 report `Expected exactly one top-level schema block`. Variables contain strings such as `t('promo.heading')`; these are data, not executable calls. Empty patch. | Model selects an unsupported workflow despite the visible static-only task instructions, never reads/edits, and repeats errors for 12 turns. Generic system instructions/error feedback could make the schema option and render limitations clearer. The turn cap is the terminal symptom, not evidence that productive work needed more turns. |
| product-card / `20261023T001639Z-bf9de566` | L3,6,…,36 repeat a render of Sample Product/Example Vendor with `strip_schema:true`; all 12 tool results reject the missing schema. Empty patch. | Same model tool-selection/recovery failure; no attempted Liquid repair to assess. Original starter still fails availability, fallbacks and escaping. |
| section-schema / `20261023T001711Z-d2868907` | L3 analyzes the section; L4 returns the original AST/schema/body. L6 writes only the extracted JSON body, still with duplicate `heading`, string `yes`, range default 7 and misspelled `show_summry`. L9 finishes. The patch removes the `<div>` markup and `{% schema %}` / `{% endschema %}` wrappers. | Model copies diagnostic data as a complete replacement without fixing it. The full file was available through `read_file`, which it never used. Large, repetitive analyzer output is a usability limitation; instructions did not explicitly distinguish extracted metadata from source. The grader correctly rejects missing schema even though Theme Check alone reports no errors. |
| shipping-message / `20261023T001726Z-7f9a88ba` | L3,6,…,36 repeat a snippet render with `strip_schema:true`; all 12 fail before rendering. The proposed settings also omit threshold/message. Empty patch. | Same repeated tool error and failure to edit. Missing variable keys are an additional visible mistake, but the trace does not show a Liquid render failure from them because schema extraction fails first. |

All 41 replies have a valid action envelope after the existing single-fence
normalization. There were **0 protocol errors, 37 tool errors, 0 provider errors,
0 output-length stops, 0 infrastructure failures**, and only one write. The five
results are all failures: two explicit finishes and three turn-budget stops. The
model used 42,221 input and 3,419 output tokens, counting cached/repeated prompts.

No missing hidden context caused these failures: the public prompts state the
requirements, and initial files were accessible. We cannot infer private reasoning
from traces; the attribution above describes observable actions. Finite hidden
tests cannot prove universal correctness, but all existing adversarial verdicts
remain required.

## What changed, and why

The portable JSON-in-content action protocol remains; native function calling
was not introduced. Initially, syntax was not the baseline bottleneck. Once the
models attempted writes, both sizes repeatedly produced malformed multiline
JSON, so the final calibration adds explicit `response_format: json_object`
through the serving API. This constrains JSON syntax only: no task-specific
schema, solution, tool choice or acceptance rule is encoded in the decoder.
The identical mode applies to all models and future comparison conditions.
`text` remains an explicit configuration option for reproducing unconstrained
experiments. Unsupported JSON mode fails as infrastructure, with no silent
fallback. A single Markdown fence remains accepted by the parser; arbitrary JSON
repair is still forbidden.

The shared instructions now say to read source, save a **complete** edited file,
check it, then finish. They explicitly distinguish rendering from editing,
extracted metadata from source, snippets from section schema extraction, and test
data from executable code. The final prompt includes a read-envelope example and
the exact finish action, with no example replacement content or task solution.
The same instructions apply to every model/task.

The harness validates argument names/types before execution, including boolean
`strip_schema`. Render/parser failures have one unambiguous `ok:false` envelope.
Schema-extraction errors explain the flag's precondition; repeated identical
failures receive generic recovery feedback. Errors still consume turns. A
provider `finish_reason:length` is logged and rejected without executing a
possibly incomplete action. Results now distinguish protocol errors, tool errors
and output truncations. No task grader, task fixture, or sandbox capability was
changed.

## Context and budgets

An 8,192-token context is a **per-request** bound on templated history plus output.
The 24,000-token budget is a **per-attempt cumulative** allowance across all
requests, including repeated/cached input. These are different controls; 24K does
not promise that one 24K prompt fits an 8K server.

Previously only cumulative admission was checked using an intentionally
conservative UTF-8-byte estimate. No separate context limit was enforced. In this
baseline, the largest actual prompt was only **2,249 tokens**, and no response
exceeded **265 tokens**, so neither the 8K window nor 1,024-token output limit
explains the failures. Some byte reservations exceeded 8K despite much smaller
actual prompts; treating those estimates as exact counts would prematurely stop
otherwise admissible requests.

Configurations now require `max_context_tokens` and `token_counting`.
`llama_cpp` applies the server chat template then tokenizes it; `vllm` uses its
chat `/tokenize` endpoint. A 32-token margin is reserved. Every request records
counting mode, count, reservation, context limit and message digest; reported
usage is checked before executing any action. Underestimated counts beyond the
margin or measured context overflow are infrastructure/accounting failures.
Counting failure fails closed, without inference or a fabricated token charge.

`conservative_bytes` remains an explicitly selected fallback for servers without
counting endpoints. It is not appropriate for an exact controlled comparison:
its early rejection can differ with prompt length. There is no silent history
truncation, summarization, sliding window, or fallback from failed server counting.
An overfull prompt stops with `context_budget`. Run llama.cpp with
`--no-context-shift`; its configured slot context must match the harness limit.

The frozen calibration budgets remain **12 turns, 1,024 output tokens/request,
24,000 cumulative tokens, 300 seconds, 90-second request timeout, two provider
retries**. The baseline gives no evidence for raising them. Cumulative remaining
tokens may reduce the last response allowance, as before; length stops are now
visible. Budgets must be frozen across future experimental configurations, and
any subsequent revision requires rerunning all compared conditions.

## Reproduction and interpretation

Keep one server and one attempt active at a time. Use temperature 0, top_p 1,
seed 42, the pinned GGUF, the recorded llama.cpp build, 8K context, one slot, and
the identical runtime image/task digests. Token counting performs no inference.
The local smoke rates are zero API cost, excluding hardware and electricity.

```sh
uv run liquidbench run-suite --config configs/local-smoke.json
uv run python scripts/analyze_runs.py \
  before=runs/suite-20261023T001559Z-b132dee1 \
  after=runs/<new-suite> > comparison.json
```

The before/after comparison evaluates a bundle of protocol/accounting changes,
not an isolated causal ablation. There is one attempt per task/model and no
statistical reliability claim. Larger-model runs are diagnostic; parameter count
and quantization differ from the future 7B experiment.

Serving details and the remaining 7B validation gate are in [qwen-7b.md](qwen-7b.md).

## Recorded prompt-only calibration runs

| Run | Passed | Protocol errors | Tool errors | Input / output tokens | Termination counts |
| --- | --- | --- | --- | --- | --- |
| Original Milestone 2 | 0/5 | 0 | 37 | 42,221 / 3,419 | finished 2; turn budget 3 |
| Initial calibration candidate (`f626dc7`) | 0/5 | 13 | 0 | 36,663 / 1,367 | finished 3; turn budget 2 |
| Final prompt, text decoding (`6a66d0e`) | 0/5 | 21 | 0 | 41,690 / 4,254 | finished 3; turn budget 1; token budget 1 |

All three suites had zero infrastructure errors and zero output-length stops.
Tool errors are failed tool operations, including legacy nested render failures;
protocol errors are responses rejected before execution. A lint diagnostic is not
itself a tool error. The final prompt-only run used 45,944 total tokens versus 45,640 originally
(+304, approximately +0.7%), across 28 versus 41 model calls. A lower tool-error
count does not establish better agent performance: invalid actions and incorrect
submissions replaced the earlier render loops.

The candidate suite is retained at
`runs/suite-20261023T012009Z-c324f706`. Its announcement submission copied the
illustrative `<p>Example</p>` write example from the initial prompt. Asset/product
runs also repeatedly omitted `args:{}` on finish (13 rejected actions). This is
evidence of a demonstration-copying risk and a protocol usability regression.
The final revision removed replacement-content examples and gave the exact
finish envelope both in the prompt and in envelope-error feedback. The parser
was **not** relaxed, and budgets/graders were unchanged. No further prompt changes
were made after observing the final scores. This intermediate run is not hidden
or replaced with a selected successful attempt.

Final prompt-only 1.5B suite: `runs/suite-20261023T012201Z-2b1c55a2`.

| Task / prompt-only attempt | Evidence and outcome |
| --- | --- |
| announcement-subtitle / `20261023T012201Z-3d8ea598` | L3 writes without reading, removes the schema, uses Handlebars-style `{{#if}}` instead of Liquid, loses escaping and show-body behavior. L7 finishes. 1,465 input / 148 output tokens. Coding/instruction-following failure. |
| asset-references / `20261023T012207Z-0c3beaea` | L3,6,…,36 repeat an incomplete JSON write envelope (missing a closing brace); errors at L4,7,…,37. Proposed content also replaces Liquid markup with an unrelated JSON object. No write executes; empty patch. Turn budget; 17,229 / 984 tokens. Protocol and proposed-code failure, not output truncation. |
| product-card / `20261023T012234Z-ce6aafab` | L3 now renders successfully with `strip_schema:false`. L7 saves the rendered HTML with literal Example Product / Shopify; L11 finishes. No general conditional/fallback behavior remains. 2,282 / 184 tokens. Tool use improved, but the model confuses rendered output with source code. |
| section-schema / `20261023T012242Z-6b3b822f` | Nine attempted writes contain literal newlines inside a JSON string (`Invalid control character`, first at L4). None executes. Proposed replacement also omits surrounding section code and required defaults. Stops at cumulative admission budget after 19,281 / 2,790 tokens, not at the 8K context boundary or output limit. The unspent balance cannot fund another growing prompt. |
| shipping-message / `20261023T012350Z-bf8204fa` | L3 writes the English acceptance instructions literally inside a paragraph; L7 finishes. 1,433 / 148 tokens. No conditional Liquid implementation; coding failure. |

Every server-counted prompt in both calibration suites exactly matched the
reported prompt usage (difference 0). A separate generic 7,022-token prompt also
matched exactly within the 8,192-token server window; see
[context-probe.json](context-probe.json). This supports the local accounting
implementation, not the unexecuted vLLM deployment. All original task digests and
the runtime image ID were preserved across these runs.

The same prompt-only revision on the larger official 3B Q4_K_M model also passed
0/5: 49,807 input / 4,164 output tokens, 33 calls, 23 protocol errors, zero tool or
infrastructure errors, and no output-length stops. It read and edited source on
three tasks, but product-card and section-schema repeatedly failed JSON parsing
(12 and 11 times). This cross-model evidence justifies JSON-object decoding;
simply adding turns would prolong invalid-action loops.

That suite is `runs/suite-20261023T012537Z-01442a59`. The valid edits were still
wrong: announcement appended subtitle after body, used the unsupported
`strip_whitespace` filter, and did not handle whitespace-only subtitles; asset
references fixed only the CTA key; shipping behavior remained incorrect.
These are model coding failures, independent of JSON syntax. Both models are
from the Qwen family, so this is not evidence of cross-family generalization.

The final code revision `3d7ea86` keeps the prompt fixed and enables JSON-object
decoding for both local models and the provisional 7B configuration. The prompt,
task/runtime hashes, turn/output/time/token budgets, and strict graders are
otherwise unchanged. The selection criterion is syntactic action reliability,
not task success. The initial candidate and both unconstrained model suites
remain in [metrics.json](metrics.json); all collected task attempts are retained.

## JSON-object decoding: larger-model result

The 3B JSON-mode suite is `runs/suite-20261023T012954Z-ef72862f`. It completed all
five attempts with explicit finish, **zero protocol/tool/infrastructure errors**,
zero length stops, and exact prompt-count agreement. It used **10,593 input /
1,185 output tokens in 13 calls**, versus 49,807 / 4,164 in 33 calls without JSON
mode. It still passed **0/5**; syntax reliability and coding correctness are
different outcomes.

| Task / JSON-mode 3B attempt | Why the grader rejected it |
| --- | --- |
| announcement-subtitle / `20261023T012954Z-4d10a199` | Reads source, then writes at trace L7 and finishes at L11. Preserves schema but appends subtitle after body, uses nonexistent `strip_whitespace`, and tests truthiness rather than trimmed nonempty text. |
| asset-references / `20261023T013026Z-fd9e57e9` | Reads at L3, writes at L7, finishes at L11. Only `promo.cta_missing` is fixed; the missing CSS filename and heading key remain broken. |
| product-card / `20261023T013036Z-51a6b929` | L3 writes invented Liquid syntax: object literal/default, `assign` and `unless` as filters, `strip_whitespace`, and a ternary expression. L7 finishes. The valid JSON envelope contains invalid Liquid. |
| section-schema / `20261023T013048Z-ff5387d8` | L3 repairs the settings/preset values, but deletes the protected markup and substitutes `<!-- Your existing markup here -->`. L7 finishes. Correct JSON schema alone is insufficient. |
| shipping-message / `20261023T013103Z-654db58e` | Reads at L3, writes at L7, finishes at L11. Adds `strip`/`escape` only; retains false-overriding default, wrong threshold boundary, missing empty-cart priority and missing message fallback. |

Neither model was given hidden grader feedback between actions. These diagnoses
come from post-run traces, patches and grader results. The 3B model's valid edits
and submissions show that the tool path can work with a real coding model; five
incorrect solutions do not establish reliable task-solving ability. It made no
`check` or `render` call in this JSON-mode suite, despite the shared instructions.

## Final before/after comparison

Final 1.5B suite: `runs/suite-20261023T013146Z-f5c34ab9`.

| Metric | Original 1.5B | Calibrated 1.5B | Calibrated 3B |
| --- | --- | --- | --- |
| Task success | 0/5 (0%) | 0/5 (0%) | 0/5 (0%) |
| Protocol errors | 0 | 0 | 0 |
| Tool errors | 37 | 0 | 0 |
| Input tokens | 42,221 | 8,140 | 10,593 |
| Output tokens | 3,419 | 996 | 1,185 |
| Model calls | 41 | 11 | 13 |
| Termination | finished 2; turn budget 3 | finished 5 | finished 5 |
| Infrastructure errors / length stops | 0 / 0 | 0 / 0 | 0 / 0 |

The final 1.5B run uses 9,136 total tokens, about **80.0% less** than the original
45,640, because invalid-action loops disappear and attempts finish earlier.
This is a development observation, not a general efficiency claim. Both final
models used source revision `3d7ea86` with an identical Python-source fingerprint;
only report/document files were uncommitted during the runs. All 30 retained
attempts share the original task digests and runtime image ID. The original
Milestone 2 run recorded its then-uncommitted implementation via source digest.
See [serving.json](serving.json) for local build/template metadata and pinned
configurations for model/GGUF revisions.

| Task / final 1.5B attempt | Tokens in/out | Trace evidence and coding failure |
| --- | --- | --- |
| announcement-subtitle / `20261023T013147Z-5faf2bec` | 1,461 / 144 | Write L3, finish L7; no read. Same Handlebars syntax, lost schema and missing preserved behavior as the text-mode attempt. |
| asset-references / `20261023T013153Z-16d4381a` | 1,286 / 93 | Write L3, finish L7. JSON envelope now parses, but file content is an unrelated JSON object with CSS import text and `t(...)` call syntax, replacing the required live Liquid outputs. |
| product-card / `20261023T013156Z-1be9ca8a` | 2,270 / 176 | Render L3, write L7, finish L11. Saves rendered Example Product/Shopify HTML as source; no general fallbacks or availability logic. |
| section-schema / `20261023T013205Z-547f84c2` | 1,694 / 439 | Write L3, finish L7; no read. Deletes markup, omits required defaults, adds an unsupported `numeric` field and changes preset structure to setting declarations rather than values. |
| shipping-message / `20261023T013218Z-069e98c8` | 1,429 / 144 | Write L3, finish L7. Saves the English requirements inside a paragraph rather than implementing Liquid conditionals. |

The final 1.5B run did not read source or call `check`. Both models stopped early
with incorrect code; **12 turns and 1,024 output tokens were not exhausted** in
the selected JSON-mode runs. More allowance is not justified by this evidence.
The full result/check lists and patches are preserved at the listed paths, with
content hashes in the committed metrics. No paid inference occurred.

## Readiness recommendation

Final validation: **161 tests passed locally** (76 unit, 85 container integration),
including **all 71 original grader verdicts** and the five scripted-reference
end-to-end successes. Ruff lint/format and `git diff --check` passed. CI runs the
same unit/container suites plus lint/format, including the analysis script.
Diff inspection confirms no changes to tasks, evaluators, shared grading,
runtime helpers or sandbox boundaries in this milestone. New tests cover context
admission, cumulative accounting, token-count failures, truncated responses,
tool arguments/error feedback, JSON-mode enforcement/no fallback, 7B request
compatibility and normalization of legacy trace errors.

**Ready for a frozen 7B development pilot; not yet ready for the four-configuration
research comparison.** Context accounting and action execution now have automated
coverage and real-server evidence. JSON-object output is the selected common
protocol mode. The current small-model results do not justify skills integration,
post-training, a larger budget, or any research score claim.

On an already available suitable host, first verify the pinned 7B checkpoint,
serving build, BF16 precision, JSON-output enforcement and `/tokenize` agreement,
then run all five development tasks and audit failures. Only after that should
the serving/protocol/budget manifest be frozen for a four-condition comparison.
Keep model mistakes distinct from protocol errors, context/cumulative stops and
missing infrastructure attempts. Do not silently tune a condition's budget or
exclude failures. See [qwen-7b.md](qwen-7b.md) for serving and cost assumptions.
