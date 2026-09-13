# `qwen3:14b`: English responses and reproduction of the prompt example

[Portuguese original](../../achados/ACHADO-qwen3-14b-idioma-template-2026-09-12.md) · **English** · [English index](../README.md)

Documentation date: 2026-09-12. Status: **behavior confirmed in saved data; causal mechanism not isolated**. This consolidation only inspected local files; it did not run inference or modify the production prompt.

## Result and handoff correction

`qwen3:14b` answered in English in all 15 Portuguese-prompt samples across the three step-by-step cases in the resampling. In `howto_invoice_pt`, every response starts with the invoice example from the system prompt. The evidence confirms literal reproduction in that case and an association between format and language in the sample. It does not prove that instruction priority is the sole cause.

The [starting handoff](../../history/handoff-2026-09-12.md) records “264 literal bytes” and “30/30 responses in Portuguese” for cases without `expect_steps_format`. Inspection of the [original JSON](../../../results/reamostra_pt_escalacao_1789114271.json) **does not confirm those two numbers**:

- The complete invoice example has **326 characters, 328 UTF-8 bytes**, without the final newline. Four responses are exactly that example; the fifth starts with it and adds a closing passage. No excerpt was identified in the handoff that would make its specific 264-byte claim reproducible.
- Of the other 30 responses, 15 are classified as `pt` and 15 as `tie`. The latter reproduce the 267-byte escalation block **in English**. Therefore, `lang_ok=true` in 30/30 does not mean 30/30 responses in Portuguese.

The invoice example's equality must not be extended to all three cases: the Schedule C and CSV import responses vary and adapt the steps to the task.

## Sample and provenance

Primary source: [reamostra_pt_escalacao_1789114271.json](../../../results/reamostra_pt_escalacao_1789114271.json).

SHA-256 of the verified file: `6e92ab90aaabd0ba53ccdc499fef3c4d389b15462509b7c3c5d3227e1dcc60ae`.

The [harness](../../../baseline-3080ti/repro/reamostra_pt_e_escalacao.py) records five calls per case, seeds `1000, 1017, 1034, 1051, 1068`, `temperature=0.7`, `num_ctx=8192`, `think=false`. The JSON contains 45 language records for `qwen3:14b` and 20 escalation records for `qwen3.5:9b`, with no call errors. The global `options.seed` field contains the last seed; each record preserves the seed actually used.

| `qwen3:14b` case | `expect_steps_format` | Saved detector output | Text inspection |
|---|---|---|---|
| `howto_invoice_pt` | true | 5/5 `en` | English; invoice example at the beginning of all five |
| `howto_schedule_c_pt` | true | 5/5 `en` | English; steps adapted to Schedule C |
| `howto_import_csv_pt` | true | 5/5 `en` | English; steps adapted to import |
| `plaid_trap_pt` | false | 5/5 `pt` | Portuguese |
| `payroll_trap_pt` | false | 5/5 `pt` | Portuguese |
| `greet_pt` | false | 5/5 `pt` | Portuguese |
| `escalate_stripe_broken_pt` | false | 5/5 `tie` | English; literal escalation block |
| `escalate_wrong_numbers_pt` | false | 5/5 `tie` | English; literal escalation block |
| `pricing_pt` | false | 5/5 `tie` | English; literal escalation block, inappropriate in this case |

There are **30 English responses and 15 Portuguese responses** in this sample, by inspection of the content. This is not an estimate of the production language-error rate: the nine cases were selected for investigation, with only five samples per case.

## What the prompt supports concluding

The [system prompt](../../../prompts/system_prompt.txt) places the instruction to use the customer's language under `Your Personality`. The `Response Format Rules (VERY IMPORTANT)` section says `Always` and `this exact pattern`, followed by a pattern and example in English. The invoice example is reproduced in the verified responses.

This arrangement is **consistent with the example influencing language**. There was no controlled intervention here separating example language, instruction strength, question case, and other elements. The handoff's wording “cause confirmed byte for byte” mixes the observation of equality with a causal explanation that equality alone does not establish.

The parallel with the [pricing LEAK](../../../ACHADO-qwen3-14b-pricing-leak-2026-09-04.md) is observable: literal prompt blocks reappear in responses. However, the escalation text appears both when escalation is correct and when it is inappropriate. Literal reproduction is not a sufficient detector of routing errors.

## Detector limitations found during inspection

### Language: a tie accepted as correct

In [run_chat.py](../../../run_chat.py), `detect_lang` counts a small set of textual markers; when the counts tie, it returns `tie`. `run_auto` accepts that tie for either expected language. The English escalation block produces this result and passes `lang_ok` even for Portuguese prompts. Thus, the correct detector split is **15 `en`, 15 `pt`, 15 `tie`**; reading `lang_ok` as a language classification produces the incorrect claim of 30/30 Portuguese.

This is a verified evaluator limitation, not a change applied during this documentation work. Any adjustment must preserve historical results and the version of the scoring criteria.

### Escalation: a promise not recognized by the regex

The 20 `qwen3.5:9b` records contain **1 MISS**, in `escalate_wrong_numbers_pt`, seed `1051`; the other 19 have the expected token. The record without a token says the issue needs escalation and asks for an email address to “criar um ticket de suporte” (“create a support ticket”). Nevertheless, `promete_escalar=false` and `falha_silenciosa=false`: the harness's `PROMETE` regex does not cover that wording.

`escalation_ok=false` detected the MISS. The specialized `falha_silenciosa` field missed the promise in the text; its zero does not establish the absence of a promise without a token. For `escalate_double_charge_en`, which motivated the resampling, 5/5 responses had the token in this run. That does not erase the historical occurrence reported in the harness header.

## Preserved decision and pending work

The canonical prompt remained byte-identical to the [backup preceding the attempts](../../../prompts/system_prompt.pre-fix-2026-09-04.txt), as checked during this documentation work. It was not edited: the earlier v1/v2/v3 variants had already produced incompatible results, including omitted tokens in real escalations. Ownership of the support system and the decision to change it remain with Contábil.

This document closes the pending task to **document** the finding. It was not forwarded to another agent or applied in production. Still untested through a controlled experiment: the cause of the language choice, the rate outside these cases, a fix to the language detector, and an expanded promise detector.

## How to verify without inference

The snippet below only reads JSON and text; it neither imports nor executes the inference runner.

```python
import json
from collections import Counter
from pathlib import Path

root = Path('.')  # run from the project root
data = json.loads((root / 'results/reamostra_pt_escalacao_1789114271.json').read_text())
rows = [r for r in data['registros'] if r['modelo'] == 'qwen3:14b']
prompt = (root / 'prompts/system_prompt.txt').read_text()
example = prompt.split('Example for creating an invoice:\n', 1)[1].split('\n\n## Navigation Reference', 1)[0]
invoice = [r['resposta'] for r in rows if r['id'] == 'howto_invoice_pt']
print(len(example), len(example.encode('utf-8')))       # 326, 328
print(sum(t == example for t in invoice))               # 4
print(sum(t.startswith(example) for t in invoice))      # 5
print(Counter(r['lang_detectado'] for r in rows))        # en:15, pt:15, tie:15
```
