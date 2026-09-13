# Fase 6b — `OLLAMA_NUM_PARALLEL` sob contexto longo — RTX 5090, 2026-09-12

> **CORREÇÃO DO DONO DA FASE 6 — 2026-09-12.** O mecanismo descrito abaixo
> (*"o Ollama trata o `num_ctx` pedido como total e divide pelos slots"*) está
> **contradito pelo log do próprio servidor**, e com ele cai a tabela de teto
> por requisição. O truncamento é real e os números medidos estão certos; a
> explicação não está. Ver **"Correção: o que o log mostra"**, no fim.

**Resultado: prompts longos são truncados silenciosamente num limite de
metade do contexto do slot. Para prompt curto concorrente (Fase 6) o ganho
continua válido; para requisição única de contexto longo é uma perda pura, e
o servidor não avisa. Nenhuma decisão tomada — este documento é a medição que
a ressalva da Fase 6 pediu.**

Continuação direta de `RESULTADO-fase6-numparallel-2026-09-05.md`, que fechou
com: *"ainda só testado com `qwen3:14b` sozinho... Se o padrão real de
produção for diferente disso, vale medir de novo antes de assumir que o ganho
se generaliza."* Este é esse caso diferente.

## Como apareceu (não foi um teste desta fase)

Medindo outra coisa: um teste de paridade de handoff (Claude vs
`qwen3-coder:30b` local) para o projeto `herdr-mesh-tools`, em que se pede a
uma LLM local que resuma o log de uma sessão longa. Carga oposta à da Fase 6
— **uma requisição, prompt enorme, sem concorrência nenhuma**.

## A medição

| pedido | `num_ctx` declarado | enviado | `prompt_eval_count` | descartado |
|---|---|---|---|---|
| mfc, map-reduce (4 chunks) | 32.768 | ~20.000 tok/chunk | 16.384 | ~18% por chunk |
| mfc, chamada única | 98.304 | 79.393 tok | 49.152 | **38%** |
| mfc, `num_ctx=131072` | 131.072 | — | alocou 262.144 → crash | — |
| omasession | 98.304 | 94.987 tok | **49.154** | **48%** |

`98304 / 2 = 49152`. O `prompt_eval_count` medido foi `49154` — os 2 tokens de
diferença são moldura. Bate na casa da unidade.

## O mecanismo

Com `NUM_PARALLEL=N`, o Ollama trata o `num_ctx` pedido como **total do
servidor** e o divide em `N` slots. Quem pede 98.304 com `N=2` recebe 49.152
por requisição. O log de carga do servidor confirma: `n_ctx=196608`,
`n_ctx_seq=98304`, `n_slots=2`.

Três fontes independentes convergem, nenhuma sabendo das outras:

1. o log de carga do servidor (`llm-exec`, lendo `/api/ps` e o log real);
2. a aritmética de VRAM (0,103 MiB/token para `qwen3-coder:30b`);
3. este `prompt_eval_count`, obtido por acidente medindo outra coisa.

> **Ressalva acrescentada depois (ver "Os dois mecanismos estão confundidos"):**
> as três fontes concordam no **número**, não no **mecanismo**. Tratar
> concordância numérica como confirmação causal foi o erro da primeira versão
> deste documento.

Isso também reexplica o crash em `num_ctx=131072`, antes atribuído a "1,6%
acima do teto": o pedido real de alocação foi **262.144** tokens, o dobro.

## Teto efetivo por requisição — **condicionado à hipótese A, não estabelecido**

> Esta seção só vale se a hipótese A for a certa, e o log aponta contra ela
> (`n_ctx_slot = 98304`, não 49.152). Ver "Os dois mecanismos estão
> confundidos" mais abaixo antes de usar qualquer número daqui. Mantida
> visível em vez de apagada porque foi o raciocínio original e a correção
> só faz sentido ao lado dele.

```
n_ctx total    = (30,3 GiB - ~18 GiB de pesos) / 0,103 MiB/tok ~= 122.000 tok
por requisicao = 122.000 / NUM_PARALLEL
```

| `NUM_PARALLEL` | teto por requisição |
|---|---|
| 1 | ~122.000 tok |
| 2 (produção hoje) | **~61.000 tok** |

## A forma da degradação — o achado que não era esperado

Truncamento silencioso **não produz saída pior**. Produz saída fluente, bem
estruturada, com nomes de arquivo reais — e **identificadores inventados** no
lugar dos que o modelo não viu.

No handoff gerado com 48% do contexto descartado, o modelo:

- afirmou que as rodadas de revisão foram "omasession-12 a 15" e "16 a 18"
  (as reais foram 14–21);
- afirmou, **num campo de GABARITO**, ter "executado o `guard-cases.sh`
  completo 10 vezes" — quando a instrução do projeto é NUNCA rodar esse
  script naquela máquina (fecha todas as janelas; só roda na VM de lab).

Truncamento não degrada a fluência, degrada a **ancoragem factual**. É pior
que saída ruim, porque saída ruim é detectável e esta passa em revisão
superficial — e ainda por cima num campo de gabarito, que é onde ninguém
relê.

## O que NÃO se conclui daqui

**Não se conclui que `NUM_PARALLEL` deva virar 1.** A Fase 6 mediu o ganho de
`=2` com rigor (três medições convergentes, −28% no lote e −41% por
requisição, duas rodadas de revisão cega que acharam e fecharam defeitos
reais). Aquele resultado continua de pé no cenário dele.

O que se conclui é que **`NUM_PARALLEL` não tem valor único certo** — é um
trade-off por carga, e as duas cargas desta casa querem valores opostos:

| carga | quer | por quê |
|---|---|---|
| prompts curtos concorrentes (produção do gateway) | `=2` | limitado por fila |
| requisição única de contexto longo (handoff, resumo de log) | `=1` | limitado por KV cache |

Uma variável de ambiente global não serve às duas. Decidir entre elas exige
saber qual carga domina, e isso não é uma pergunta de medição — é de produto.

## Pendências

- Medir a Fase 6 com `qwen3-coder:30b` (só foi testada com `qwen3:14b`).
- Medir carga combinada dos dois modelos residentes — ressalva ainda aberta
  desde 05/09.
- `~/Devs/llm-bench` **não é um repositório git**. Todos os `RESULTADO-*.md`
  são arquivos sem histórico e sem remote. Este inclusive.

## Correção: o que o log mostra — 2026-09-12

Fui ler as linhas de carga e de requisição no
`C:\ProgramData\ollama-server\ollama.log`. Elas dizem outra coisa.

**O slot recebeu o contexto INTEIRO que foi pedido:**

```
llama_context: n_seq_max  = 2
llama_context: n_ctx      = 196608      <- TOTAL alocado = 2 x 98304
llama_context: n_ctx_seq  = 98304       <- por sequência: os 98304 pedidos, inteiros
srv load_model: n_slots = 2, n_ctx_slot = 98304
slot load_model: id 0 | new slot, n_ctx = 98304
slot load_model: id 1 | new slot, n_ctx = 98304
```

`NUM_PARALLEL=2` **não divide o `num_ctx` entre os slots.** Ele *multiplica* a
alocação total por 2 para dar a cada slot o valor cheio. O oposto do que o
documento afirmava.

**O que trunca é outra coisa, e o log a nomeia:**

```
WARN "truncating input prompt"  limit=49154  prompt=111288  keep=4  new=49154
slot: new prompt, n_ctx_slot = 98304, n_keep = 4, task.n_tokens = 49154
```

Há um **limite de truncamento do lado do servidor** em 49.154, com o slot a
98.304. O truncamento é real e maior do que o documento dizia — **111.288
tokens cortados para 49.154, 56% descartado** — e `keep=4` mostra que sobram
só 4 tokens do início.

### Os dois mecanismos estão confundidos nesta medição

`num_ctx` pedido = 98.304, `NUM_PARALLEL` = 2, limite observado = 49.154.

| hipótese | prevê o limite como | dá 49.154 aqui? |
|---|---|---|
| A — o Ollama divide o `num_ctx` pelos slots | `num_ctx / NUM_PARALLEL` | sim |
| B — o Ollama reserva metade do contexto do slot | `n_ctx_slot / 2` | sim |

**As duas dão o mesmo número porque `NUM_PARALLEL` é 2.** Uma única medição
com `N=2` não as separa — é o mesmo tipo de confundimento que já derrubou uma
conclusão desta bancada esta semana.

A hipótese A já está enfraquecida pelo log (`n_ctx_slot = 98304`, não 49.152).
Se B estiver certa, **`NUM_PARALLEL` não tem efeito nenhum sobre o teto de
prompt** — só sobre o custo de VRAM, que passa a ser `N x num_ctx`.

**O teste que separa:** uma requisição com o mesmo `num_ctx=98304` e
`NUM_PARALLEL=1`. A prevê limite 98.304; B prevê 49.152. Exige mudar variável
de ambiente de máquina e reiniciar o servidor — **não fiz, é decisão do Breno
e mexe em produção.**

### O que isso muda no resto do documento

- **A tabela "Teto efetivo por requisição" não se sustenta como derivada.** A
  fórmula `122.000 / NUM_PARALLEL` pressupõe a hipótese A. E ela ignora que a
  alocação total medida é `N x num_ctx` (196.608 no log), então o custo de
  VRAM e o teto de prompt não escalam do mesmo jeito.
- **Continua de pé, sem depender do mecanismo:** o truncamento é real e
  silencioso; a degradação é de ancoragem factual e não de fluência; e a
  conclusão de **não mexer no `NUM_PARALLEL`** — que agora fica mais forte, não
  mais fraca, porque o mecanismo sequer está estabelecido.
- **O enquadramento de trade-off por carga continua correto** como descrição do
  problema, mas o lado "contexto longo quer `=1`" ainda não tem medição que o
  sustente.

## Ligação com o `llm-gateway` (lacuna 9)

Reportado ao `llm-exec`, que já agiu. A proposta inicial daqui — conferir
`prompt_eval_count >= tokens_enviados * 0,98` — foi **corrigida por ele e a
correção é melhor**: o gateway não tokeniza, só tem chars, então esse limiar
exigiria estimar tokens a partir de chars — a mesma família de heurística que
já falhou na guarda de eco do `llm-bench`.

A forma exata: **declarar `num_ctx` primeiro torna a conferência exata**. Com
o teto declarado, não se estima nada — se o `prompt_eval_count` voltar colado
no teto declarado, o prompt foi cortado, ponto. "Declarar" e "conferir" não
eram duas metades independentes da lacuna 9; uma é o que torna a outra
possível.

Já mergeado lá: `e3d4ce1` faz o `tasks.py` registrar `input_chars` ao lado de
`input_tokens` — sozinho o `input_tokens` não denuncia nada, ao lado dos chars
vira uma razão conferível depois do fato. Com a ressalva escrita no código e
no `AGENTS.md` de que **registrar não é conferir**. A guarda em si fica para
depois do `num_ctx` declarado, e passa por revisão antes, porque muda
comportamento de todos os consumidores e o valor certo é por modelo.
