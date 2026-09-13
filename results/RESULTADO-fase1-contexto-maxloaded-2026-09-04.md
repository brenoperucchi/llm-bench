# Fase 1 — contexto × MAX_LOADED_MODELS × KV cache — RTX 5090, 2026-09-04

7 configs testadas na tarefa `OllamaServer` (Windows nativo). Measure A do
plano (alternância dentro da janela de `keep_alive`, lida via `ollama ps`) —
é essa medida que discrimina `MAX_LOADED_MODELS`, não a de >5min ociosidade
(que testa só `keep_alive` e ficou fora do escopo desta rodada por custo de
tempo).

## Resultado por config

| # | ctx | MAX | KV | Modelos | VRAM total | 2ª passada | Veredito |
|---|---|---|---|---|---|---|---|
| 1 (produção antes) | 32k auto | 1 | f16 | 14b+9b | — | despejo a cada troca (0,4–4,2s load) | baseline confirmado |
| 2 | 8192 | 1 | f16 | 14b+9b | — | idem, mesmo padrão | contexto sozinho não resolve nada |
| 3 | 8192 | 2 | f16 | 14b+9b | 15,09 GiB | **0,00s, ambos residentes** | passa |
| **4** | **32k auto** | **2** | f16 | 14b+9b | **19,68 GiB** | **0,00s, ambos residentes** | **passa — célula que faltava no plano original** |
| 5 | 16384 | 3 | f16 | 14b+9b+8b | 23,62 GiB | 0,00s, os 3 residentes | passa |
| 6 | 32k auto | 2 | **q8_0** | 14b+9b | 16,93 GiB | 0,00s, ambos residentes | passa (depois de limpar um vazamento — ver achado abaixo) |
| **7 (bônus)** | **32k auto** | **3** | **q8_0** | 14b+9b+8b | **24,11 GiB** | **0,00s, os 3 residentes** | **passa — maior capacidade testada** |

## O que isso confirma

**Config 4 fecha a questão da rodada 1 de revisão do plano**: não era preciso
cortar contexto para ter os dois modelos residentes. A 32k, sem tocar em nada
além de `MAX_LOADED_MODELS`, os dois cabem com **10,6 GiB de folga**. A tese
"fixar contexto compra o segundo residente" — que a revisão já tinha corrigido
no texto — está agora confirmada por medição, não só por aritmética.

**Config 7 é o teto de capacidade nesta classe de VRAM**: três modelos,
contexto cheio, KV quantizado, ~6 GiB de folga. Se a qualidade do `q8_0`
nesses três modelos específicos for validada (ver pendência abaixo), essa é a
configuração que "esvazia o argumento de cortar contexto" por completo, como o
plano previu.

## Achado operacional — não estava no plano, e é o mais importante do dia

**Reiniciar a tarefa `OllamaServer` matando só o processo `ollama` deixa o
worker de inferência (`llama-server.exe`) órfão, segurando a VRAM
indefinidamente.**

Sequência real, nesta sessão: cada uma das minhas 5 primeiras trocas de config
matou `ollama.exe` (o supervisor) mas não `llama-server.exe` (o processo real
que carrega os pesos e segura o contexto CUDA). Resultado: **7 processos
`llama-server.exe` zumbis acumulados** entre 21:21 e 21:25, e a VRAM real caiu
de 31,8 GiB livres para **252 MiB livres** — sem nenhum processo aparecendo em
`nvidia-smi --query-compute-apps` (por isso é invisível num check superficial:
os processos "sumiram" da lista de compute apps mas a memória continuou presa).

**Isso quase foi confundido com um bug do `q8_0`.** Testando a config 6 com a
VRAM já degradada pelos zumbis, o carregamento de `qwen3.5:9b` **crashou**
(`CUDA error: shared object initialization failed` no kernel de flash
attention, processo morto com `exit 0xc0000409`), e o retry automático do
Ollama só colocou 20 de 34 camadas na GPU (SPILL, resto na CPU) — mesmo com
"19 GiB livres" segundo o cálculo do próprio Ollama, que não sabia da memória
presa pelos zumbis. **Matando os 7 zumbis e testando de novo com VRAM
realmente limpa, a config 6 passou perfeitamente** — mesmo `qwen3.5:9b`, mesmo
`q8_0`, zero crash, 100% em GPU. O defeito era o vazamento, não o KV
quantizado.

**Correção aplicada:** o script de restart usado nesta sessão agora mata
`ollama` **e** `llama-server` antes de reiniciar. Isso precisa entrar no
runbook de operação — `MIGRACAO-windows-nativo-2026-09-04.md` só documentava
matar `ollama`, porque na migração original não havia motivo para reiniciar
com um modelo carregado. Qualquer restart futuro da tarefa (manual ou por
script) que não mate `llama-server` corre o mesmo risco.

## O que ficou sem medir por custo de tempo

- **Measure B do plano** (recarga depois de >5min ociosidade, testando
  `OLLAMA_KEEP_ALIVE` isoladamente): não executada em nenhuma config — exigiria
  ~35+ minutos de espera passiva só para as 7 configs. Não bloqueia a decisão
  desta fase (o critério de sucesso real era a Measure A), mas fica pendente
  se algum dia o objetivo for otimizar especificamente o caso de cliente com
  intervalo longo entre chamadas.
- **Qualidade do `q8_0`** nos três modelos exatos desta fase
  (`qwen3:14b`, `qwen3.5:9b`, `qwen3:8b`): a análise do plano usava divergência
  KL de `Qwen3.6-27B`/`Qwen3.6-35B-A3B` — modelos diferentes, mesma família.
  Configs 6 e 7 provaram que **cabe e não quebra tecnicamente**; não provaram
  que a **qualidade** se mantém. Antes de adotar `q8_0` em produção, rodar o
  goldset da Fase 0 contra as configs 6/7 e comparar com
  `chat_table.gpu5090-baseline.md`.
- **`qwen3.5:9b` continua com geometria de atenção não explicada.** VRAM
  residente variou entre 6,13 GiB (f16) e 5,73 GiB (q8_0) — uma diferença de
  só 0,4 GiB, muito menor que a metade esperada para KV quantizado, reforçando
  a suspeita já registrada no plano de que este modelo tem atenção não-padrão
  (`/api/show` não retorna `head_count_kv`). Não impede uso, só invalida
  qualquer estimativa de VRAM feita por extrapolação simples para ele.

## Estado em que o servidor ficou

**Config 4** (`OLLAMA_CONTEXT_LENGTH` não definida → auto 32k,
`OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_KV_CACHE_TYPE` não definida → f16),
validada limpa, `qwen3:14b` + `qwen3.5:9b` residentes, 19,68 GiB de 30,3.

Comparado à config 1 (a que a produção tinha antes desta fase): mesmo
contexto, mesma qualidade (f16 em ambas), **zero recarga entre os dois
modelos principais** em vez de 0,4–4,2 s a cada troca (medido nesta placa,
ver tabela no topo — não os ~25 s da 3080 Ti, que era outra placa e não é
comparável). É um ganho estritamente positivo, sem nenhum novo risco
introduzido — por isso foi a escolhida para
deixar em produção ao final desta sessão, em vez de 6 ou 7 (que dependem da
validação de qualidade pendente) ou 5 (que usa um contexto menor, 16k, sem
necessidade comprovada).

## Reprodução

Scripts desta fase: `fase1_apply.ps1` (troca as 3 env vars no escopo Machine e
reinicia a tarefa, matando `ollama` e `llama-server`) **é** o
`ollama-restart.ps1` da raiz do repositório — versionado desde 2026-09-04,
com o comentário do achado do zumbi, e desde então revisado e estendido
(`-NumParallel`, ordem de kill invertida, `exit 1` no health check — rodadas
`llm-bench-4`/`5`). `fase1_measure.sh` (Measure A: chama cada modelo-alvo duas
vezes e lê `ollama ps` entre cada chamada) **continua não versionado, perdido
em `/tmp` da sessão original** — a tabela acima não é reproduzível byte a
byte sem reescrever esse script.
