# Achado: `qwen3:14b` escala deterministicamente uma pergunta de preço — 2026-09-04

**Severidade:** alta. `qwen3:14b` é hoje o `default_model` do perfil `local` no
`llm-gateway` (`ryzen9-qwen3-14b`), escolhido em 02/09 por um A/B de
tool-calling (12/12 vs 4/12 do qwen2.5) que **não cobria grounding**. Este
achado é da mesma classe de defeito — direção errada, mas real.

## O que acontece

Caso `pricing_pt` do goldset (`goldset_chat.json`, categoria `grounding`):

```
Prompt: "Quanto custa exatamente o plano Pro por mês?"
Esperado: NÃO escalar; direcionar para Settings → Billing / pricing; PT.
```

`qwen3:14b` responde, **em inglês**, com escalação:

```
I don't have enough information to help with this specific issue. **[ESCALATE_TO_SUPPORT]**

I'd like to forward your question to our support team so they can investigate
and get back to you. Please provide your email address and I'll create a
support ticket for you.
```

## Reproduzido 6/6, sem seed fixa

Descoberto na Fase 0 do goldset (`seed=42`, 1 amostra: `auto_score=0,40`).
Repetido 5× adicionais com `temperature=0.7`, **sem seed** (para descartar
determinismo por seed): **5/5 idênticos, caractere por caractere**, incluindo o
mesmo trocadilho de idioma. `wall_s` na repetição original: 0,4 s — sugere
resposta de baixa entropia / atalho do modelo, não geração "pensada".

Não é ruído amostral. É comportamento sistemático do modelo neste prompt, com
este system prompt, nesta configuração (`num_ctx=8192`, `think=false`).

## Por que isso é grave em produção

Escalar uma pergunta de preço vira ticket de suporte desnecessário a cada
usuário que pergunta "quanto custa o Pro" — exatamente o tipo de carga que a
automação deveria absorver. É a mesma classe de risco que o
`RELATORIO_CONSOLIDADO.md` (bench de CPU) chamava de LEAK, só que na direção
"escalou quando não devia", e nunca apareceu nesse relatório porque o
`gemma4:26b` daquele bench não tinha esse defeito.

## O que não sabemos ainda

- Se é específico deste caso ou de perguntas de preço em geral (só há 1 caso
  `grounding` no goldset).
- Se troca de idioma (PT→EN) é o mesmo defeito ou um segundo, correlacionado.
- Se acontece nos outros modelos qwen3.x (`qwen3.5:9b` passou neste mesmo caso
  com 100%, então não é generalizado à família).
- Se está relacionado ao mesmo confusor "modelo vs template do registry Ollama"
  já registrado em `baseline-3080ti/tool-calling-ab-2026-09-02.md` para
  tool-calling — este caso não usa `tools`, então é evidência de que o
  problema (se for de template) não se limita a tool-calling.

## Ação recomendada

Não trocar o default do gateway com base só nisto — mas achatar a prioridade:
antes de qualquer decisão da Fase 2 (que já compara `qwen3.5:9b`, hoje o melhor
score da Fase 0), vale confirmar se `qwen3.5:9b` também tem algum ponto cego
equivalente com um segundo caso de grounding, e escrever 2–3 casos novos de
"pergunta de preço/billing" no goldset — hoje há só 1, e ele sozinho já achou
isto.

## Fonte

`results/chat_raw.gpu5090-baseline.json`, entrada `model=qwen3:14b,
id=pricing_pt`. Repetição em `/tmp` desta sessão, não salva à parte (script
ad-hoc, 5 chamadas diretas ao `/api/chat`, mesmo prompt e system prompt do
goldset).

## Reprodução literal confirmada, byte a byte — mecanismo é hipótese

A resposta original é **texto idêntico, byte a byte**, ao bloco `**Escalation
response format:**` do próprio system prompt (`prompts/system_prompt.txt`) —
isso é observação direta, comparação de string confirmou igualdade exata.

**O que essa igualdade NÃO prova** (achado de revisão, rodada `llm-bench-7`):
um LLM não tem um modo de "recuperação" separado de "geração" — ele sempre
gera token a token. A igualdade de texto mostra *o quê* foi produzido, não
*por quê* a amostragem convergiu para essa sequência específica com tanta
confiança. A leitura de que a latência baixa (0,4s) e o determinismo das
primeiras repetições vêm de "alta confiança numa sequência quase memorizada"
é uma hipótese plausível — sequências de alta probabilidade tendem a ser mais
rápidas e mais determinísticas —, mas não foi isolada de outras explicações
(ex.: a sequência ser curta o suficiente para não distinguir latências nesse
patamar). Fica registrado como hipótese razoável, não como mecanismo provado.

## Três tentativas de correção, nenhuma adotada

Testadas em `prompts/system_prompt.experimental-v{1,2,3}.txt`, nunca aplicadas
ao canônico por mais de alguns minutos (v2 foi promovido e revertido no mesmo
dia depois de expor uma regressão pior). **`prompts/system_prompt.txt`
permanece idêntico ao original** — cópia de segurança em
`prompts/system_prompt.pre-fix-2026-09-04.txt`.

| Variante | Mudança | `pricing_pt` (qwen3:14b) | Token `[ESCALATE_TO_SUPPORT]` (qwen2.5:14b, 2 casos de escalação real) |
|---|---|---|---|
| original | — | 0/8 | 4/4 e 4/4 (100%) |
| v1 | de-literaliza só o bloco de formato de escalação | 0/8 — sem efeito | não testado |
| v2 | v1 + desambigua o gatilho genérico "qualquer pergunta que não sei" | **5/8 (62,5%)** — melhora real | **6/12 — regressão nova e mais grave** (medição ad hoc, ver nota abaixo) |
| v3 | mesmo gatilho do v2, mas isola o token numa linha própria marcada como reuso literal obrigatório | **0/8 de novo** | 10/12 — melhor, não resolvido |

**v2 trocou um defeito visível (LEAK: escala quando não devia) por um
silencioso (token de escalação real omitido)** — pior, porque é exatamente o
modo de falha que o regex de produção não detecta: sem o token exato, a
escalação simplesmente não acontece e ninguém percebe. Foi por isso que v2
foi revertido no mesmo dia em que foi promovido.

**Nota — são duas medições distintas da mesma regressão, não uma só:** a
tabela acima (6/12) é uma contagem ad hoc feita durante a investigação; **2 de
4** é a contagem no artefato salvo daquela rodada (`chat_table.gpu5090-postfix.md`),
com denominador diferente (só os 4 casos de escalação real do goldset, não os
12 chamados ad hoc). As duas dão 50% de falha — consistente — mas são
amostras diferentes, não a mesma medição relatada duas vezes.

v3 tentou consertar isso isolando o token numa linha própria com instrução
explícita de cópia literal — melhorou o token (10/12) mas **destruiu o ganho do
gatilho de pricing que vinha do v2** (voltou a 0/8), mostrando que as duas
mudanças não são independentes: a redação do bloco de formato interage com a
decisão de escalar ou não, não só com a fidelidade do token.

**Conclusão: três tentativas, três resultados incompatíveis entre si, com
amostra pequena (n=6–8 por ponto).** Isso deixou de ser ajuste de frase e virou
engenharia de prompt de verdade — precisa de amostra maior (n≥20 por variante),
mais variações testadas em paralelo, e idealmente validação contra o texto real
de produção (`app/services/chat/process_message.rb`), não só a cópia deste
bench. Não retomado nesta sessão.
