# Fase 6 — `OLLAMA_NUM_PARALLEL` — RTX 5090, 2026-09-05

**Resultado: `NUM_PARALLEL=2` reduz latência real sob concorrência, com
VRAM sobrando. Servidor deixado em `=2` ao final — ver decisão abaixo.**
**Remediado no mesmo dia com prompt de produção real (2108 tokens de
prefill) e checagem de VRAM — ganho confirmado, não mais circunstancial. Ver
a seção "Remediação" mais abaixo.**

## Método

`baseline-3080ti/repro/fase6_concurrency.py qwen3:14b 3 5` — 3 threads
disparando requisições **concorrentes** (não alternadas) ao mesmo modelo já
residente, 5 lotes por config, 1º lote descartado como warmup. Prompt fixo,
`num_predict=64`, `temperature=0`. Config 4 da Fase 1 mantida em tudo o
resto (32k, f16); só `OLLAMA_NUM_PARALLEL` mudou.

## Resultado

| Config | Wall do lote (mediana) | Por requisição (mediana) | VRAM (`qwen3:14b`+`qwen3.5:9b`) |
|---|---|---|---|
| `NUM_PARALLEL=1` (era produção) | 1,29 s | 0,86 s | 19,68 GiB |
| `NUM_PARALLEL=2` | **0,93 s** | **0,53 s** | 24,68 GiB (`qwen3:14b` sozinho foi de 13,55 para 18,55 GiB — dobrou o KV, +5 GiB, batendo com o medido na Fase 1) |

**−28% no tempo de lote, −38% por requisição**, com **5,6 GiB de folga**
ainda disponível em 30,3 GiB.

## O padrão que confirma o mecanismo

Com `NUM_PARALLEL=1`, os tempos por requisição sobem em degraus de ~0,43s
cada (0,43 / 0,86 / 1,28) — as três chegam juntas mas são processadas
estritamente uma de cada vez. Com `NUM_PARALLEL=2`, duas terminam quase
juntas (~0,45-0,53s, rodando em paralelo de verdade) e a terceira espera uma
vaga liberar antes de começar (~0,92-0,94s — roughly o dobro, exatamente
"esperou uma das duas primeiras, depois levou seu próprio tempo"). É a
assinatura exata que a documentação do Ollama descreve para `NUM_PARALLEL`,
agora medida nesta placa, neste servidor.

## Ligação com a baseline da 3080 Ti

A pista original (`baseline-3080ti/baseline-3080ti.md`) era GPU a 1-4% de
utilização durante chamadas lentas — assinatura de espera em fila, não de
placa saturada. Este teste mede exatamente esse cenário (múltiplas
requisições simultâneas ao mesmo modelo) e confirma: `NUM_PARALLEL=2`
reduz a fila real, não só a percebida.

## Decisão: servidor deixado em `NUM_PARALLEL=2`

Diferente das fases anteriores, apliquei e **não revertei** — o ganho é
limpo, medido, sem custo de VRAM (folga de 5,6 GiB) e sem regressão
conhecida. Mesma lógica da migração WSL→Windows: ganho real, aplicado.

**Ressalva que fica registrada:** só testado com `qwen3:14b`. Não retestei
`qwen3.5:9b` sob concorrência, nem o efeito combinado dos dois modelos
recebendo carga concorrente ao mesmo tempo (só um por vez, cada teste). Se o
padrão real de produção for diferente disso (ex.: rajadas nos dois modelos
juntas), vale medir de novo antes de assumir que o ganho se generaliza.

## Ressalva adicional — revisão de código (rodada `llm-bench-4`, 2026-09-05)

O `fase6_concurrency.py` usado nesta fase **não verificava residência 100% em
GPU** (`size_vram == size` via `/api/ps`) antes/depois da medição — achado de
`llm-bench-rev-2`, P1. O risco é concreto: sob `NUM_PARALLEL=2` o KV cache
dobra, e se o modelo não coubesse o Ollama faria *spill* de camadas pra CPU
silenciosamente, o que apareceria como "`NUM_PARALLEL=2` é pior", quando a
causa real seria "não coube" — é literalmente a mesma classe de erro que já
gerou o falso diagnóstico de bug do `q8_0` na Fase 1
(`results/RESULTADO-fase1-contexto-maxloaded-2026-09-04.md`).

Tentei reconferir isso agora, direto: `/api/ps` no servidor devolveu
`{"models":[]}` — nenhum modelo residente. O `keep_alive` já expirou desde a
Fase 6 e o dado de residência daquele momento específico **não é mais
recuperável**. O script foi corrigido (checa `/api/ps` antes/depois e avisa
se houver spill) para as próximas fases, mas isso não retroage.

O que sustenta a leitura original mesmo sem essa checagem: um *spill* pra CPU
é ordens de grandeza mais lento, não mais rápido — e o resultado medido foi
**mais rápido** com `NUM_PARALLEL=2` (−28% lote, −38% por requisição), com
VRAM medida em 24,68 GiB de 30,3 GiB disponíveis (5,6 GiB de folga). Spill e
"mais rápido com folga de VRAM" são estatisticamente incompatíveis o
suficiente para que a decisão continue de pé — mas é uma inferência pela
direção do efeito, não uma medição direta de `size_vram == size` no momento
do teste. Registrado como o que é: circunstancial, não confirmado.

Achado adicional (`llm-bench-rev-2`, P2): o prompt sintético usado (~12
tokens) não representava o perfil de produção (prompt médio ~2086 tokens,
`baseline-3080ti/baseline-3080ti.md`) — prefill sob concorrência real se
comporta diferente de decode sob concorrência real. **Remediado abaixo.**

## Remediação com prompt de produção e checagem de VRAM (2026-09-05, mesmo dia)

Os dois achados acima (VRAM não verificada, prompt não representativo) foram
fechados no mesmo dia, com medição nova, direta no servidor real — não é mais
inferência circunstancial. **Esta seção passou por uma segunda rodada de
revisão (`llm-bench-5`) que achou um problema real na primeira tentativa —
ver "Correção de percurso" abaixo antes da tabela final.**

**Prompt:** `baseline-3080ti/repro/fase6_prompt_longo.txt` — texto real (908
palavras do próprio `baseline-3080ti.md`, não sintético/lorem-ipsum), com uma
instrução de resumo na frente. Calibrado contra o servidor ao vivo:
`prompt_eval_count=2108`, dentro da faixa de produção medida (2086–2183
tokens nas três tarefas do `baseline-3080ti.md`) — e confirmado constante
(2108 em todas as 15 amostras de cada run, sem exceção) nas quatro runs desta
seção. **Ressalva (achado de revisão, rodada `llm-bench-7`): isso não descarta
cache de prompt, só não dá evidência positiva dele.** O mesmo prompt é
enviado repetidas vezes, exatamente o cenário em que um cache de prefixo (se
existir) mais provavelmente atuaria — e não há como saber, só pelo
`prompt_eval_count` reportado, se ele conta tokens genuinamente reprocessados
ou tokens nominais do prompt independente de cache interno. Não afirmo que
houve cache; afirmo que o experimento como desenhado não o exclui. Um braço
de controle com prefixos diferentes por chamada fecharia essa lacuna.

**Execução real, não simulada:** `ollama-restart.ps1` (já com `-NumParallel`
adicionado na rodada `llm-bench-4`) foi executado de fato em cada config, via
SSH → WSL2 → interop → PowerShell nativo elevado no próprio Ryzen9 — cadeia
de acesso descoberta e confirmada nesta sessão. Cada restart saiu limpo e o
log do servidor confirmou a variável aplicada em cada caso.

### Correção de percurso — a 1ª tentativa misturou duas versões do harness

A primeira medição desta remediação (`NUM_PARALLEL=1` antes de `=2`) rodou
com **duas versões diferentes** de `fase6_concurrency.py`: o braço `=1`
executou antes de eu corrigir o bug do falso-positivo de spill (ver histórico
abaixo), e o braço `=2` já com o fix. `llm-bench-rev-2` achou isso ao ler os
próprios JSONs gravados — `residente_pos_warmup=None`/`residente_depois=True`
(tipo antigo) no braço `=1` contra `residente_pos_warmup="ok"` (tipo novo) no
braço `=2` — e apontou corretamente que a frase "passando limpa nos dois
casos" que esta seção tinha originalmente não era sustentada pelo artefato do
braço `=1` daquela tentativa (a checagem de *fim* de janela daquela run
mostrou `size==size_vram` de verdade, mas não havia uma checagem equivalente
de *início* de janela, porque essa checagem só passou a existir no fix).
`llm-bench-rev` (revisor 1, mesma rodada) achou de forma independente que o
guard de residência era **fail-open**: falha ao consultar `/api/ps` e "modelo
ainda não carregado" caíam no mesmo estado neutro, sem alerta, mesmo depois
do warmup — quando o modelo deveria estar residente.

**Os percentuais da tentativa original nunca estiveram errados** — a
checagem de residência roda fora dos lotes cronometrados, e o caminho de
medição (`call_one`/`run_batch`) foi idêntico nas duas versões. O que estava
errado era a alegação de verificação completa. Em vez de só reescrever a
frase, corrigi o script (4 estados de residência em vez de 3 — `ausente`
deixou de ser sinônimo de `ok` depois do warmup —, `size`/`size_vram` brutos
agora persistidos no JSON, rótulo sanitizado, lotes com falha de requisição
excluídos das estatísticas em vez de enviesar o resultado pra parecer mais
rápido) e **re-rodei as duas configs do zero**, na mesma versão do harness
para as duas. Os JSONs da tentativa original foram descartados.

| Config | Wall do lote (mediana) | Por requisição (mediana) | `qwen3:14b` sozinho | Residência GPU (pós-warmup / final) |
|---|---|---|---|---|
| `NUM_PARALLEL=1` | 1,44 s | 0,96 s | 13,55 GiB | **OK / OK** |
| `NUM_PARALLEL=2` | **1,04 s** | **0,57 s** | 18,55 GiB | **OK / OK** |

Artefatos: `results/fase6_resultado_numparallel1-longo-v2_1788624124.json`,
`results/fase6_resultado_numparallel2-longo-v2_1788624157.json`. Comando:
`baseline-3080ti/repro/fase6_concurrency.py qwen3:14b 3 5 <rotulo>
baseline-3080ti/repro/fase6_prompt_longo.txt` (mesmos `threads=3`, `lotes=5`
da run original — a comparação de percentuais entre as duas é válida porque
a concorrência medida é a mesma).

**−28% no tempo de lote, −41% por requisição** — três medições **consistentes**
convergindo agora (não "independentes": a 1ª tentativa e esta re-medição usam
o mesmo prompt/servidor/janela e só diferem na versão do harness; o achado
original difere no prompt) — o original com prompt curto (−28%/−38%), a 1ª
tentativa desta remediação (−27%/−40%, com o defeito de verificação acima) e
esta re-medição limpa (−28%/−41%). VRAM idêntica à Fase 1 nas três vezes
(13,55→18,55 GiB), como esperado — KV cache escala com contexto configurado,
não com o prompt específico.

**Nuance nova, só visível porque o script agora guarda `eval_count`/
`eval_duration`** (achado `llm-bench-rev-2` da rodada `llm-bench-4`, também
corrigido): a geração pura (decode) fica ~9–11% **mais lenta** por fluxo sob
`NUM_PARALLEL=2` (138,4 → 125,3 tok/s nesta re-medição), os dois fluxos
concorrentes dividem o mesmo compute da GPU de verdade. O ganho de latência
percebida não vem de cada fluxo ficar mais rápido, vem de não esperar mais o
outro terminar inteiro antes de começar. As duas coisas são reais e não se
contradizem: fila menor, geração unitária um pouco mais lenta, resultado
líquido melhor.

**Decisão confirmada, agora sem ressalva de circunstancialidade nem de
harness inconsistente:** `NUM_PARALLEL=2` fica. Servidor terminou a
remediação já na config final (`=2`), coincidindo com o estado de produção
desejado — nenhum revert necessário.

**Ressalva que continua de pé:** ainda só testado com `qwen3:14b` sozinho.
Carga combinada dos dois modelos residentes ao mesmo tempo, e `qwen3.5:9b`
sob concorrência, continuam não medidos.

**Nota de transparência sobre o processo de revisão:** ao disparar a rodada
`llm-bench-5`, descrevi `ollama-restart.ps1` como "sem mudança de código"
desde a rodada `llm-bench-4` — isso estava errado. Esse arquivo mudou
substancialmente entre as duas rodadas (foi exatamente onde apliquei as
correções que a rodada 4 pediu: `-NumParallel`, ordem de morte invertida,
`exit 1` no health check, validação de parâmetros) e foi essa versão,
funcionalmente diferente da revisada, que aplicou a configuração de produção
usada para gerar estes números. `llm-bench-rev-2` sinalizou isso
corretamente como fora do escopo daquela rodada mas necessário registrar. Não
invalida os números (as correções tornaram o script mais seguro, não menos,
e os dois restarts desta seção saíram limpos com a config certa confirmada
no log), mas o arquivo em si segue sem uma rodada de revisão que veja essa
versão final lado a lado com o texto que a motivou.
