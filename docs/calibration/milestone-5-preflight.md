# Milestone 5: approved session stopped at preflight

**The paired experiment did not start.** The approved A40 session was provisioned
and verified, but the mandatory near-window probe failed before any task attempt.
All evidence was exported and the Pod was deleted. Baseline and skills scores
are **unmeasured**, not 0/5. No task prompts, graders, skills, budgets or serving
settings were changed to bypass the failure.

## Authorization, deployment and cost

The user approved 32,768 context tokens and 393,216 cumulative tokens for both
conditions, plus one A40 session of at most 90 minutes and **$2 USD all-in** using
existing credits. This superseded the preparation document's proposed $1 cap.

At 18:33:07 UTC on October 23, Runpod's live Secure Cloud catalog returned LOW
A40 availability in CA-MTL-1 and EU-SE-1, CUDA 13.2 support, and $0.59/hour.
One Pod, `vl71qkgjewldr9`, was created in CA-MTL-1 at **18:33:41.854 UTC** with
one A40, 100 GB ephemeral disk, and no persistent/network mounts. No substitute
GPU, additional Pod, top-up or other billable resource was created.

The official pinned image, all software package versions, model/tokenizer files
and four weight-shard hashes matched the previous pilot. Host evidence confirms
NVIDIA A40, BF16 support, vLLM 0.32.0, PyTorch 2.13.0+cu130, Transformers 5.19.0,
tokenizers 0.23.3 and xgrammar 0.2.8. The engine logged BF16, no quantization,
32,768 maximum sequence length and 24.53 GiB available KV-cache memory. The full
serving command matched the pilot except for the approved context change.
Inference used an SSH tunnel with its host fingerprint verified through provider
logs. Only SSH was requested as an exposed port.

The source tree was clean at preparation commit
`1299f740ec941904ee81f5cc63f0b64078d2a028`. The local agent/evaluator image remained
`sha256:ffd88aa28203d5582a880a59727f5e4700f1bf225387a381b60cb60bbadc9638`.
This results commit changes documentation/observed evidence only.

Deletion was requested at **18:37:15 UTC**, **213.146 seconds** after creation.
Estimated GPU cost is $0.03493; ephemeral storage adds about $0.00082, using
$0.10/GB/month and a 720-hour month. **Estimated total: $0.03575 (3.6 US cents),
before tax or billing adjustments.** The post-deletion billing read had no records;
the settled invoice is unknown, not zero.

Delete returned 204, an independent get returned 404, and fresh Pod and network
volume lists were empty. The SSH tunnel closed after deletion, and the local
Colima VM was stopped. No billable resource created for this session remains.

## Preflight evidence

All four probes used the frozen baseline configuration and synthetic messages,
not development task solutions or hidden cases. Trace lines refer to
`runs/m5-endpoint-preflight/trace.jsonl`.

| Probe | Input / output tokens | Count delta | Finish | Result |
| --- | ---: | ---: | --- | --- |
| Short read action, L4 | 522 / 18 | 0 | stop | Pass |
| Tool-feedback history, L8 | 613 / 10 | 0 | stop | Pass |
| JSON despite plain-text request, L12 | 42 / 9 | 0 | stop | Pass |
| Near-window action, L48 | 31,712 / 1,024 | 0 | length | **Fail** |

Preflight consumed **32,889 input and 1,061 output tokens**. These are diagnostic
tokens, not benchmark-attempt usage. The three shorter responses were complete
JSON and followed their probe contracts. The server fingerprint was
`vllm-0.32.0-9da1cd72`; full engine configuration is retained.

The near-window prompt fills the context with repeated `filler` tokens and then
asks for the normal finish action. The reply began `{"tool": "filler filler ...`
and continued repeating that word inside the tool-name string until the output
limit. It never closed the JSON object or emitted the expected action. The
response took 38.45 seconds; it was not a request timeout. Prompt usage matched
`/tokenize` exactly, and total request usage stayed within the 32K context.

This is evidence of **model instruction-following failure on the repetitive
near-window probe**, not a token-accounting error, memory failure or demonstrated
transport defect. JSON grammar enforcement permits a growing string; hitting
the output limit can leave that otherwise valid prefix incomplete. The passing
short JSON probe and active xgrammar configuration do not guarantee that a model
will choose the correct tool or finish a long string within 1,024 output tokens.

The predeclared runner requires `passed:true` from the complete endpoint
preflight. That report is false. We did not patch the report, relax the gate,
retry until a favorable output appeared, enlarge output budgets, or launch the
ten tasks anyway.

After the failure, **tokenization-only** checks independently matched all ten
planned initial conversations against the local measurements: baseline prompts
646–712 tokens; skills prompts 10,466–10,532. No completion requests were made
for those conversations. No task agent read a skill reference or submitted a
patch; no grading result exists for either arm. The three skill entries were
included only in the treatment tokenizer checks, not a model-inference attempt.

## What can and cannot be concluded

The 32K configuration starts successfully and counts tokens exactly. Its
repetitive near-window probe does not pass. This single probe does **not** show
that ordinary 10K skill prompts fail, identify a reliable context threshold, or
measure a skills benefit/regression. There is no paired correctness, validation
behavior, reference-use or latency comparison yet. The previous 2/5 pilot cannot
replace the missing fresh baseline.

The most useful next step is a separate preflight review and a predeclared
diagnostic plan: distinguish serving/accounting checks from model instruction
following, compare repetitive and varied synthetic padding across context
lengths, and retain every outcome. Any change to which checks gate the paired
experiment must be justified and documented **before** another run, rather than
retroactively marking this failure as passed. Do not use task answers or weaken
the graders to repair a serving diagnostic.

No preflight redesign is implemented in this commit. No fine-tuning or training
data is started. Another paid session requires fresh approval; the approved one
has been used and terminated.

## Retained artifacts and validation

The complete preflight trace and report, host/model/software evidence, creation
and cleanup records, initial-count checks and cost estimate are retained locally
under `runs/skills-ab-session/` and `runs/m5-endpoint-preflight/`.

The verified archive is `runs/liquidbench-skills-ab-preflight-20261023.tar.gz`,
with a companion SHA-256 file and per-file manifest. Machine-readable observations,
trace line references and archive/file hashes are committed in
[milestone-5-preflight.json](milestone-5-preflight.json). No credentials, model
weights, hidden cases or upstream skill bodies are included in the committed
evidence summary. Private SSH keys remain outside the archive.

The unchanged preparation code passed 201 tests and all 71 grader verdicts in
[preparation CI](https://github.com/Sahaj0312/liquidBench/actions/runs/40003274060).
The documentation/evidence commit is also checked by GitHub CI before handoff.
