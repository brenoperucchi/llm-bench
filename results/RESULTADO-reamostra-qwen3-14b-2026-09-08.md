# Reamostragem do `qwen3:14b` nos 9 casos críticos — 2026-09-08

**Fecha a lacuna que duas rodadas de revisão cega apontaram independentemente
(`llm-bench-6` e `llm-bench-7`):** o desafiante `qwen3.5:9b` tinha sido
reamostrado nos 9 casos críticos (n=5) e "perdido" por revelar 3 defeitos,
enquanto o incumbente `qwen3:14b` nunca passara pelo mesmo teste — só tinha a
passada única da Fase 0. Comparar "taxa mais baixa" entre os dois comparava um
número medido com um desconhecido. Agora não mais.

## Método

`baseline-3080ti/repro/reamostra_criticos.py qwen3:14b 5` — os mesmos 9 casos
da Fase 4 (5 traps de anti-alucinação + 4 de escalação real), n=5 cada,
45 chamadas, seed variando por repetição, `THINK=false`, mesmo system prompt e
mesmo auto-check do goldset. **Artefato persistido** em
`results/reamostra_criticos_qwen3-14b_*.json` com cada resposta, seed e
auto-check — o achado `llm-bench-7` era que a Fase 4 é a única fase decisória
sem artefato reconferível; esta não repete o erro.

## Resultado

| Caso | `qwen3:14b` | `qwen3.5:9b` (Fase 4) |
|---|---|---|
| `plaid_trap_pt` | 5/5 | 5/5 |
| `autosync_en` | 5/5 | 5/5 |
| **`quickbooks_trap_en`** | **0/5** | 4/5 |
| `payroll_trap_pt` | 5/5 | **1/5** |
| `mobile_trap_en` | 5/5 | 5/5 |
| `escalate_double_charge_en` | 5/5 | 5/5 |
| `escalate_stripe_broken_pt` | 5/5 | 5/5 |
| `escalate_feature_en` | 5/5 | **3/5** |
| `escalate_wrong_numbers_pt` | 5/5 | 5/5 |
| **Agregado** | **40/45 (88,9%)** | 38/45 (84,4%) |
| **Casos com defeito** | **1 de 9** | 3 de 9 |

## O defeito: um segundo LEAK, com a mesma assinatura do de pricing

`quickbooks_trap_en` é um **trap de anti-alucinação** — o caso espera que o
modelo responda direto, sem escalar. O `qwen3:14b` escala, e a resposta é:

> *"I don't have enough information to help with this specific issue.
> **[ESCALATE_TO_SUPPORT]**"*

Esse texto é o **bloco 87–89 do `prompts/system_prompt.txt`** copiado
literalmente — o exemplo do formato de escalação, incluindo a segunda frase,
que pede o e-mail do usuário para abrir ticket (é ela que torna a resposta
operacionalmente pior, não só errada). A reprodução literal é **observação direta**; que ela seja a *causa* do
roteamento errado é **hipótese**, a mesma que o `ACHADO` do LEAK de pricing
levanta — a igualdade de texto identifica o que foi produzido, não o mecanismo
que decidiu escalar, e "cópia em vez de geração" opõe duas coisas que não são
alternativas num LLM. O que os dois casos compartilham, e isso é fato: o mesmo
bloco do system prompt sai literal, com assinatura de alta confiança. O default de produção tem, portanto,
**dois LEAKs conhecidos da mesma família**, não um.

### Frequência: alta, mas não determinística

A rodada de n=5 deu 0/5 com respostas byte-idênticas, o que me levou a escrever
"100% determinístico". **Estava errado**, e a amostra ampliada mostra por quê:

| Seed | Resultado |
|---|---|
| 1017, 1034, 1051, 1068, 1085 | falha (5) |
| 42, 7 | falha (2) |
| 1, 999 | **passa** (2) |

**~7 falhas em 9 seeds distintos.** LEAK de alta frequência, não determinístico.

**Segunda correção** (rodada `llm-bench-8`): eu tinha atribuído as 5 respostas
idênticas a "correlação da progressão aritmética de seeds". **Isso também era
overclaim, e não foi testado.** A explicação mais simples, e que o artefato
sustenta, é outra: as 5 respostas têm `eval_count=59` idêntico e `wall_s` de
0,4 s — a mesma assinatura de distribuição concentrada que o `ACHADO` do LEAK
de pricing já descrevia. Quando a distribuição é assim, *qualquer* seed produz
o mesmo texto; o seed decide se o modelo entra no modo, não o que ele escreve
depois de entrar. Além disso, seeds **fora** da progressão (42 e 7) também
falharam — se a progressão fosse a causa da identidade, esses não deveriam
casar. O enunciado honesto é: **a afirmação universal veio de n pequeno; dois
seeds que passam foram encontrados ao ampliar.** Nada aqui prova nem refuta
correlação de PRNG, que não foi medida.

## O que foi descartado como causa

Na Fase 0 (04/09) este caso **passava**, com `seed=42`, e o artefato prova
(`results/chat_raw.gpu5090-baseline.json`: `auto_score` 1.0, resposta
substantiva e correta). Hoje `seed=42` falha. Testei as hipóteses:

- **`NUM_PARALLEL=2`** (aplicado na Fase 6, mudança que eu recomendei):
  **descartado** — instância isolada com `NUM_PARALLEL=1`, mesmo store, dá o
  mesmo 0/5.
- **`MAX_LOADED_MODELS=2`**: descartado pelo mesmo teste (a instância isolada
  rodava com `=1`).
- **System prompt alterado**: descartado — `diff` limpo contra o backup, e o
  tamanho (5110 bytes) não bate com nenhuma das três variantes experimentais.
- **Mudança de store (C: → E:)**: blobs conferidos com tamanho idêntico, e o
  modelo produz saída coerente.

### Questão da regressão: FECHADA em 2026-09-08

Teste sugerido pela rodada `llm-bench-8` e executado com proveniência gravada
(`baseline-3080ti/repro/seed_ab_instancia.py`, artefato
`results/seed_ab_instancia_*.json` com `OLLAMA_URL`, versão do Ollama,
quantização e hash do system prompt de cada lado):

| seed | produção (NP=2, MAX=2) | isolada (NP=1, MAX=1) |
|---|---|---|
| 42 | passa | passa |
| 7 | falha | falha |
| 1 | passa | passa |
| 999 | passa | passa |
| 1017 | falha | falha |

**Duas conclusões, as duas firmes:**

1. **Config está descartada.** As duas instâncias dão resultado **idêntico nos
   cinco seeds**. `NUM_PARALLEL` e `MAX_LOADED_MODELS` não influenciam este
   caso — nem em ocorrência, nem em frequência.
2. **Não houve regressão, e agora há demonstração direta.** O `seed=42` falhou
   **2 de 2** na manhã de 08/09 (instância isolada) e passa **2 de 2** poucas
   horas depois, nas duas instâncias, com mesmo modelo, mesmo prompt e mesma
   config. Um mesmo seed muda de resultado **entre sessões**. O flip de 04/09
   para 08/09 não precisa de nenhuma causa além disso — é o achado da Fase 2
   ("esta GPU não é determinística nem com seed fixo"), agora medido de forma
   controlada em vez de inferido.

**Terceira correção que isso força:** a tabela de "~7 falhas em 9 seeds"
acima trata resultado por seed como se fosse propriedade estável do seed. **Não
é.** Seeds 7 e 1017 falharam nas duas sessões e 1 e 999 passaram nas duas, mas
o 42 inverteu — então contagem por seed não é medida confiável. O que se pode
afirmar é a **taxa agregada sobre amostras**, não o comportamento de um seed
específico. A ordem de grandeza (maioria falha, alguns passam) se mantém; a
precisão de "~78%" não.

## O que isso muda na decisão do default

A justificativa registrada em 05/09 para manter o `qwen3:14b` era: *"trocar não
eliminaria risco, só mudaria qual risco se aceita"*. A revisão apontou que essa
frase comparava um número medido com um desconhecido. **Agora os dois números
existem, e a frase se sustenta — com uma nuance que ela não capturava:**

- No **agregado**: 40 contra 38, em 45. **Diferença de duas chamadas, com
  n=5 por caso — indistinguível.** Não dá para chamar de "melhor"; este
  programa já rejeitou leituras de diferença menor que o ruído (a Fase 6
  exigiu três medições convergindo antes de afirmar um ganho).
- Em **largura**, o incumbente é melhor, e este é o único item que os números
  carregam: **1 caso com defeito contra 3**.
- Em **profundidade**, os dois empatam: o pior caso do incumbente
  (`quickbooks_trap_en`, 0/5 aqui, ~78% na extensão) e o pior do desafiante
  (`payroll_trap_pt`, 1/5 = 80% de falha) estão no mesmo patamar.

**Correção de uma leitura que eu já tinha retirado e reintroduzi** (achado da
rodada `llm-bench-8`): uma versão anterior desta seção dizia que o incumbente
erra "mais fundo" e o desafiante "de forma mais rasa e mais aleatória". Isso
contradiz o `RESULTADO-fase4`, que eu mesmo corrigi nas rodadas 6/7 e que diz
textualmente que o `payroll_trap_pt` do `qwen3.5:9b` *"empata com o pior caso
da Fase 2, **não é mais brando**"*. A frase que os números sustentam é:
**mesma profundidade máxima, o desafiante mais largo, agregado
indistinguível.**

"Trocar não eliminaria risco, só mudaria qual risco" continua verdadeira — por
largura, não por profundidade. Qual perfil é preferível é decisão de produto,
não de medição; o que mudou é que agora os dois números existem.
