# llm-bench

Medição dos LLMs locais do home lab — o Ollama do **Ryzen9**, único servidor do
parque, consumido por content-insights-collector (direto), Khronos/DRE,
miqueias/MFC e acervo (via `llm-gateway`).

> **Onde o servidor roda (desde 2026-09-04):** Windows nativo, como tarefa
> `OllamaServer` do SYSTEM que sobe no boot. Saiu do WSL2 depois de um A/B medir
> ~14% a mais de decode. Endereço inalterado (`…:11434` na LAN e na tailnet).
> Runbook: [`MIGRACAO-windows-nativo-2026-09-04.md`](MIGRACAO-windows-nativo-2026-09-04.md).

Três coisas convivem aqui, com propósitos diferentes:

| O quê | Mede | Como roda |
|---|---|---|
| **`run_chat.py`** + `goldset_chat.json` + `prompts/` | **Qualidade** — 18 casos PT/EN com auto-checks (escalação por token exato, anti-alucinação, grounding, idioma, formato) | `python3 run_chat.py`, fala com `OLLAMA_URL` |
| **`bench.py`** | **Velocidade** — tok/s de geração pura por modelo | `python bench.py [modelo...]` |
| **`bench_engine_ab.py`** | **A/B entre dois endpoints** — WSL vs nativo, runner vs runner, config vs config | `ENDPOINT_A=… ENDPOINT_B=… python3 bench_engine_ab.py` |
| **[`baseline-3080ti/`](baseline-3080ti/)** | **Arquivo histórico** da placa anterior — não é executável | leitura |

## Histórico de GPU desta máquina

RTX 2080 Ti 11 GB → RTX 3080 Ti 12 GB → **RTX 5090 32 GB** (trocada em
**2026-09-04 ~02:36**). A 3080 Ti não está mais disponível fisicamente: nada dela
pode ser re-medido, e tudo que sobrou está congelado em
[`baseline-3080ti/`](baseline-3080ti/).

Um benchmark de tok/s comparando 3080 Ti e MacBook Pro M5 Pro foi feito numa
sessão de chat em **25/03/2026**, mas nunca foi salvo em arquivo e a sessão foi
perdida. O `bench.py` existe para que isso não se repita: resultado versionado,
método fixo, sempre em `results/`.

## `run_chat.py` — qualidade

Harness do agente de suporte "Lana" (projeto Isafi/contábil). Stdlib pura. Manda
o system prompt real de produção + cada caso do gold set e aplica auto-checks
objetivos por resposta; `auto_score` é a fração aprovada.

```bash
MODELS_OVERRIDE="qwen3:14b,qwen3.5:9b" THINK=false OUT_SUFFIX=".gpu5090" \
  OLLAMA_URL=http://100.88.95.78:11434 python3 run_chat.py
```

| Variável | Efeito |
|---|---|
| `MODELS_OVERRIDE` | lista de modelos, separada por vírgula |
| `THINK` | `false` desliga o bloco de raciocínio dos modelos "thinking" |
| `OUT_SUFFIX` | sufixo dos arquivos de saída, para não sobrescrever runs |
| `OLLAMA_URL` | default `http://localhost:11434` |

Saídas: `results/chat_raw<suffix>.json` (respostas cruas + métricas + auto-checks)
e `results/chat_table<suffix>.md` (resumo).

O relatório consolidado das runs de CPU (i7-14700KF, maio/2026) vive no projeto
de origem, em `~/Devs/contabil-ollama/llm-bench/results/RELATORIO_CONSOLIDADO.md`.
Nunca rodou em GPU.

## `bench.py` — velocidade

```bash
python bench.py                    # todos os modelos instalados no Ollama
python bench.py qwen3:8b llama3.2  # só modelos específicos
```

Cada modelo roda 3 prompts fixos × 2 vezes contra `/api/generate`, e calcula
`eval_count / eval_duration` — **geração pura**. Resultado bruto em
`results/bench_<timestamp>.json`, junto com nome/VRAM/driver da GPU.

Limitações conhecidas, que importam na hora de comparar:

- Os prompts têm ~26 tokens, então a coluna de `prompt_tok_s` **não é** throughput
  de prefill — é overhead fixo. Ignore-a.
- A primeira run de cada modelo pode incluir o load na VRAM (`wall_s` alto).
- Sem system prompt e sem gold set: mede velocidade, não qualidade.

## `results/`

| Arquivo | O quê | Hardware |
|---|---|---|
| `RESULTADO-wsl-vs-windows-2026-09-04.md` | **WSL2 custa ~14% no decode; runner cuda_v12 vs v13 empata** — leitura dos dois A/B abaixo | RTX 5090 |
| `engine_ab_20260904_145228.*` | A/B WSL2 vs Windows nativo | RTX 5090 |
| `engine_ab_20260904_145334.*` | A/B cuda_v12 vs cuda_v13, ambos no Windows | RTX 5090 |
| `bench_20260904_043001.json` | primeira run de tok/s na placa nova | RTX 5090 |
| `chat_raw.gemma4.json` / `chat_table.gemma4.md` | cross-check do gemma4:26b no harness canônico | i7-14700KF, CPU-only |
| `chat_table.gpu5090-baseline.md` / `chat_raw.gpu5090-baseline.json` | **Fase 0 — a régua de qualidade oficial** (18 casos × 3 modelos, prompt canônico) | RTX 5090 |
| `chat_table.gpu5090-postfix.md` / `chat_raw.gpu5090-postfix.json` | ⚠️ **não é régua válida** — rodado com um system prompt experimental (v2) revertido no mesmo dia por regredir o token de escalação. Arquivado só como evidência; ver `ACHADO-qwen3-14b-pricing-leak-2026-09-04.md` | RTX 5090 |

## Documento de referência

[`rtx5090-modelos-parametrizacao.md`](rtx5090-modelos-parametrizacao.md) — o que
passa a caber em 30 GiB de VRAM, o que realmente muda o número na Blackwell
(separando medido de folclore), e o plano de medição em fases sobre este harness.
Inclui o estado atual da unit do Ollama e as três coisas que mudaram sozinhas com
a troca de placa.

[`SESSOES.md`](SESSOES.md) — índice das sessões de chat por trás deste diretório,
com os comandos de resume e a janela de retenção do histórico local (só desde
30/06/2026; o que ficou de fora está listado lá).
