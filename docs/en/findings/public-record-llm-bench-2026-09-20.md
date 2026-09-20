# Public findings record — llm-bench

**Cutoff date:** 2026-09-20

**Primary bench:** Ryzen9/WSL Arch CUDA with a 32 GB RTX 5090
**Objective:** evaluate local models and runtimes for use in the LLM stack, with special attention to a guardian that reads pane buffers and artifacts, summarizes and ranks candidates, and has no authority to act.

> This document is a human-readable synthesis and a context aid for future conversations. It does not replace hash-addressed artifacts. When sources conflict, the raw result and the execution-specific record take precedence.

## 1. Executive summary

The work produced five main conclusions:

1. **The fastest model is not automatically the right model.** High throughput can mean that a model spent its entire token budget thinking and never produced a usable answer. The test battery therefore separates speed, completion, and contract adherence.
2. **The runtime is part of the result.** A model can load without an error and still compute incorrectly. This happened with Bonsai on the Codacus fork: the file loaded, but perplexity reached hundreds of thousands; the same model produced healthy PPL on the Prism fork.
3. **Instrumentation was the largest early risk.** Several T87 rounds measured incomplete preparation, remote sandbox failures, permissions, response-channel handling, or an inadequate token cap rather than model capability. Those results were excluded rather than reinterpreted as quality.
4. **A hybrid guardian architecture is safer:** a deterministic collector performs triage and gathers evidence; an LLM without tools, writes, callbacks, or interruption authority may summarize and rank; deterministic rules remain the only authority that notifies the human.
5. **Typed logprob decisions are a promising route for closed choices.** The Coder and the no-think a3b returned distributions over one-letter options. This measures mechanics, cost, and concentration, not accuracy: the packets used had no gold labels.

The project **has not selected a production candidate**. The initial criterion “code understanding better than qwen3-14b” was withdrawn by the owner before it could be validly measured; it must be replaced by an approved rejection criterion.

## 2. What was evaluated

llm-bench began as a test bench for the question: “Can a local model enter our stack?” The question was refined during the work:

- for general benchmarks, loading, speed, quality, and behavior must be measured separately;
- for the guardian, the question is whether a model can read buffers and artifacts, produce an auditable classification or summary, and operate continuously;
- the guardian model **receives no tools, does not write, execute commands, or interrupt the human**;
- evidence, state, listeners, PIDs, and observable transitions come from the collector and rules;
- the LLM may interpret, summarize, and rank, while the external decision remains deterministic.

This separation matters: generating attractive JSON does not grant operational authority.

## 3. How to read the results

Every claim must be read together with four dimensions:

| Dimension | Examples | Why it matters |
|---|---|---|
| artifact | GGUF, shard, Ollama blob, prompt | different files are not the same experiment |
| runtime | Ollama, Codacus/llama.cpp, PrismML/llama.cpp | the same model can load or compute differently |
| route/context | LAN, tailnet, SSH forward, Windows/WSL session | latency and GPU access change with route and session |
| configuration | offload, `-ngl`, `--cpu-moe`, `--n-cpu-moe`, `--load-mode`, context, sampling | moving weights changes output and throughput |

Therefore a correct `series_key` includes, at minimum, runtime, commit/binary, artifact hash, route, offload configuration, context, prompt, schema, harness version, and the parameters actually sent. Series with different keys must not share averages, trends, or dispersion estimates.

### Provenance used in this record

- **observed/canonical:** manifest, request/response, log, and hash available in the workspace;
- **derived:** a reproducible calculation from observed artifacts;
- **weak:** an owner-supplied SSH/curl report without a complete manifest;
- **invalidated:** an execution that did not satisfy the experiment contract;
- **unknown:** the data was not observed; this is not permission to fill the gap by inference.

Measurement provenance and public availability are separate axes. Some numbers below were canonical inside the bench, but their manifests, logs, and raw responses are not part of this first bundle. They are marked `observed internally; public artifact absent` and are not publicly reproducible benchmarks.

## 4. Condensed timeline

### 4.1 T87 P1: from experiment to experimental hygiene

P1 was intended to test the stability of a 17-task suite. The campaign passed through several versions because each attempt exposed a preparation failure:

1. the remote sandbox exited before its marker; the harness did not capture exit code, signal, or stderr, so the original cause remained `unknown`;
2. the `flask` dependency was missing; the agent encountered a laboratory obstacle rather than the task's intended trap;
3. the agent gained access to private solution and answer artifacts in the protected checkout; that round was invalidated;
4. the grader was invoked through the wrong path and an orphaned `app.py` held port `5000`, causing a timeout;
5. response classes and token limits needed to be recorded explicitly by the harness.

The laboratory became valid only in the protected series: the checkout was outside the measured user's reach, dependencies were frozen, the execution user could not access the answer key, reset was privileged through a narrow rule, and the grader used the correct Python environment. The owner then ended the campaign before the remaining 92 generations were spent.

Closure was an owner-approved decision on 2026-09-19 for campaign `t87-p1-harness-v8`. The conclusion is limited to the pair `(harness-v8, qwen3.6-35b-a3b)` and is not a general model verdict. The series did not produce the five homogeneous runs required to estimate dispersion; partial scores are not a final statistic.

### 4.2 Response-channel correction

Transcripts showed empty `content`, populated `reasoning_content`, and present `tool_calls`. Harness v9 records channel classes and treats `tool_calls` as the only action source. `reasoning_content` is never promoted to a command. V9 was implemented, but the owner-approved closure did not authorize spending the returned generations again.

The methodological detail is essential: for reasoning models, empty `content` can mean a separate action channel or a token-budget truncation. Without `finish_reason`, `tool_calls`, and token counts, the cause cannot be assigned to the model.

## 5. Infrastructure lessons

### 5.1 GPU, session, and daemon

Two Ollama instances existed on the Windows machine. The Session 0 daemon held port `11434` and loaded on CPU (`size_vram=0`); the interactive-session instance regained access to the RTX 5090 after the repair. The version also changed from 0.33.3 to 0.34.2 and the CUDA runner libraries were restored.

**Rule:** `/api/version`, `/api/tags`, and `health=200` do not prove that a model is resident on the GPU. Always record `GET /api/ps`, `nvidia-smi`, PID, session, listener, VRAM, RAM, and flags.

### 5.2 LAN, tailnet, and SSH forwarding

There were two routes to the Ryzen9 machine. LAN was preferred for P1 to reduce noise; tailnet remains relevant when the question is production latency. The dedicated llama.cpp endpoint and route must be part of the series without publishing private addresses.

When direct LAN access was unavailable in a context, the harness used SSH forwarding. That preserved the client's local contract, but it does not make latency from one route equivalent to latency from another.

### 5.3 CUDA and builds

The new distro had only CUDA 13.4 (`libcudart.so.13`); the old binary depended on CUDA 12 and could not run in that environment. Rebuilding with `CMAKE_CUDA_ARCHITECTURES=120a-real`, Flash Attention, and CUDA graphs was preferable to mixing libraries and creating an ambiguous runtime series. On a 32-core machine, `-j24` reduced the Codacus build from hours of estimated time to roughly six minutes.

The Prism build was kept separate. The Prism fork is required for PrismML/Ternary Bonsai artifacts; the Codacus fork supports qwen4exp for Flash-Next but must not be used to calculate Bonsai perplexity.

### 5.4 WSL storage

`/` inside WSL showed the VHDX growth ceiling rather than the host's physical free space. Copying 53.8 GB into the distro filesystem inflated the VHDX. The file was removed; large GGUFs and logits belong on a host-mounted directory. Check host-mounted filesystems for real free space instead of relying only on the virtual filesystem ceiling.

Moving the Bonsai F16 from the host mount to the native WSL filesystem reduced load time but did not improve chunk time:

| Configuration | Chunk time |
|---|---:|
| `-ngl 20`, host mount | 27.74 s |
| `-ngl 24`, host mount | 25.66 s |
| `-ngl 24`, distro filesystem | 25.99 s |

The result does not support declaring drvfs the calculation bottleneck from this swap. The working interpretation is repeated rereading of a 53.8 GB model with only 47 GB of RAM; it is not a universal proof.

## 6. Candidates, runtimes, and measurements

### 6.1 Overview

| Candidate | Artifact | Runtime | Quality/contract result | Recorded speed |
|---|---|---|---|---:|
| Qwen3-Coder 30B-A3B | UD-Q5_K_XL, 21.74 GB | Codacus | 2/5 valid in each of four T1/T2 phases; all completed | 267.86 tok/s warm median |
| Qwen3.6-35B-A3B | Q4_K_M, Ollama blob 21.72 GB | Codacus | T1 unconstrained 4/5; T2 0/5 with a 2048 cap; no-think was separate | 233.30 tok/s with reasoning; observed internally, public artifact absent |
| Qwen3.8-27B | UD-Q5_K_XL, 20.88 GB | Codacus | T1 unconstrained 5/5; T2 unconstrained 0/5; GBNF pending on a residual GPU gate | 63.77 tok/s weak; non-canonical |
| Ternary Bonsai 2 | PTQ1_0, 5.95 GB | PrismML | T1 unconstrained 4/5; GBNF 0/5 in `content`, 3/5 in reasoning | approximately 121.3 tok/s weak; non-canonical |
| Flash-Next | UD-IQ3_XXS, 3 shards, 81.96 GB | Codacus | loads and completes, but outside evaluation scope | 16.18 `--cpu-moe`; 26.98 `--n-cpu-moe 32`, weak provenance |

The speed values do not all have the same formal status. Canonical measurements use a manifest, hashes, a discarded warm-up, and the median of three warm generations. Values explicitly marked weak came from SSH/curl without a complete manifest and are historical only. Public-artifact absence is reported separately and does not automatically change the measurement provenance inside the bench.

### 6.2 Qwen3-Coder 30B-A3B

The numbers in this subsection were observed internally with a structured protocol; the corresponding public artifact is not part of this release.

- GGUF: `21,740,305,568` bytes;
- SHA-256: `eb331a4eee8eb6b5a8eb25f44f96f45c71b8d10f553c0a456190dd590a7ef77d`;
- T1 unconstrained, T2 unconstrained, T2 GBNF, and T1 GBNF: `2/5` valid responses in each phase;
- five of five requests ended with `stop` in each phase;
- speed: warm-up `261.89`; warm `265.14 / 267.86 / 270.78`; median `267.86 tok/s`;
- speed-measurement output: 885 tokens, `stop`, populated `content`.

The Coder had the strongest structural behavior in this battery, but `2/5` is not a promotion criterion. The owner-facing acceptance criterion must be defined before selecting a candidate.

### 6.3 Qwen3.6-35B-A3B

With reasoning enabled, the model was very fast, but all four throughput-probe calls with `max_tokens=2048` ended with `length`, empty `content`, and populated reasoning. This does not prove that the model cannot complete; it proves that the selected cap was insufficient for that task.

A separate test used `chat_template_kwargs: {"enable_thinking": false}`. It must be treated as a separate series: disabling reasoning is a model/runtime configuration and cannot be mixed with the normal series. The numerical detail of that smoke test is not claimed in this publication because its artifact is not in the public bundle.

### 6.4 Qwen3.8-27B

T1 with `max_tokens=8192` finished `5/5`, showing that a 2048 cap was not a fair basis for evaluating completion. The earlier weak 63.77 tok/s measurement used only a few calls and no formal cold/warm protocol; it must not be used as an operational number.

### 6.5 Ternary Bonsai 2

Bonsai showed why quality and speed must remain separate. The older approximately 121 tok/s measurement with a 2048 cap ended by `length`; T1 with 8192 completed `4/5` in unconstrained mode. With GBNF, all five calls stopped, but three valid objects appeared only in `reasoning_content`; the correct consumer kept `content` as the canonical channel and counted zero contract-valid responses.

The GBNF condition was applied during server initialization, but the public artifact does not record that property. The observation is therefore internal with indirect evidence; a future reproduction must record the active grammar with the result. This does not mean that the model “cannot produce JSON”; it shows that grammar can guarantee form in a channel the consumer cannot accept as an action.

### 6.6 Flash-Next

Flash-Next loaded with `--cpu-moe`, completed a response, and produced 16.18 tok/s warm; `--n-cpu-moe 32` produced 26.98 tok/s warm. Offload changed the output even with the same seed and temperature; offload therefore belongs in the `series_key`.

It was removed from evaluation scope by owner decision: 33–44 GB of RAM use, an approximately 82 GB mmap on host-mounted storage, long load time, dependence on the Codacus fork, and measurements taken with the machine idle. In addition, the local artifact (177B/qwen4exp) was not proven to be the same model as the historical scorecard that mentioned 125B/17/17. The artifact was retained as historical reference for a large-model class, not as a reproduction of that scorecard.

## 7. Critical finding: KL and the PrismML runtime

### 7.1 The silent error

The first Bonsai F16 was processed by Codacus `llama-perplexity`. The file loaded without an error, but PPL was absurd:

- Codacus, common-text control: `1,165,154.2284`;
- Codacus, internal corpus, 100 chunks: `838,794.2256`.

The same F16 on the Prism binary produced `1.1045` on the short control and `5.4163` on one chunk of the internal corpus. The proven cause is silent runtime incompatibility: for PrismML models, loading is insufficient; computation must be checked with the correct fork.

The common-text control was repetitive and must not be cited as “Bonsai PPL.” It served only to distinguish the incorrect runtime from the correct one.

### 7.2 Valid within-bench base and quantization curve

The numbers in this subsection were calculated on the bench and are retained as internal reference; the corpus and raw artifacts are not part of this public release.

With Prism, the 100-chunk F16 base over the internal operational-artifact corpus produced `PPL = 6.0012 ± 0.04775`. The base logits file is `50,807,909,620` bytes; the reference F16 is `53,808,408,928` bytes. These sizes identify different files and must not be confused. The corpus is not published, so the curve is reproducible only inside the bench. External verification requires rebuilding the base with a public corpus, knowing that absolute values will change.

Comparisons against the same Prism base:

| Quantization | Size | Mean KLD | Median | p99 | p99.9 | Same top-p |
|---|---:|---:|---:|---:|---:|---:|
| PTQ1_0 | 5.95 GB | 0.000368 ± 0.000020 | 0.000184 | 0.001760 | 0.015705 | 98.630% |
| PQ2_0 | 7.21 GB | 0.000385 ± 0.000020 | 0.000183 | 0.001725 | 0.016675 | 98.593% |

Correct reading: PTQ1_0 and PQ2_0 preserve the ternary weights represented by F16 very closely. This is **storage fidelity**, not evidence of Bonsai merit against a dense model. PQ2_0 showed no material gain that justified 1.26 GB extra; PTQ1_0 is the more economical choice for this model.

The exact fraction of tokens above `0.01` nats is `unknown`: the binary published quantiles, not a per-token count. That percentage must not be invented from p99.

## 8. What the guardian test actually measured

The frozen packet contains five real rounds, but `labels_loaded=false`. T1/T2 therefore measure completion and mechanical contract adherence, not accuracy.

Schema v1 requires `agent_session`, `suggested_state`, `abstain`, `evidence`, `confidence`, and `escalation_requested`. Evidence must resolve to a file and excerpt; confidence has operational bands (`low`, `review`, `high`) but is heuristic. The model does not execute the action.

Two limits are explicit:

- GBNF/JSON Schema can produce valid JSON in the reasoning channel, which the consumer must reject;
- a valid coordinate/path does not prove semantic relevance of the excerpt; that dimension remains unmeasured.

Current measurements do not authorize claiming that a model correctly detects `stalled`, `correction-in-progress`, or any other class. That requires a labeled corpus, independent labels, and an owner-approved threshold.

## 9. Typed decisions through logprobs

An independent typed-decision probe was created and executed. It uses five one-letter options (`A`–`E`), because words such as `correction-in-progress` may use multiple tokens. Token IDs were checked before using the probability mass.

The protocol used `max_tokens=1`, `temperature=0`, `seed=42`, `logprobs=true`, and `top_logprobs=10`, with four questions for each packet: state, need for attention, escalation, and confidence.

The probe's numerical results remain outside this first bundle because the packets and raw JSON contain private material. Without a hash-addressed public bundle, no public latency or entropy table is claimed.

The result demonstrates mechanics and cost, not correctness. There were no gold labels. It also does not solve literal evidence: a typed decision must receive its evidence from the deterministic collector. Raw numbers and packets remain outside this public bundle.

## 10. Invalidated, historical, and open work

### Do not use as a verdict

- T87 results from runs with an accessible suite, missing dependencies, or an incorrect grader;
- partial P1 scores as a final dispersion estimate;
- Codacus Bonsai PPL as model quality or as a KL base;
- speed measured with concurrent build/download activity without explicit marking;
- throughput under `max_tokens=2048` as proof that a model cannot complete;
- comparisons across different runtimes, routes, artifacts, or offload settings as if they isolated one variable.

### Retained as historical reference

- Flash-Next and its two offload configurations;
- owner-supplied SSH/curl values without a manifest;
- the attempt to copy F16 into the distro filesystem, retained as a negative optimization experiment and storage lesson;
- P1 attempts that exposed laboratory failures.

### Real open items

1. replace the removed “better than qwen3-14b” criterion with an owner-approved rule; the model remains available as a possible operational baseline but is no longer this campaign's ruler;
2. decide whether the guardian will use typed decisions, structured generation, or a hybrid composition;
3. build an independently labeled corpus to measure accuracy, abstention, and false positives;
4. repeat only the measurements needed with a complete `series_key`;
5. specify operational p95: cold-event types, cadence, machine load, and sample count;
6. measure evidence semantic relevance without promoting valid coordinates into proof of pertinence;
7. determine whether and when a3b no-think is acceptable for the closed-choice role.

## 11. Publication and reproduction boundary

This is a self-contained public document. Packets, transcripts, manifests derived from internal Herdr state, raw responses, internal metrics, and local paths are not automatically published because they may contain usernames, private addresses, pane content, or review material not intended for GitHub.

The evaluation code and typed probe remain outside this first public commit while they undergo sanitization and contract review. The bundle also does not include the initialization property that would externally prove that GBNF was active; that field must be recorded in a future reproduction.

A future reproduction should publish a hash-addressed bundle with artifact, binary, flags, a public form of the route, prompt, schema, sampling, environment, cache state, and per-field provenance. Without that bundle, values marked weak remain historical and must not be treated as canonical public benchmarks.

## 12. Current conclusion

The work did not end with “model X won.” It delivered what is needed for a reliable decision:

- a protected laboratory and a taxonomy of invalid results;
- evidence that runtime and configuration change outcomes;
- a quantization-fidelity curve for Bonsai against its own F16 representation;
- an initial comparison of completion and structural behavior across candidates;
- a typed-decision alternative that reduces channel, truncation, and parsing risks;
- an operational separation between deterministic collection, LLM interpretation, and action authority.

The correct next step is to fix the acceptance rule, freeze the labeled packet, and only then measure the candidate that best fits the actual role.
