# Juiz LLM para escalação: o degrau anda com o tamanho, não com a família

> **Sobre o título.** Uma versão anterior dizia "o que decide é o tamanho".
> Os dois revisores da rodada `llm-bench-9` apontaram que isso afirma causa
> que o desenho não identifica: não há comparação de tamanhos dentro de uma
> mesma família nem de famílias com tamanhos equivalentes, e não há nenhum
> não-Qwen entre 8B e 25B. O que está medido é **associação nesta amostra** —
> quatro juízes até 8,0B sem sinal, três de 9,7B para cima com sinal — não que
> o tamanho seja a causa.

**Data:** 2026-09-10
**Medição válida:** `results/juiz_grande_1789065587.json` — os sete juízes,
**sem truncamento**. É a única cujos números aparecem neste relatório.
**Superadas (mantidas só como registro do bug):**
`juiz_grande_1789042738.json`, `_1789043675.json`, `_1789043937.json` — as três
foram medidas com o corte de 1500 caracteres.
**Rodada parcial de teste do harness:** `_1789065150.json` — já sem
truncamento, só `llama3.2:latest`, sete minutos antes da válida. Ver
*Quanto vale repetir a rodada*.
**Complemento:** `_1789065587_complemento.json` — o par que deu `HTTPError` no
`gemma4:26b`, re-julgado em 2026-09-10. Fecha a cobertura em **196/196**.
**Conjunto:** `results/juiz_pares_2026-09-10.json`, sha256 `db06f457a538…`,
196 pares de **9 perguntas**, 11 modelos de origem.
**Harness:** `baseline-3080ti/repro/juiz_grande.py`
**Revisão cega:** `.herdr/review/llm-bench-9` (dois revisores, ambos reprovaram
a versão anterior)

> **Três correções registradas.**
>
> 1. A primeira versão, com 5 juízes, concluía que "a hipótese de família
>    independente está refutada". **Retirada** — havia um confundimento de
>    tamanho. Ver *O erro da primeira versão*.
> 2. A segunda versão media com um harness que **truncava a resposta em 1500
>    caracteres**, escondendo o token de escalação de 4 pares. Isso produziu
>    falsos positivos que não existiam e sustentou a recomendação de produção.
>    **Todos os números abaixo são da re-medição sem truncamento** (revisão
>    cega `llm-bench-9`). Ver *O bug de 1500 caracteres*.
> 3. **A recomendação que sobrevivia a tudo — "`gemma4:26b` como auto-check
>    offline do goldset" — também está errada, e é a correção maior.** O check
>    determinístico que já existe acerta **12/12 com zero falso positivo**,
>    instantâneo e sem GPU; o melhor juiz faz 11/12 com 3 falsos positivos. Ver
>    *A aplicação offline não existe*.

## O que se queria decidir

Depois que o llm-exec refutou a guarda de saída por string (precisão 20% — a
mesma string de 267 bytes marca 5 LEAKs e 20 escalações corretas), sobrou um
item meu: *o sinal precisa vir do par (pergunta, resposta), não do texto da
resposta.* Um modelo-juiz olha o par. A pergunta era se isso funciona — e,
junto, uma hipótese do Breno: um juiz de **família diferente** do trabalhador
(Qwen) erraria diferente e por isso serviria melhor.

## O conjunto, e por que o anterior não valia

O teste de triagem (2026-09-09) tinha 25 registros — mas 5 perguntas distintas
e **uma única resposta**, byte-idêntica nas 25 ocorrências. Media a reação a um
texto só.

Este tem 196 pares distintos, de 11 modelos, com os quatro quadrantes:

| quadrante | n | é defeito? |
|---|---|---|
| `ok_respondeu` (não escalou, e não devia) | 123 | não |
| `ok_escalou` (escalou, e devia) | 61 | não |
| `LEAK` (escalou, e não devia) | 9 | **sim** |
| `MISS` (não escalou, e devia) | 3 | **sim** |

Total: 184 corretos, 12 defeitos. **Aprovar tudo dá 94% de acurácia e pega
zero defeitos** — por isso o critério aqui nunca é acurácia.

## Resultado: sete juízes, ordenados por tamanho

Recall alto não vale nada se vier de acusar quase tudo. A coluna que separa
sinal de barulho é o **lift** — quantos defeitos o juiz pegou contra quantos
o acaso entregaria dada a taxa com que ele acusa (Fisher exato).

| juiz | arquitetura | params | acusa | pegou | FP | **FP em escalação** | precisão | lift | p global | p por pergunta |
|---|---|---|---|---|---|---|---|---|---|---|
| `llama3.2:latest` | `llama` | 3,2B | 134/196 | 8/12 | 126 | **35** | 6% | 1,0× | 0,683 | 0,509 |
| `gemma3n:e2b` | `gemma3n` | 4,5B | 125/196 | 4/12 | 121 | **1** | 3% | 0,5× | 0,994 | 0,996 |
| `deepseek-r1:8b-llama-distill` | `llama` | 8,0B | 29/196 | 3/12 | 26 | **0** | 10% | 1,7× | 0,254 | 0,449 |
| `ministral-8b` | `llama` | 8,0B | 0/196 | 0/12 | 0 | **0** | — | — | 1,000 | 1,000 |
| **`qwen3.5:9b`** | `qwen35` | 9,7B | 7/196 | 7/12 | **0** | **0** | **100%** | 16,3× | <0,001 | <0,001 |
| `qwen3:14b` | `qwen3` | 14,8B | 4/196 | 3/12 | 1 | **1** | 75% | 12,2× | <0,001 | **0,069** |
| **`gemma4:26b`** | `gemma4` | 25,2B | 14/196 | **11/12** | 3 | **0** | 79% | 12,8× | <0,001 | <0,001 |

A coluna **FP em escalação** é a que importa para produção: só um falso
positivo em `ok_escalou` suprime uma escalação real e vira MISS silencioso. Um
FP em `ok_respondeu` força uma escalação desnecessária — LEAK, que é
barulhento. São 61 escalações legítimas no conjunto, não 184.

A coluna **p por pergunta** existe porque os 196 pares vêm de **9 perguntas**,
e `quickbooks_trap_en` sozinha concentra 8 dos 12 defeitos. Tratar os 196 como
independentes premia quem acusa concentrado justo nela. Redistribuindo as
acusações dentro de cada pergunta, o `qwen3:14b` cai de 0,0007 para **0,069** e
deixa de ser significativo — seus 3 acertos estão todos na mesma pergunta. O
`qwen3.5:9b` e o `gemma4:26b` sobrevivem.

**Existe um degrau, e nesta amostra ele coincide com o tamanho.** Abaixo de ~9B: nenhum juiz tem
sinal, em nenhuma família — três `llama` e um `gemma3n` todos indistinguíveis
do acaso. De 9,7B para cima, os três têm sinal **no teste global**, em três famílias
diferentes (`qwen35`, `qwen3`, `gemma4`) — mas **sob o teste por pergunta
sobram dois**: `qwen3.5:9b` e `gemma4:26b`. O `qwen3:14b` fica em 0,069.
"Não significativo" também não demonstra ausência de capacidade; demonstra que
esta amostra não a estabelece.

O `llama3.2` parece o segundo melhor até você olhar quanto ele acusa: **134 de
196**, 68% de tudo — e **35 das 61 escalações legítimas**. Acusando 134 ao
acaso, pegaria 8,2 dos 12 defeitos. Pegou 8. Lift 1,0×. O `gemma3n` está
*abaixo* do acaso. O `ministral-8b` é degenerado: respondeu CORRETO nos 196.

### Recall por quadrante

| juiz | LEAK (9) | MISS (3) | tem sinal? |
|---|---|---|---|
| **`gemma4:26b`** | **9/9** | 2/3 | sim |
| `qwen3.5:9b` | 7/9 | 0/3 | sim |
| `qwen3:14b` | 3/9 | 0/3 | não, agrupado |
| `llama3.2` | 5/9 | 3/3 | não |
| `gemma3n:e2b` | 2/9 | 2/3 | não |
| `deepseek-r1:8b-llama-distill` | 1/9 | 2/3 | não |
| `ministral-8b` | 0/9 | 0/3 | não |

Sem o truncamento, o `gemma4:26b` pega **todos os 9 LEAKs**. O LEAK que
"escapava" na medição anterior era o do `qwen3.8:27b`, cujo token de escalação
está na posição 1712 — depois do corte.

## O bug de 1500 caracteres

O harness enviava `par['resposta'][:1500]` ao juiz. **Quatro pares têm o token
`[ESCALATE_TO_SUPPORT]` depois do corte**, então o juiz julgava sem ver a
escalação e dizia "não escalou" — corretamente, sobre o texto mutilado:

| quadrante | caso | origem | tamanho | token na posição |
|---|---|---|---|---|
| `ok_escalou` | `escalate_wrong_numbers_pt` | `qwen3:30b-a3b` | 12 515 | 5 938 |
| `ok_escalou` | `escalate_wrong_numbers_pt` | `qwen3-coder:30b` | 1 860 | 1 661 |
| `ok_escalou` | `escalate_feature_en` | `qwen3:30b-a3b` | 1 722 | 1 535 |
| `LEAK` | `quickbooks_trap_en` | `qwen3.8:27b` | 1 911 | 1 712 |

Os dois primeiros eram **exatamente os falsos positivos que sustentavam a taxa
de escalação bloqueada** publicada na versão anterior. O quarto era o LEAK que
publiquei como limite do melhor juiz. Nenhum dos dois era defeito do juiz.

Efeito da correção, medido:

| juiz | com o bug | sem o bug |
|---|---|---|
| `qwen3.5:9b` | 6/12, 3 FP | **7/12, 0 FP** |
| `gemma4:26b` | 10/12, 5 FP | **11/12, 3 FP** |
| `qwen3:14b` | 3/12, 1 FP | 3/12, 1 FP |
| `deepseek-r1 distill` | 2/12, 33 FP | 3/12, 26 FP |
| `gemma3n:e2b` | 5/12, 124 FP | 4/12, 121 FP |
| `llama3.2` | 8/12, 128 FP | 8/12, 126 FP |

O truncamento **suprimia** desempenho, não o inflava. E o dano foi ao
julgamento sobre o dado, não ao dado — que continuou íntegro no arquivo,
parecendo confiável. Um limite de tamanho no caminho de diagnóstico é
diferente de um no caminho de dados; este era do primeiro tipo e por isso
passou despercebido.

Vale além deste caso: o vazamento de raciocínio do `qwen3:30b-a3b` produz
resposta de 12,5 KB com o token de escalação no meio. Qualquer coisa que olhe
só o início — log truncado, preview, regex com limite — pode concluir "não
escalou" sobre uma escalação que existe.

## O erro da primeira versão

A versão de 5 juízes concluiu que a hipótese de família independente estava
refutada, porque o único juiz com sinal era o CONTROLE (`qwen3.5:9b`, mesma
família do trabalhador). **Essa conclusão não se sustentava: eu tinha criado
um confundimento de tamanho e não percebi.**

Os quatro juízes não-Qwen que testei tinham 3,2 a 8,0B. O Qwen do controle
tinha 9,7B — o maior dos cinco. Família e tamanho andavam juntos na amostra, e
eu atribuí à família o que era do tamanho.

Havia um segundo defeito na mesma tabela: eu listei **fornecedores** (Mistral,
Google, Meta, DeepSeek) como se fossem famílias, superestimando a diversidade
testada. As famílias declaradas pelo Ollama eram `llama`, `llama`, `llama`,
`gemma3n` — **duas** famílias não-Qwen, não quatro.

Acrescentar um Gemma de 25,2B mostra que **existe juiz útil fora da família
Qwen** — mas não realiza o cruzamento que separaria família de tamanho. Para
isso faltariam tamanhos diferentes dentro de uma mesma família, ou famílias
diferentes com tamanhos equivalentes; não há nem um nem outro, nem qualquer
não-Qwen entre 8B e 25B.

**O efeito de família continua não identificado** — não foi demonstrado que
ela não importa. O que está medido é que a hipótese original (família
diferente ajuda) não se sustenta como enunciada, e que nesta amostra o
resultado coincide com o tamanho. "Competência de instrução" é uma leitura
plausível, não uma variável que eu tenha medido.

## O defeito de geração não se transfere ao julgamento

**Formulação corrigida.** A versão anterior dizia "gerar e julgar são
capacidades separadas" e apoiava isso em **uma** observação. "Separadas"
implica independência, que este dado não mede. O que os dados sustentam é mais
modesto e suficiente: *o defeito que o modelo comete ao gerar não reaparece
quando ele julga*.

E a evidência é cinco vezes maior do que eu havia usado. O bloco de 267 bytes
(hash `eb71bad4`) aparece **5 vezes no conjunto** — 4 escalações corretas e 1
LEAK, resposta **byte-idêntica**, todas do `qwen3:14b`. Só a pergunta
distingue:

| juiz | discriminou | tem sinal? |
|---|---|---|
| `qwen3:14b` | **5/5** | não (0,069) |
| `gemma4:26b` | **5/5** | sim |
| `deepseek-r1:8b-llama-distill` | **5/5** | **não (0,449)** |
| `qwen3.5:9b` | 4/5 (errou o LEAK) | sim |
| `ministral-8b` | 4/5 | não — degenerado, diz CORRETO a tudo |
| `gemma3n:e2b` | 4/5 | não |
| `llama3.2:latest` | 3/5 | não |

**Este bloco é fraco como discriminador entre juízes**, e a própria tabela
mostra por quê: o `deepseek-r1 distill` também faz 5/5, e é um juiz **sem
sinal** (p por pergunta 0,449, 26 falsos positivos). Fazer 5/5 aqui é
compatível com "acusa LEAKs em `quickbooks_trap_en` e aprova o resto", que
qualquer juiz acusando ~15% dos pares tende a produzir. O `ministral-8b` faz
4/5 sendo degenerado. A versão anterior desta tabela listava só quatro juízes
e omitia justamente o distill — achado do `llm-bench-rev-2`, rodada 10.

O que o bloco sustenta é a afirmação sobre **um** modelo, e essa continua de
pé: o `qwen3:14b` produziu aquele LEAK e o reprova como juiz, acertando as 4
escalações legítimas de texto idêntico. Não sustenta ranking entre juízes.

Este é exatamente o conjunto em que a guarda de string teve **20% de
precisão**: os mesmos 267 bytes marcavam 5 LEAKs e 20 escalações corretas, e
nenhuma comparação de texto podia separá-los. O `qwen3:14b` — que **produziu**
o LEAK — o reprova como juiz, e acerta as 4 escalações legítimas de texto
idêntico.

O que isto **não** demonstra: independência dos erros, vantagem geral de
revisão mútua, ou que julgar seja uma capacidade distinta. Uma leitura
igualmente compatível é que julgar é simplesmente *mais fácil* — classificação
binária com a política no prompt, contra geração sob um system prompt de 5 KB
que contém o bloco que o modelo copia. A versão fraca basta para fundamentar
modelos revisando o trabalho um do outro; a forte não é necessária e não está
medida.

## Ensembles

| combinação | pegou | FP | FP em escalação | precisão |
|---|---|---|---|---|
| `gemma4:26b` sozinho | 11/12 | 3 | **0** | 79% |
| `qwen3.5:9b` sozinho | 7/12 | 0 | **0** | 100% |
| `gemma4` **OU** `qwen3.5` | 11/12 | 3 | **0** | 79% |
| `gemma4` **E** `qwen3.5` | 7/12 | 0 | **0** | 100% |
| ≥2 de 3 (`g4`,`q3.5`,`q14`) | 8/12 | 0 | **0** | 100% |

Ao contrário da medição anterior, **aqui combinar ajuda**. O voto `≥2 de 3`
pega 8 dos 12 defeitos com **zero falsos positivos** — domina o `qwen3.5:9b`
sozinho (7/12), com a mesma precisão perfeita. Duas fronteiras, então:

- **Recall máximo:** `gemma4:26b` sozinho, 11/12, 3 FP (nenhum em escalação).
- **Precisão perfeita:** `≥2 de 3`, 8/12, 0 FP.

`gemma4 OU qwen3.5` não acrescenta nada sobre o `gemma4` sozinho — tudo que o
`qwen3.5` acusa, o `gemma4` também acusa. E `gemma4 E qwen3.5` é idêntico ao
`qwen3.5` sozinho, pela mesma razão: as acusações do `qwen3.5` são um
subconjunto das do `gemma4`.

Custo importa na escolha: o `qwen3.5:9b` ocupa 5,73 GiB e **cabe** residente ao
lado do `qwen3:14b`; o `gemma4:26b` ocupa ~17,5 GiB e não cabe.

## O que dá para usar, e onde

O resultado **prova que o par (pergunta, resposta) carrega o sinal** que a
string não carregava. O `gemma4:26b` pega 11 dos 12 defeitos — todos os 9
LEAKs — com 79% de precisão. O `qwen3.5:9b` pega 7 de 12 com **100% de
precisão**: sete acusações, sete certas.

> **Onde isso vale, e onde não vale — leia a seção *A aplicação offline não
> existe* antes desta.** Este resultado é relevante para o caso **sem rótulo**,
> que é produção. No goldset, que é rotulado, o check determinístico faz 12/12
> com zero falso positivo e nenhum juiz o supera. As duas subseções abaixo
> discutem produção; a aplicação offline foi retirada.

### A recomendação anterior perdeu a base — e não a substituo ainda

A versão anterior recomendava **nenhum juiz no caminho de produção**, e a
justificativa era uma só: *"2,7% das escalações legítimas bloqueadas, e
escalação bloqueada vira MISS silencioso"*.

**Esse número era do meu bug.** Sem o truncamento:

| juiz | escalações legítimas bloqueadas |
|---|---|
| `qwen3.5:9b` | **0 de 61 = 0,0%** |
| `gemma4:26b` | **0 de 61 = 0,0%** |
| `qwen3:14b` | 1 de 61 = 1,6% |

Os 3 falsos positivos restantes do `gemma4:26b` estão **todos em
`ok_respondeu`** — ali uma guarda forçaria escalação desnecessária, que é LEAK
(barulhento), não MISS (silencioso). Pelo critério que este próprio documento
usa para manter o `qwen3:14b` em produção, essa é a direção aceitável de erro.

### Mas "0 de 61" tem o mesmo problema que o p global

Este documento acabou de argumentar que 196 pares vindos de 9 perguntas não
são 196 observações independentes, e usou isso para retirar a significância do
`qwen3:14b`. **O mesmo argumento se aplica ao 0/61 — e eu não o havia
aplicado.** As 61 escalações legítimas vêm de **4 perguntas**:

| pergunta | pares |
|---|---|
| `escalate_wrong_numbers_pt` | 17 |
| `escalate_double_charge_en` | 15 |
| `escalate_stripe_broken_pt` | 15 |
| `escalate_feature_en` | 14 |

Em termos de perguntas, "0 falso positivo em 61" é **0 em 4 tipos de
escalação**. A regra dos três sobre n=61 daria teto de ~4,8%; sobre 4 clusters
não dá teto útil. E a quarta pergunta já se mostrou sensível ao juiz: o único
FP em escalação de todo o conjunto — `qwen3:14b` em `escalate_feature_en` —
está justamente ali.

### Quanto vale repetir a rodada: quase nada

Eu havia listado "é uma rodada" como primeiro motivo para não decidir. **É o
motivo mais fraco dos quatro**, e há evidência no próprio repositório contra
ele. A rodada parcial `_1789065150.json` mediu o `llama3.2` no mesmo conjunto,
sem truncamento, `temperature: 0`, sete minutos antes da válida:

| | acusações | FP |
|---|---|---|
| `_1789065150` | 133 | 125 |
| `_1789065587` | 134 | 126 |

**±1 acusação em 196.** É o que uma repetição compra.

E eu usei mal o meu próprio precedente: o `ministral-8b` passar de "25/25
perfeito" a degenerado **não foi uma re-rodada** — foi uma troca de conjunto,
de uma resposta repetida 25 vezes para 196 distintas. O que muda o resultado é
conjunto novo, não rodada nova. Achado do `llm-bench-rev-2`, rodada 10.

### Por que a pergunta continua aberta, com os rótulos certos

- **O motivo real:** as 61 escalações vêm de 4 perguntas e os 12 defeitos de 9.
  `0/61` não é `0%` como propriedade do juiz. O que fecha isso é **conjunto
  novo com mais perguntas de escalação**, não repetição.
- **Latência e VRAM**, e aqui é preciso separar: o `gemma4:26b` **não coexiste**
  com o `qwen3:14b`, o que sozinho o descarta do caminho de produção hoje,
  independentemente dos falsos positivos. O `qwen3.5:9b` **cabe** — 5,73 GiB, e
  já é o segundo residente.
- **O erro de infra foi fechado.** O `HTTPError` do `gemma4` estava em
  `plaid_trap_pt` (`ok_respondeu`, verdade CORRETO). Re-julgado: o juiz
  respondeu CORRETO — verdadeiro negativo. **Cobertura 196/196**, e nenhum
  número muda: `vn` passa de 180 para 181, `vp`/`fp`/`fn` intactos. Já não é
  motivo para nada, e nunca foi de mérito — mantê-lo como razão para não
  decidir seria usar detalhe operacional como argumento.

**A pergunta que sobra, nomeada:** *o `qwen3.5:9b` como juiz inline vale a
latência, tendo feito 7/12 com 0 falso positivo sobre apenas 4 perguntas de
escalação?*

E o enquadramento certo é do `llm-exec`, melhor que o meu: **a medição habilita
a opção e nenhum consumidor a pediu — fica registrada como possível, não
feita.** "Reaberta" sugere uma decisão esperando ser tomada; não há. O acervo
quer código atribuível na borda, não segunda opinião; o CIC não é consumidor
do gateway; o MFC é one-shot; o DRE não pediu. Construir juiz inline sem
consumidor que o queira seria mecanismo genérico antes do caso.

O que fica registrado, então: o `qwen3.5:9b` **cabe** residente ao lado do
`qwen3:14b` (5,73 + 13,93 = 19,66 GiB contra ~30,3) — é o par que esta bancada
já documentou — e a objeção de VRAM que descarta o `gemma4:26b` não se aplica
a ele. O custo real seria dobrar a latência de toda chamada. Se algum
consumidor pedir, a medição está aqui.

**Estado: reaberta, não respondida.** O que caiu foi a justificativa, não a
decisão. Trocar uma conclusão mal medida por outra mal medida repetiria o
erro, e não a natureza dele.

## A aplicação offline não existe

**Retirado em 2026-09-10.** Todas as versões anteriores deste relatório
terminavam dizendo que o `gemma4:26b` "permanece firme como auto-check offline
do goldset". **Não permanece. Não há lugar para ele ali.**

O goldset é um conjunto **rotulado**: cada caso traz `expect_escalation`, e o
check determinístico faz simplesmente
`escalation_ok = (has_token == auto["expect_escalation"])`. Ele não precisa
inferir nada — só comparar com o gabarito. Medido sobre os mesmos 196 pares
(`results/comparacao-check-vs-juiz-2026-09-10.json`,
`baseline-3080ti/repro/compara_check_vs_juiz.py`):

| corretor | pegou | FP | precisão | tempo | VRAM |
|---|---|---|---|---|---|
| **`run_auto`, determinístico** | **12/12** | **0** | **100%** | instantâneo | **0** |
| `gemma4:26b` | 11/12 | 3 | 79% | 1,1 min | ~17,5 GiB |
| `qwen3.5:9b` | 7/12 | 0 | 100% | 0,6 min | 5,73 GiB |
| `qwen3:14b` | 3/12 | 1 | 75% | 0,4 min | 13,93 GiB |

Zero divergências no check determinístico. **O juiz é estritamente pior que o
que já estava lá**, e ainda expulsa o modelo de produção da VRAM para rodar.

### O erro, que é o mesmo dos outros de hoje

Transportei uma conclusão para um lado da comparação onde ela não foi medida.
"Só a pergunta distingue LEAK de escalação legítima" é verdade **em
produção**, onde chega uma resposta sem rótulo. No **goldset** o rótulo está
escrito ao lado da pergunta. A cegueira que o juiz resolve não existe aqui.

Pior: as próprias etiquetas `verdade` dos 196 pares **foram produzidas por
esse check determinístico**. Eu medi o juiz contra o gabarito que o check gera
perfeitamente, e não notei que estava comparando o candidato com o titular
usando a régua do titular.

### O que isso deixa em pé

- **O juiz não tem aplicação no goldset.** Nem escalação (o check é exato) nem
  as rubricas `judge` dos 18 casos — essas nunca foram medidas.
- **Em produção continua "possível, não feita"**, pelo enquadramento do
  `llm-exec`: lá não há rótulo, e ali o juiz de fato acrescenta sinal que
  nenhuma comparação de texto alcança. Mas nenhum consumidor pediu.
- **O item que assumi do `llm-exec` continua aberto e o juiz não o resolve.**
  "Enquanto o auto-check aprovar exatamente a mesma string que reprova, nenhum
  conserto de texto passa no goldset" é problema de **desenho do prompt**:
  qualquer mudança que tire a string quebra as 4 escalações legítimas,
  qualquer uma que a mantenha mantém o LEAK. O check já distinguia os casos; o
  juiz distinguir também não conserta o prompt.
- **A única aplicação plausível que sobra é a dimensão não medida:** julgar
  contra as rubricas `judge` (passo a passo correto, caminho de navegação,
  tom), que hoje ninguém verifica e o `run_auto` só aproxima por substring e
  regex de formato. Isso exigiria pares rotulados contra as rubricas, que não
  existem.

### Capacidade — corrigido depois que a sessão `llm-gateway` (`llm-exec`) contestou o número

**A nota anterior estava errada.** Ela dizia que o `gemma4:26b` "ocupa 16,5 GiB"
e que "não cabe ao lado do `qwen3:14b` **mais o segundo modelo de produção**" —
o que implica que caberia ao lado do `qwen3:14b` sozinho. **Não cabe.** Medido
diretamente:

| | GiB em VRAM |
|---|---|
| `qwen3:14b` carregado (41/41 camadas, KV q8_0 5440 MiB) | 13,93 |
| `gemma4:26b` carregado (alvo 25,23B, 31/31 camadas + rascunho 419,71M) | ~17,5 |
| **soma** | **~31,4** |
| documentado como utilizável | ~30,3 |

Confirmado empiricamente: carregar o `gemma4:26b` **expulsou** o `qwen3:14b` da
VRAM. Logo, toda rodada de goldset com este juiz custa uma carga fria ao
próximo consumidor de produção. "Offline" descreve o propósito do check, não o
isolamento dele — o goldset e a produção dividem a mesma GPU.

**Consequência operacional:** combinar janela antes de rodar o juiz em lote,
não apenas rotular as chamadas. O harness agora registra `load_duration` por
chamada e reporta cargas frias.

### `/api/ps` sub-reporta a VRAM deste modelo — cuidado

O `gemma4:26b` usa **decodificação especulativa**: o blob traz um alvo
`gemma4` de 25,23B e um rascunho `gemma4-assistant` de 419,71M. O
`/api/ps` reporta **apenas 1,38 GiB**, que é o rascunho — some com os ~16 GiB
do alvo. O log do servidor mostra os dois carregando:

```
print_info: arch = qwen3             model params = 14.77 B   offloaded 41/41 layers
print_info: arch = gemma4            model params = 25.23 B   offloaded 31/31 layers
print_info: arch = gemma4-assistant  model params = 419.71 M  offloaded  5/5  layers
```

**Isso quebra o check de spill que uso na Fase 6**, que compara
`size_vram == size` do `/api/ps`. Para um modelo com rascunho especulativo os
dois campos batem em 1,38 GiB e o check aprova, sem enxergar o alvo. Se o
`gemma4:26b` (ou qualquer modelo especulativo) entrar num teste de
concorrência, o check precisa ler as camadas offloaded do log, não o
`/api/ps`. Fica registrado como pendência.

Isto também explica a velocidade do `gemma4:26b`: o rascunho acelera a
geração. (Na rodada válida ele levou 1,1 min, que inclui 15,4 s de carga fria; os
0,4 min que eu havia citado eram da rodada truncada.)

## O que a dimensão (B) rendeu: consertar o check, não medir juiz

A pergunta seguinte era medir um juiz contra as **rubricas `judge`** dos 18
casos — a dimensão que o `run_auto` não cobre. A sondagem disse para não
medir, e o motivo é o mesmo que derrubou a aplicação offline: **o titular
resolve mais barato.**

**As rubricas são majoritariamente redundantes.** Comparei as 18 uma a uma com
o `auto` de cada caso: a maioria só reescreve `must_include_any`, `lang` e
`steps_format`. As três traps de anti-alucinação (`quickbooks_trap_en`,
`payroll_trap_pt`, `mobile_trap_en`) são a exceção — não têm check além de
idioma e escalação, e toda a substância vive na rubrica.

Escrevi detectores para o que as rubricas acrescentam de verificável.
**Acusaram 7; ao ler os registros exatos, 4 estavam errados.** Dois erros meus
no caminho, ambos registrados porque são instrutivos:

1. A lista de negações não tinha `"rather than"` — marquei *"we use Stripe
   Financial Connections (rather than Plaid)"* como se o modelo afirmasse usar
   Plaid.
2. Na primeira verificação usei `next()` e **li registros diferentes dos
   marcados** — há várias respostas por (caso, modelo) entre os seis arquivos.
   Quase concluí "tudo falso positivo" pela razão errada.

### O que sobrou verificado

**Duas violações genuínas**, ambas em `howto_estimate_en`, ambas com
`auto_score` 1,0:

- `qwen2.5:14b` manda ir em **Sales → Invoices** e clicar em *"Create Invoice
  from Estimate"* — caminho diferente do da rubrica. O `include_ok` passava
  porque só exigia a palavra "Estimate".
- `qwen3.5:9b` diz *"clique no botão Convert **se disponível**"* — vago, e não
  é o fluxo pedido.

**Uma limítrofe:** `qwen3.5:9b` no `mobile_trap_en` nega o app corretamente mas
inventa um *"Isafi Progressive Web App"*. É julgamento genuíno.

### O achado maior, que nenhuma rubrica pedia

As outras três acusações estavam erradas pelo motivo que apontei — mas as três
respostas têm outro defeito, real:

| vazamento de raciocínio na resposta | |
|---|---|
| respostas afetadas | **18 de 251** |
| modelo | todas do `qwen3:30b-a3b` |
| com `auto_score` 1,0 antes | **11** |
| tamanho mediano | 3 020 chars contra 530 nas limpas |
| rubricas que mencionavam isso | **nenhuma** |

O modelo entrega o próprio raciocínio ao usuário. Nenhum check pegava, nenhuma
rubrica pedia — e foi isto que produziu as respostas de 12,5 KB que forçaram o
truncamento que estragou a medição de hoje cedo.

### O que foi consertado

Três mudanças, todas determinísticas, nenhuma precisa de GPU
(`results/checks-estendidos-2026-09-10.json`):

1. **`run_chat.py`** ganhou o check **global** `no_reasoning_leak`.
2. **`howto_estimate_en`** passa a exigir `"Convert to Invoice"` no
   `must_include_any`.
3. **As 18 rubricas** ganharam *"O raciocínio do modelo NÃO pode aparecer na
   resposta"* — a regra que faltava estar escrita.

Efeito medido sobre as 251 respostas: **13 que passavam em tudo agora
reprovam** (11 por vazamento, 2 pelo estimate) e **zero regressões**. O check
apertado não gera falso positivo: das 14 respostas de `howto_estimate_en`, 12
trazem a string literal e passam.

> **Aviso de comparabilidade:** o denominador do `auto_score` mudou de 5–6 para
> 6–7 checks. `auto_score` de artefatos anteriores a 2026-09-10 **não** é
> comparável com os de depois; os campos individuais continuam comparáveis.

### O que ainda exigiria um juiz, e continua sem gabarito

Sobra o que não é mecânico: *"não pode inventar um fluxo"* (inventar não é
palavra-chave), *"tom da Lana"*, e consistência entre casos. Isso precisaria de
rótulos humanos e ainda seria subjetivo. **Não medido, e não recomendado
enquanto houver conserto determinístico por fazer.**

## O que continua em aberto

- **A recomendação de produção está reaberta.** A justificativa caiu junto com
  o bug de truncamento; não a substituí. Precisa de mais de uma rodada.
- **O formato do goldset é o item maior, e não é deste relatório.** Levantado
  pelo `llm-exec`: os 196 pares vêm de **9 perguntas**, uma delas concentrando
  8 dos 12 defeitos — e **é o mesmo goldset que decidiu o modelo de produção
  por reamostragem**. Se essa concentração derruba a significância de um juiz
  (`qwen3:14b`, p 0,0007 → 0,069), o mesmo raciocínio se aplica ao desempate
  entre `qwen3:14b`, `qwen3.5:9b` e `qwen3.8:27b`. Ninguém aplicou. Isso não
  afirma que a decisão do modelo cai — afirma que ela não foi examinada sob
  este critério.
- **Quais outros números passaram por harness não auditado.** Um corte de 1500
  caracteres mudou 5 FP para 0 e uma recomendação inteira. A pergunta vale para
  as outras fases.
- **Um defeito ainda escapa do melhor juiz:** o MISS do `qwen2.5:14b`
  (`escalate_double_charge_en`, 392 caracteres — não é truncamento).
- **O degrau entre 8,0B e 9,7B não foi localizado**, nem testado um não-Qwen
  nessa faixa.
- **O check de spill da Fase 6 não cobre modelos especulativos.** `# TODO`
  registrado na linha do check em `fase6_concurrency.py`; não consertado.
- **`num_predict` difere entre juízes** (900 para o distill R1, 48 para os
  demais). Efeito observado nulo — `truncado=0` e `ilegivel=0` em todos os
  sete — mas a tabela compara orçamentos diferentes.
- **O limiar de 0,5 s para carga fria** foi escolhido entre 0,004 s e 3,0 s.
  Não há nada entre os dois na amostra; uma carga "morna" cairia em lugar
  desconhecido.

## Achados de instrumentação

Os distills R1 **ignoram `think: false`**: o texto vai para `message.thinking`
e `content` sai vazio quando o orçamento acaba antes
(`done_reason: "length"`). Com `num_predict=48`, 4 de 4 pares deram ilegível —
o que teria sido lido como "juiz confuso" e era falta de token. O harness dá
900 tokens ao distill e reporta `TRUNCADO` separado de `ILEGIVEL`. O
`qwen3:14b` e o `gemma4:26b` honram `think: false` e respondem direto.

O tag `deepseek-r1:8b-llama-distill` **não existe** no registry (o pull retorna
`pull model manifest: file does not exist`). O tag real é
`deepseek-r1:8b-llama-distill-q4_K_M`, `families: ['llama']` — ao contrário do
`deepseek-r1:32b`, que declara `families: ['qwen2']`.

O `gemma4:26b` não estava no store apesar de aparecer como modelo de origem nos
pares; foi puxado hoje (16,9 GB, `families: ['gemma4']`, 25,2B, Q4_K_M).
Espaço no E: depois disso: 631 GB livres de 931 GB.
