# Methodology and reproduction

[Português](../metodologia.md) | **English** · [English index](README.md)

The [experiment catalog](benchmarks.md) describes the design and caveats of
each measurement. This page guides interpretation and new runs; publishing
the archive did not rerun inference.

## Metrics that must not be confused

| Metric | Definition and limit |
|---|---|
| Decode, tok/s | `eval_count / (eval_duration / 1e9)`; measures generation, excluding load time and prefill. |
| Prefill, tok/s | `prompt_eval_count / (prompt_eval_duration / 1e9)`; short prompts and caching can dominate this metric. |
| Wall time | Time observed by the client, including waiting and other costs. A queue A/B is not equivalent to a decode A/B. |
| Cold load | Duration of loading the model; distinguish it from warmup and calls with a resident model. |
| `auto_score` | Fraction of applicable checks passed. The scoring rules changed on September 10; do not aggregate different versions. |
| Escalation | Presence of the token compared with `expect_escalation` in a labeled set. LEAK and MISS have different impacts. |
| Multi-round contract | Includes correct value, protocol, sources, and provenance; getting the value right alone is insufficient. |
| Language | Marker-based heuristic; an accepted `tie` does not demonstrate correct language. See [PT→EN](findings/qwen3-14b-language-template.md). |

The [old baseline](../../baseline-3080ti/baseline-3080ti.md) divides tokens by
total time, which includes prefill. Comparing it directly with pure decode on
the 5090 produces a biased ratio. A GPU's throughput cannot be inferred from
where a file sits in the directory tree.

## Offline verification

```bash
python3 tools/inventory.py check
```

The command validates SHA-256, size, and the evidence file list; parses JSON
files; and checks relative links to files in the new documentation. It does
not access Ollama or import an inference harness. The manifest is a record of
byte integrity, not a classification of experimental validity.

To incorporate new evidence, first inspect the added files, record the method
and result, and then update the manifest:

```bash
python3 tools/inventory.py update
python3 tools/inventory.py check
```

Do not use `update` to hide accidental changes to historical data.
Corrections should identify which conclusions they supersede. Use the
[experiment template](templates/experiment.md).

## Running a new measurement

These instructions make real calls to the server. In a shared benchmark
environment, arrange a window and record the configuration before starting;
see [infrastructure](infrastructure.md). The examples do not restart the server.

### Customer support quality

`run_chat.py` uses only the standard library. Specify models explicitly:
its internal defaults are inherited from the older campaign and do not
represent the September production configuration.

```bash
OLLAMA_URL=http://127.0.0.1:11434 \
MODELS_OVERRIDE=qwen3:14b THINK=false \
OUT_SUFFIX=.minha-medicao-001 python3 run_chat.py
```

Choose an unused `OUT_SUFFIX`: the runner writes
`results/chat_raw<SUFIXO>.json` and `results/chat_table<SUFIXO>.md` and can
overwrite a run with the same suffix. Record hashes of the prompt, goldset,
and runner before the call; their current state does not automatically
reconstruct the old scoring rules.

The runner's current options are `temperature=0.7`, `num_ctx=8192`, and `seed=42`.
A single run of the 18 cases is a screening pass. Repeating a seed is not
equivalent to independent samples, and the same seed produced different results
between sessions in the [resampling experiment](../../results/RESULTADO-reamostra-qwen3-14b-2026-09-08.md).

### Generation throughput

`bench.py` depends on `requests`, declared in [requirements.txt](../../requirements.txt).
Its endpoint is hardcoded to `http://localhost:11434`; the `OLLAMA_URL` variable
does **not** change this runner. GPU capture attempts `powershell.exe` with
`nvidia-smi` and records an error if unavailable. This does not establish the
GPU behind a remote endpoint; record the server hardware separately.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python bench.py qwen3:14b
```

Always pass the intended list: without arguments, it enumerates every installed
model and may replace resident models. The test uses three prompts and two
runs per prompt, saves `results/bench_<timestamp>.json`, and has no separate
warmup or evaluation of generated content.

### Endpoint A/B

```bash
ENDPOINT_A=http://127.0.0.1:11434 LABEL_A=controle \
ENDPOINT_B=http://127.0.0.1:11435 LABEL_B=candidato \
MODEL=qwen3:8b REPS=5 NUM_CTX=8192 python3 bench_engine_ab.py
```

The endpoints must be prepared beforehand. The runner alternates A/B
sequentially, discards warmup, and fixes options. Two servers competing for
the same GPU in parallel would confound the experiment. Runtime version and
context must be recorded; the preserved WSL/Windows measurement used different
Ollama versions.

### Phase harnesses

Consult the [catalog](benchmarks.md) for specific scripts and raw files.
The `baseline-3080ti/repro/` location was preserved because the scripts resolve
relative paths to the root. Some depend on SSH, PowerShell, or the external
`llm-gateway` checkout; a file's presence does not guarantee self-contained
reproduction. The historical offline judge comparator contains an absolute
path and overwrites its output artifact. To read the archive only, use the
inventory command above.

## Rules for new conclusions

1. State the hypothesis, workload, unit of analysis, versions, hashes, and
   success criteria before measuring. Distinguish question, seed, and run samples.
2. Preserve complete responses, errors, latency, and actual counts. A truncated
   preview does not establish the absence of a token or evidence.
3. Report denominators and exclusions. HTTP errors do not become correct
   responses; a labeled set does not reproduce production's unlabeled problem.
4. Check residency and truncation. For speculative models, `/api/ps` alone
   does not validate all VRAM usage. Matching numbers do not identify a cause.
5. Compare with controls and distribute the test across questions. Nine
   questions generating 196 pairs do not produce 196 independent observations.
6. Preserve invalidated results with their corrections identified. Two reviews
   by the same reviewers are one sample reviewed twice.

These precautions derive from [this benchmark environment's findings](findings.md);
they are not a claim that every historical experiment fully followed them.
