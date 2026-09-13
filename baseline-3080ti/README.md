# Arquivo da RTX 3080 Ti

> **Organização em setembro/2026:** os relatórios e métricas da placa antiga
> permanecem arquivados, mas `repro/` também recebeu scripts usados na RTX 5090.
> Consulte o [catálogo da 5090](../docs/rtx5090/experimentos.md) antes de atribuir
> hardware ou executar um script pelo nome desta pasta.

Tudo que sobrou de mensurável da placa que serviu o Ollama do Ryzen9 até
**2026-09-04 ~02:36**, quando a RTX 5090 entrou. A 3080 Ti não está mais na
máquina: **as medições dessa placa não podem ser repetidas nesta máquina**.

Coletado em 2026-09-04, de quatro fontes que iam expirar em ritmos diferentes:
um SQLite de staging que é rotacionado, comentários de código, um scratchpad em
`/tmp`, e relatórios em um diretório `.local/` fora de versionamento.

## O que tem aqui

| Arquivo | O que é | Fonte original |
|---|---|---|
| [`baseline-3080ti.md`](baseline-3080ti.md) | **A baseline.** Throughput e latência de 2.462 chamadas em produção, o incidente de 29/08, e a query re-executável para gerar o lado 5090 do A/B | `content-insights-collector/data/local-staging.db` |
| [`runs-3080ti.csv`](runs-3080ti.csv) | Dados brutos: 3.109 runs com `prompt_eval_count`, `eval_count`, `total_duration`, status e timestamps. Só métricas — nenhum conteúdo de post | idem |
| [`tool-calling-ab-2026-09-02.md`](tool-calling-ab-2026-09-02.md) | O A/B qwen2.5 vs qwen3 (4/12 contra 12/12), a anomalia do alfabeto não-latino, e a hipótese do template que ninguém testou | comentários em `llm-gateway/src/llm_gateway/profiles.py` e `tests/test_profiles.py` |
| [`phase7-qwen3-2026-08-24.md`](phase7-qwen3-2026-08-24.md) | Validação do pipeline no dia em que os primeiros runs do CSV foram gravados: ocupação de VRAM (9,49 de 12 GiB), topologia do túnel SSH, `think=false`, volume do lote | `content-insights-collector/docs/validation/` |
| [`relatos-originais-2026-09-02.md`](relatos-originais-2026-09-02.md) | Relatos dos 4 agentes (DRE, acervo, content-insights, MFC) sobre o que quebrou e o que ficou sem investigar | scratchpad `/tmp` da sessão `43f68058-…` |
| [`reports/`](reports/) | Dois estudos de qualidade do qwen3:14b, com tokens e duração reais por run | `content-insights-collector/.local/reports/` |
| [`repro/`](repro/) | Scripts históricos de tool-calling e harnesses posteriores da RTX 5090 | scratchpad `/tmp` da mesma sessão |

### `reports/`

- `ab-qwen-sonnet-review.md` / `ab-qwen-sonnet-comparison.html` (27/08) —
  qwen3:14b contra uma leitura Sonnet, post a post, com `prompt_eval_count` /
  `eval_count` / duração por run. Encontrou um falso negativo grave (evidência
  literal que desmentia a alegação central do post, disponível e ignorada).
- `qwen-capacity-sonnet.md` / `qwen-capacity-sonnet.html` (27/08) — obediência do
  qwen3:14b a um schema JSON de 14 campos sob decoding restrito, incluindo o que
  ele ecoa em vez de sintetizar.

Ambos medem **qualidade**, não velocidade, e são a evidência mais rica que existe
do comportamento do parque de modelos na placa antiga.

## O que não existe

Um benchmark de tok/s dedicado da 3080 Ti. Foi procurado na home local inteira,
no Ryzen9 (WSL e Windows) e em 382 transcripts de sessão. O
[`../README.md`](../README.md) registra o motivo: foi feito em **25/03/2026** numa
sessão de chat, nunca salvo, sessão perdida — e o histórico local só retém desde
30/06/2026. A busca completa, com os falsos positivos encontrados, está em
[`baseline-3080ti.md`](baseline-3080ti.md).

## Ressalva que atravessa tudo

O `tok/s` da baseline é `eval_count / total_duration`, e `total_duration` inclui
o prefill de ~2.100 tokens. **Subestima** a geração pura e **não** é comparável
com `../results/bench_*.json`, que usa `eval_duration`. Comparar as duas colunas
diretamente produz um número errado — a query re-executável existe justamente
para não precisar disso.
