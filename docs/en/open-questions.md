# Open questions and gaps

[Português](../pendencias.md) | **English** · [English index](README.md)

This record is derived from the [handoff](../history/handoff-2026-09-12.md),
the sources cited below, and the offline checks performed while organizing
the repository. An open question does not authorize measurements on the
production server.

| Topic | What is missing | Closure criterion |
|---|---|---|
| Phase 6b: cause of truncation | Separate hypotheses with `num_ctx=98304` and `NUM_PARALLEL=1` | Authorized window, allocation and truncation logs, actual token count, and persisted raw output; this measurement has not yet been performed. |
| Goldset and default model selection | Evaluate concentration and grouping by question in the model comparison as well | Analysis that preserves clusters and states the scope of the tie-break; nine questions do not equal 196 independent observations. |
| Speculative spill | Fix and validate the check that is blind to Gemma's target model | A detector that does not accept the 1.38 GiB from `/api/ps` as sufficient proof; the TODO remains in the harness. |
| Phase 5: programming | Resolve the execution sandbox and run the goldset | Verifiable execution result with an evaluation contract, not just a textual score. |
| Two resident models under load | Measure two models serving requests simultaneously | Dedicated scenario and artifact; Phase 6 measured one model at a time. |
| `keep_alive=5m` | Investigate its effect on the actual request pattern | Experiment measuring cold loads and latency for the target workload. |
| PT→EN | Reassess the scope of the diagnosis against the raw output | The [documented finding](findings/qwen3-14b-language-template.md) records discrepancies with the handoff; no prompt correction has been applied. |
| Language check | Examine false negatives when the detector returns `tie` | Control cases and verification against the corpus; behavior found in the PT→EN finding. |
| Support-promise detector | Examine coverage of the wording “criar um ticket de suporte” (“create a support ticket”) | Validate against complete responses and the escalation token; see [findings](findings.md). |
| Historical reproducibility | Recover unpersisted phase and disk data, if they exist | Original artifacts with provenance; do not reconstruct data from published averages. |

The [proposed `NUM_PARALLEL` discriminating test](plans/num-parallel-discriminating-test.md)
describes a future experiment. It has **not been executed** and does not resolve
the Phase 6b question.

Sources: [Phase 6b](../../results/RESULTADO-fase6b-numparallel-contexto-longo-2026-09-12.md),
[production decision](../../results/DECISAO-producao-2026-09-09.md),
[judge report](../../results/RESULTADO-juiz-familia-2026-09-10.md),
[experiment catalog](benchmarks.md).

## Completed during this organization

PT→EN received a dedicated document, the archive received an index, and the
available evidence received an integrity manifest. This does not close
experimental gaps or change model, prompt, or server decisions.
The handoff's proposed forwarding to `llm-exec` was not performed as part of
publication; there is no acknowledgment of receipt to record.
