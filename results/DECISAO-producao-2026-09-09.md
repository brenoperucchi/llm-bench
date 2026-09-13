# Decisão de produção — 2026-09-09

Fecha o programa de sete fases. Todos os números **medidos nesta bancada** têm
artefato em `results/`; nada é estimativa. Os poucos atribuídos ao `llm-exec`
estão marcados como **externos, não auditados aqui** — hoje só o precedente de
janela de VRAM.

## Modelo

**Default: `qwen3:14b`. Segundo residente: `qwen3.5:9b`.**

Os três finalistas passaram pelo **mesmo** teste (9 casos críticos, n=5,
45 chamadas cada) — pela primeira vez a comparação é simétrica:

| | `qwen3:14b` | `qwen3.5:9b` | `qwen3.8:27b` |
|---|---|---|---|
| Goldset n=1 | 92% | 98% | 97% |
| **Reamostragem 9 críticos** | **40/45** | 38/45 | 38/45 |
| **Casos com defeito** | **1 de 9** | 3 de 9 | 4 de 9 |
| Tipo de falha | só LEAK | LEAK + MISS | LEAK + MISS |
| Tool-calling single-shot (A · B) | 8/8 · 8/8 | 8/8 · 8/8 | 8/8 · 8/8 |
| Fase 7 multi-rodada (contrato completo) | **5/5** | 0/4 | **5/5** |
| tok/s | 135 | 183 | 126 |

**Por que o incumbente:** menos casos defeituosos, melhor agregado, e — o que
pesa em operação — é o único cujas falhas são **todas LEAK**. Os outros dois
têm **MISS de escalação**: o cliente que precisava de humano não recebe, em
silêncio. LEAK é barulhento e detectável; MISS não.

**Por que o `qwen3.8:27b` não entrou:** quarto candidato a repetir o padrão
"score alto em n=1, defeito real ao reamostrar" (depois de `laguna-xs-2.1`,
`qwen3.5:9b` e do próprio `qwen3.5:9b` na Fase 7). Ele é bom em tool-calling
(8/8 e 5/5), mas tem 4 de 9 casos com defeito, incluindo dois MISS.

**Por que o segundo residente continua sendo o `qwen3.5:9b`:** cabe (5,73 GiB
contra 16,33 do 27B). O par `14b`+`27b` daria 30,26 GiB contra ~30,3
disponíveis — não cabe nem com `q8_0`. **Ressalva:** o `qwen3.5:9b` fabrica
citações de apoio em cadeia multi-rodada (0/4 na Fase 7 corrigida); se o
segundo slot for servir pesquisa com citação validada (acervo/DRE), ele é a
escolha errada e vale aceitar o swap de ~4 s.

## Config

| Parâmetro | Valor | Base |
|---|---|---|
| `OLLAMA_MODELS` | `E:\ollama\models` | SSD novo: leitura 1,27× (2.895→3.670 MB/s), 653 GB livres |
| `OLLAMA_CONTEXT_LENGTH` | não definida → 32k auto | Fase 1, config 4 |
| `OLLAMA_MAX_LOADED_MODELS` | `2` | Fase 1: recarga 0,4–4,2 s → 0,00 s |
| `OLLAMA_KV_CACHE_TYPE` | **`q8_0`** | **mudado hoje**: −4,62 GiB no `qwen3:14b`, qualidade idêntica (40/45 nos dois) |
| `OLLAMA_NUM_PARALLEL` | `2` | Fase 6: −28% lote, −41% por requisição, prompt de produção real |
| `OLLAMA_FLASH_ATTENTION` | não definida | **testado e descartado hoje**: efeito zero |

VRAM do par: **19,66 GiB, folga 10,64** (era 24,68 / 5,62 em f16).

### Sobre o `q8_0`

Único parâmetro alterado hoje. Reamostragem dos 9 críticos sob `q8_0` deu
**40/45, 1 caso com defeito** — idêntico ao f16, mesmo caso, mesmos números.
Ressalva: é um teste (9 casos, n=5); não prova neutralidade em geral, mas é o
mesmo teste que discriminou entre todos os modelos deste programa.

Os 4,62 GiB compram **margem defensiva**, não uma capacidade nova. Importa
porque o cenário nunca medido é justamente os dois modelos sob carga
concorrente simultânea — a Fase 6 mediu um modelo por vez.

### Sobre o `FLASH_ATTENTION`

Último lever de config do relatório original que faltava medir. A/B com
restart real, alternado por rodada, prompt de produção (2.108 tokens):

| | wall lote | por req | decode | VRAM (bytes) |
|---|---|---|---|---|
| off (r1) | 1,04s | 0,56s | 125,4 | 19.914.020.617 |
| on (r1) | 1,04s | 0,56s | 125,5 | 19.914.020.617 |
| off (r2) | 1,05s | 0,57s | 123,5 | 19.914.020.617 |
| on (r2) | 1,03s | 0,55s | 125,2 | 19.914.020.617 |

Diferença `on`×`off` menor que a diferença entre as duas rodadas de `off`
entre si. **VRAM byte-idêntica nas quatro** — se estivesse ativo, a alocação
de KV mudaria. Ou não tem efeito neste conjunto, ou é aceito na config e não
chega na inferência; de fora não dá pra distinguir. **Não usar.**

## Tweak recomendado — RETIRADO em 2026-09-09, estava errado

**Eu havia recomendado uma guarda de saída no gateway**, comparando a resposta
com o bloco `**Escalation response format:**` do system prompt e tratando a
coincidência como falha. **O `llm-exec` refutou, e a refutação está nos meus
próprios artefatos.** Verifiquei cada número:

A string de 267 bytes (hash `eb71bad4ee28`) aparece **25 vezes** em
`reamostra_criticos_qwen3-14b_1788841811.json`: **5 no LEAK** do
`quickbooks_trap_en` (`ok=false`) e **20 nas quatro escalações reais**
(`ok=true`). A comparação crua `resposta_do_LEAK == resposta_de_escalação_correta`
devolve `True` — mesmos 267 bytes, mesmo `eval_count=59`.

**Precisão da guarda: 5/25 = 20%.** Ela recusaria 20 escalações corretas para
pegar 5 LEAKs.

E o que fecha o argumento: na Fase 0 (`chat_raw.gpu5090-baseline.json`) o
mesmo hash aparece 8 vezes, sendo **3 no `qwen2.5:14b`** — modelo que não tem
este defeito — todas com `auto_score=1.0`. **A cópia literal é assinatura de
"escalou", não do defeito nem do modelo.** O system prompt manda usar
exatamente esse formato ao escalar; uma escalação correta produz o mesmo texto.

**Por que era pior que não fazer nada, pelo critério desta própria decisão:**
este documento mantém o `qwen3:14b` porque suas falhas são todas LEAK, e
"LEAK é barulhento e detectável; MISS não". A guarda pagaria **4 MISS
silenciosos por LEAK evitado** — na moeda que declaramos ser a mais cara. É a
v2 de prompt movida da geração para a entrega: a v2 fez o token sumir em 50%
das escalações reais; a guarda faria sumir em 100%.

**Nenhum limiar salva:** nos 45 registros, o maior trecho literal compartilhado
com o prompt é 7–44 bytes nas respostas boas que não escalam, e 266 tanto nos
5 LEAKs quanto nas 20 escalações corretas. As duas classes têm o mesmo texto.

**Meu erro específico:** olhei as 5 respostas que falhavam, vi que casavam com
o bloco do prompt, e concluí "detectável na borda" — **sem checar se as
respostas que passavam tinham o mesmo texto**. Era o controle óbvio e eu não
fiz. A diferença entre LEAK e escalação legítima está na **pergunta**, não na
resposta, e nenhuma comparação na borda alcança isso.

### O que o `llm-exec` propôs no lugar (sugestão de produto, decisão do Breno)

O que dói no LEAK não é escalar errado — é **pedir e-mail ao cliente**. O
passo 3 do protocolo (linhas 76 e 89 do system prompt) manda pedir e-mail no
texto gerado. Tirar isso do texto e passar para a UI (o usuário está logado, o
app já tem o e-mail) reduz o dano do LEAK a "uma escalação errada comum", sem
tocar em prompt e sem risco de MISS.

### O que isso obriga a olhar no goldset — trabalho nosso

**Enquanto o auto-check aprovar exatamente a mesma string que reprova, nenhum
conserto que atue sobre o texto pode passar no goldset.** Isso explica v1/v2/v3
melhor do que "o prompt é difícil": as três tentativas atacavam a string, e a
string é ambígua por construção. Um sinal que separe precisa vir do par
(pergunta, resposta), não da resposta.

**Respondido em 2026-09-10** (`results/RESULTADO-juiz-familia-2026-09-10.md`),
com sete juízes sobre 196 pares distintos de 11 modelos:

**Sim, o par carrega o sinal.** O `gemma4:26b` pega **11 dos 12 defeitos —
todos os 9 LEAKs — com 79% de precisão**. O `qwen3.5:9b` pega 7 de 12 com
**100% de precisão**: sete acusações, sete certas.

Isso fecha a questão de design do goldset registrada acima. **Mas não é
comparação controlada com os 20% da guarda de string:** aqueles 20% vêm de 25
registros de uma reamostragem específica; estes vêm de 196 pares de 11
modelos, com composição e prevalência diferentes. O que é comparável, e
suficiente, é o teste direto: nas **5 respostas byte-idênticas** onde a guarda
de string não podia acertar mais que o acaso, o juiz discriminou 5/5 usando só
a pergunta.

**A recomendação anterior deste bloco foi retirada.** Ela dizia "nenhum juiz
no caminho de produção", justificada por *"2,7% das escalações legítimas
bloqueadas"*. Esse número **era de um bug meu**: o harness truncava a resposta
em 1500 caracteres e escondia o token de escalação de 4 pares, criando falsos
positivos inexistentes. Sem o truncamento:

| juiz | escalações legítimas bloqueadas |
|---|---|
| `qwen3.5:9b` | **0 de 61 = 0,0%** |
| `gemma4:26b` | **0 de 61 = 0,0%** |
| `qwen3:14b` | 1 de 61 = 1,6% |

Os 3 FP restantes do `gemma4:26b` estão todos em `ok_respondeu` — ali uma
guarda forçaria escalação desnecessária, que é LEAK (barulhento), não MISS
(silencioso). Pelo critério que este documento usa para manter o `qwen3:14b`,
essa é a direção aceitável de erro.

**Estado: possível, não feita** (enquadramento do `llm-exec`, adotado — é mais
preciso que "reaberta", que sugere decisão esperando ser tomada). Não substituo a
recomendação com uma única rodada — esta bancada documentou cinco vezes que
n=1 aponta para o lado errado, e 12 defeitos vindos de 9 perguntas é denominador pequeno e concentrado — em
particular, **as 61 escalações legítimas vêm de apenas 4 perguntas**, então
"0 de 61" não estabelece 0% como propriedade do juiz. O que caiu foi a
justificativa, não a decisão.

**A aplicação offline foi RETIRADA em 2026-09-10.** Todas as versões
anteriores deste bloco diziam que o `gemma4:26b` permanecia firme como
auto-check offline do goldset. **Não permanece.** O goldset é um conjunto
rotulado — cada caso traz `expect_escalation` — e o check determinístico que
já existe (`run_auto`) acerta **12/12 com zero falso positivo**, instantâneo e
sem GPU, contra 11/12 e 3 falsos positivos do melhor juiz. Medido em
`results/comparacao-check-vs-juiz-2026-09-10.json`.

O erro foi o mesmo padrão do dia: transportei "só a pergunta distingue" — que
é verdade em **produção**, onde não há rótulo — para o **goldset**, onde o
rótulo está escrito ao lado da pergunta. As próprias etiquetas dos 196 pares
tinham sido geradas por esse check.

**O que sobra:** nenhuma aplicação do juiz no goldset. Em produção continua
*possível, não feita*. A única aplicação plausível ainda de pé é julgar contra
as rubricas `judge` dos 18 casos (passo a passo, caminho, tom), que o
`run_auto` só aproxima — e isso é **zero medido**.

**Família não é o eixo; tamanho anda com o resultado nesta amostra.** Abaixo de
~9B nenhum juiz tem sinal — três `llama` (3,2B a 8,0B) e um `gemma3n` (4,5B).
De 9,7B para cima, os três têm, em três famílias diferentes.

> **Correções.** Este bloco já foi reescrito duas vezes hoje. A primeira versão
> dizia que "juiz de família independente não ajudou" — retirada, era
> confundimento de tamanho: todos os não-Qwen testados tinham 3,2 a 8,0B. A
> segunda trazia os 2,7%/1,6% do bug de truncamento, e o denominador também
> estava errado (184 respostas corretas em vez das 61 escalações legítimas —
> só FP em `ok_escalou` vira MISS). Ambos corrigidos acima.

**Gerar e julgar: a formulação forte foi retirada.** O defensável é que *o
defeito de geração não se transfere ao julgamento*. O bloco de 267 bytes
aparece 5 vezes no conjunto — 4 escalações corretas e 1 LEAK, byte-idênticas —
e o `qwen3:14b` e o `gemma4:26b` discriminaram **5/5 usando só a pergunta**. É
o mesmo conjunto em que a guarda de string teve 20%. O `qwen3:14b` reprova
como juiz o LEAK que ele próprio produziu. Mas seu p cai de 0,0007 para
**0,069** quando o teste preserva o agrupamento por pergunta — seus 3 acertos
estão todos numa única pergunta.

**Alerta que ultrapassa este documento:** os 196 pares vêm de **9 perguntas**,
com `quickbooks_trap_en` concentrando 8 dos 12 defeitos — e **é o mesmo goldset
que decidiu o modelo de produção por reamostragem**. Se essa concentração
derruba a significância de um juiz, o mesmo raciocínio se aplica ao desempate
entre `qwen3:14b`, `qwen3.5:9b` e `qwen3.8:27b`, e ninguém o aplicou. Levantado
pelo `llm-exec`. Não afirma que a decisão do modelo cai; afirma que ela não foi
examinada sob este critério.

Registro do outro lado: `llm-gateway/docs/DECISAO-guarda-de-eco-2026-09-09.md`
(commit 3892007), com consulta cega aos dois revisores em `.herdr/ask/llm-4`.

### Topologia, para completude

O Contábil **não passa pelo gateway**: `app/services/chat/ollama_client.rb`
fala com o Ollama direto e `open_router_client.rb` com a OpenRouter direto. O
"gateway" do `runtime_config.rb` deles é a escolha entre esses dois clientes.
Nenhuma guarda no `llm-gateway` alcançaria esse tráfego hoje.

## Precedente: correção de registro não é correção de sistema (2026-09-10)

Houve **cinco correções minhas em dois dias** neste assunto, e a pergunta de
quando repassá-las aos consumidores acabou tendo uma resposta simples que não
era óbvia no meio do processo.

**Em nenhum momento houve sistema afetado.** Nunca houve juiz rodando, não
havia nada para desligar, e a decisão de modelo e de config desta página nunca
foi tocada. Tudo o que se corrigiu foi **registro** — números publicados e uma
recomendação que ninguém tinha implementado.

Essa distinção é o que torna a conta de atenção diferente. Correção de sistema
se comunica sempre e rápido, porque alguém pode estar agindo sobre o defeito.
Correção de registro compete com a atenção do destinatário, e mais uma
mensagem pode custar mais do que o erro que ela conserta.

**Refinamento do critério, do `llm-exec` (2026-09-10).** Eu havia proposto:
"consumidor com versão intermediária de pé → comunicar". Ele verificou os
quatro, achou dois nessa situação (DRE e MFC, com a recomendação de
auto-check offline ainda de pé) e **decidiu não comunicar**, com o argumento
de que importa *o que* está de pé:

- os dois estão com a **v5**, que é a versão final do número, com a ressalva
  dos 4 clusters junto — ninguém tem número errado;
- o que sobrou de pé é uma afirmação sobre **ferramenta interna do
  llm-bench**, não insumo de decisão deles. Repetir custa zero.

Ele registrou como dívida, a corrigir na próxima conversa que tiver com eles
por motivo real. O critério corrigido é: **não é "há versão intermediária de
pé", é "há versão intermediária de pé que o destinatário pode usar para
decidir alguma coisa"**.

Registro também que a verificação dele mostrou um acidente favorável: três dos
quatro consumidores pularam uma versão inteira porque havia rascunho humano
não enviado nos panes e ele segurou o disparo — menos versões intermediárias
circulando.

## Precedente operacional: janela de VRAM (2026-09-10)

O `gemma4:26b` não coexiste com o `qwen3:14b` — carregar um expulsa o outro
(ver `results/RESULTADO-juiz-familia-2026-09-10.md`). Quando o acervo pediu
janela para a medição 2 do A1, garanti não rodar o goldset com o `gemma4`
naquele dia. O `llm-exec` mediu o resultado (**relato externo — artefato no space
`llm-gateway`, não em `results/` deste repositório; não auditei estes
números**):

| braço | cargas frias |
|---|---|
| controle | 1 em 88 chamadas |
| A1 | **0 em 92 chamadas** |

Custo da garantia: não rodar um lote de que eu já não precisava. O `llm-exec`
relata que o braço ficou sem contaminação e que o resultado nulo
pré-registrado pode então ser atribuído ao fator e não ao ambiente — **essa
conclusão é deles, sobre a medição deles, e eu não a verifiquei**. O que fica
como precedente do meu lado é o custo: praticamente zero.

**Compromisso permanente:** avisar pelo canal do `llm-exec` antes de carregar
o `gemma4:26b`, sempre. O CIC também sente, porque o `qwen2.5:14b` deles não é
residente e cada chamada já expulsa alguém.

## Em aberto, sem bloquear produção

1. `keep_alive=5m` nunca foi questionado.
2. Goldset de programação (Fase 5) — bloqueado no sandbox de execução.
3. Padrão PT→EN nos modelos novos — não investigado.
4. **A recomendação sobre juiz em produção está reaberta** — ver acima. Um
   defeito ainda escapa do melhor juiz (o MISS do `qwen2.5:14b`), o degrau
   entre 8,0B e 9,7B não foi localizado, e o check de spill da Fase 6 é cego
   para modelos especulativos (`# TODO` registrado no código).
5. **O formato do goldset — 9 perguntas, uma concentrando 8 dos 12 defeitos —
   nunca foi aplicado à própria decisão de modelo desta página.**
6. Carga concorrente nos **dois** modelos ao mesmo tempo — nunca medida.
