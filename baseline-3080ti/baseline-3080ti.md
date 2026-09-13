# Baseline RTX 3080 Ti — congelada em 2026-09-04

A RTX 3080 Ti (12 GB) foi substituída por uma RTX 5090 (32 GB) no Ryzen9WSL em
**2026-09-04, por volta de 02:36** (primeira aparição da placa nova no journal do
`content-insights-ollama.service`). **A placa antiga não está mais na máquina** —
nenhum número desta baseline pode ser re-medido. Este arquivo existe para
preservar o que dá para saber sobre ela antes que as fontes rolem.

## Não existe benchmark de tok/s dedicado da 3080 Ti

Procurado em 2026-09-04 e **não encontrado**:

- toda a home local (`find` por `*bench*` + grep por `eval_count`/`tok/s`/`tokens/s`
  em `~/Devs`, `~/Projects`, `~/Documents`, `~/Downloads`, `~/Work`);
- o Ryzen9 inteiro — home do WSL **e** lado Windows (`Desktop`, `Devs`,
  `Documents`, `OneDrive`);
- 382 transcripts de sessão via `search-sessions --deep`.

O `README.md` deste repositório (escrito em 2026-09-04 04:06 no Ryzen9) registra
o motivo: um benchmark 3080 Ti vs MacBook Pro M5 Pro foi feito em **25/03/2026**
numa sessão de chat, **nunca salvo em arquivo, sessão perdida**. O transcript
mais antigo retido localmente é de **2026-06-30** — março está fora da janela.

Falsos positivos, para ninguém procurar de novo:

| Arquivo | O que é de verdade |
|---|---|
| `contabil/docs/Benchmark.md` (e 2 cópias) | comparativo de produto vs Wave Accounting |
| `Instructions/MEMORY_BENCHMARK_METHODOLOGY.md` | uso de RAM, Linux vs macOS |
| `acervo/.../benchmark_plan_layout_proposals.py` | qualidade de layout urbanístico |
| `acervo/docs/plans/01-initial-plan.md:88` — "~50 tok/s" | estimativa de planejamento, não medição |

## O que existe: 2.462 chamadas reais em produção

Não é um benchmark sintético — é telemetria do Ollama gravada pelo pipeline do
**content-insights-collector**, que consome o Ollama do Ryzen9 direto. Fonte:
`~/Devs/content-insights-collector/data/local-staging.db`, tabela `analysis_runs`.
O banco parou de escrever em **2026-08-31**, três dias antes da troca de placa —
**todo run nele é 3080 Ti**.

Dados brutos congelados aqui: [`runs-3080ti.csv`](runs-3080ti.csv) (3.109 runs,
inclusive os que falharam).

### Throughput e latência (só `status='succeeded'`)

| Modelo | Tarefa | n | prompt méd. | saída méd. | **tok/s med.** | p5 | p95 | wall med. | wall p95 | wall máx |
|---|---|---|---|---|---|---|---|---|---|---|
| qwen3:14b | triage | 1688 | 2086 | 127 | **63,9** | 24,3 | 70,1 | 1,90 s | 5,71 s | 99,2 s |
| qwen3:8b | verification | 538 | 2129 | 144 | **100,5** | 24,8 | 112,2 | 1,43 s | 5,29 s | 19,6 s |
| qwen3:14b | opportunity_probe | 236 | 2183 | 975 | **68,0** | 23,8 | 69,2 | 14,45 s | 39,52 s | 44,7 s |

> **Ressalva metodológica — leia antes de comparar.** O `tok/s` acima é
> `eval_count / total_duration`, e `total_duration` **inclui o prefill** dos
> ~2.100 tokens de prompt (e eventual load do modelo). Portanto **subestima** a
> velocidade de geração pura. Não é comparável 1:1 com `results/bench_*.json`,
> que usa `eval_count / eval_duration`. Para um A/B honesto contra a 5090,
> re-execute **esta mesma fórmula** sobre runs novos do mesmo pipeline — a query
> está no fim deste arquivo.

O p5 de ~24 tok/s nos três casos, contra medianas de 64–100, mostra uma cauda
pesada consistente: é o custo de recarga com `OLLAMA_MAX_LOADED_MODELS=1`, com
quatro projetos disputando o mesmo servidor.

### Taxa de erro por dia — o incidente de 29/08

| Dia | qwen3:14b HTTP 500 / total | qwen3:8b HTTP 500 / total |
|---|---|---|
| 24/08 | 0 / 500 | 0 / 141 |
| 25/08 | 0 / 673 | 0 / 159 |
| 26/08 | 0 / 18 | — |
| 27/08 | 0 / 167 | 0 / 45 |
| 28/08 | 0 / 2 | — |
| **29/08** | **600 / 924 (64,9%)** | **26 / 132 (19,7%)** |
| 30/08 | 0 / 146 | 0 / 74 |
| 31/08 | 0 / 106 | 0 / 22 |

Os 626 `Ollama HTTP error 500` do conjunto inteiro caem **todos** em 29/08. Zero
nos outros sete dias. E 29/08 05:48 é exatamente quando o
`content-insights-ollama.service` foi iniciado pela primeira vez na unit atual
(o journal do serviço começa nesse timestamp, ainda com o hostname antigo
`Ryzen5WSL`).

**Leitura:** isso é assinatura de um incidente de infraestrutura — a
reinstalação/migração do Ollama —, não uma característica da 3080 Ti. Não use os
64,9% como "taxa de erro da placa antiga". Os outros erros do período são de
validação de schema no lado do coletor (`relevance must be between 0 and 1`,
`programming.llm_workflow requires uses_llm=true`), não do servidor.

## Ocupação de VRAM — o aperto que justificou a troca

De [`phase7-qwen3-2026-08-24.md`](phase7-qwen3-2026-08-24.md), a validação do
pipeline no mesmo dia em que os primeiros runs do CSV foram gravados:

> GPU remota confirmada: NVIDIA GeForce RTX 3080 Ti, 12 GiB. […] Smoke real do
> Qwen3 14B: `size_vram=10190879872` e uso observado de 91% da GPU.

São **9,49 GiB residentes de 12 GiB — 79% da VRAM** com um único modelo carregado
(os 91% do texto são utilização do processador da GPU, métrica diferente; não
confundir). Sobravam ~2,5 GiB para KV cache e buffers, e era isso que forçava
`OLLAMA_MAX_LOADED_MODELS=1` com três modelos em rodízio.

Para comparação, a mesma medida na 5090: 30,2 GiB utilizáveis, com o Ollama
elevando o contexto default de 4k para 32k sozinho ao cruzar os 24 GiB. Ver
[`../rtx5090-modelos-parametrizacao.md`](../rtx5090-modelos-parametrizacao.md).

O documento também registra o resto da topologia da época: túnel SSH
`127.0.0.1:11435 → 192.168.0.125:11434`, `think=false` no adapter
(`ollama-adapter-v2-no-thinking`), e o volume do lote — 480 leituras primárias
com `qwen3:14b` e 137 com `qwen3:8b`.

## Corroboração independente da cauda de latência

O p5 de ~24 tok/s tem uma segunda testemunha, de outro projeto e outra sessão.
De `acervo/backlog/tasks/task-97` (piloto de zoneamento, 2026-09-01):

> Investigada suspeita de GPU lenta antes de só aumentar timeout (pedido
> explícito do usuário): `nvidia-smi` + `journalctl` confirmaram RTX 3080
> Ti/CUDA carregando normalmente (**1-4% de uso durante as chamadas**) — causa
> provável é fila de concorrência (`OLLAMA_NUM_PARALLEL=1` num serviço
> compartilhado) mais prompts reais maiores que os de teste, não bug de
> GPU/modelo. Timeouts subidos por decisão do usuário: Ollama 60s→120s.

Uma GPU a 1–4% de utilização enquanto a chamada demora é a assinatura de
**espera na fila**, não de placa lenta. Isso e a cauda p5 desta baseline são o
mesmo fenômeno visto por dois ângulos — e é o argumento mais forte para revisar
`MAX_LOADED_MODELS` agora que há 30 GiB.

O mesmo arquivo registra que o Ollama do Ryzen9 já foi encontrado inalcançável
por estar ligado só em `127.0.0.1`, contornado com túnel SSH em vez de editar a
unit compartilhada — contexto útil para quem for mexer nela.

## Query re-executável

Roda contra qualquer banco do coletor. Para gerar o lado 5090 do A/B, aponte para
o banco atual depois de acumular runs na placa nova.

```bash
sqlite3 -readonly -header -column data/local-staging.db "
WITH m AS (
  SELECT model, analysis_kind,
         json_extract(response_json,'\$.metadata.prompt_eval_count') AS pe,
         json_extract(response_json,'\$.metadata.eval_count')        AS ev,
         json_extract(response_json,'\$.metadata.total_duration')/1e9 AS wall
  FROM analysis_runs
  WHERE provider='ollama' AND status='succeeded'
    AND json_extract(response_json,'\$.metadata.total_duration') > 0
), r AS (
  SELECT *, ev/wall AS toks,
         ROW_NUMBER() OVER (PARTITION BY model, analysis_kind ORDER BY ev/wall) rn,
         COUNT(*)    OVER (PARTITION BY model, analysis_kind) n
  FROM m
)
SELECT model, analysis_kind, n,
  ROUND(AVG(pe),0) prompt_med, ROUND(AVG(ev),0) out_med,
  ROUND(MAX(CASE WHEN rn=n/2       THEN toks END),1) tok_s_med,
  ROUND(MAX(CASE WHEN rn=n/20      THEN toks END),1) p5,
  ROUND(MAX(CASE WHEN rn=n*19/20   THEN toks END),1) p95
FROM r GROUP BY model, analysis_kind, n ORDER BY n DESC;"
```

Percentis de latência precisam de ordenação própria — ordenar por `tok/s` e ler
`wall` na mesma linha dá número enganoso:

```bash
sqlite3 -readonly -header -column data/local-staging.db "
WITH m AS (
  SELECT model, analysis_kind,
         json_extract(response_json,'\$.metadata.total_duration')/1e9 AS wall
  FROM analysis_runs
  WHERE provider='ollama' AND status='succeeded'
    AND json_extract(response_json,'\$.metadata.total_duration') > 0
), r AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY model, analysis_kind ORDER BY wall) rn,
            COUNT(*)    OVER (PARTITION BY model, analysis_kind) n
  FROM m
)
SELECT model, analysis_kind, n,
  ROUND(MAX(CASE WHEN rn=n/2     THEN wall END),2) wall_mediana,
  ROUND(MAX(CASE WHEN rn=n*19/20 THEN wall END),2) wall_p95,
  ROUND(MAX(wall),2)                               wall_max
FROM r GROUP BY model, analysis_kind, n ORDER BY n DESC;"
```

## Para comparar com a 5090

O `bench_20260904_043001.json` (primeira run na placa nova, `results/`) mede
**geração pura** com prompts de ~26 tokens — outra métrica, outro workload:

| Modelo | 5090, `eval_count/eval_duration` | 3080 Ti, `eval_count/total_duration` |
|---|---|---|
| qwen3:14b | 127,9 tok/s | 63,9 (triage) · 68,0 (probe) |
| qwen3:8b | 197,8 tok/s | 100,5 (verification) |

As duas colunas **não são o mesmo número** — a da direita carrega o prefill de
~2.100 tokens no denominador, a da esquerda não. A razão entre elas (~2,0×) é um
limite inferior grosseiro do ganho, não a medida dele. O A/B legítimo exige
rodar a mesma fórmula nos dois lados.
