# Fase 4 — Tool-calling do `qwen3.5:9b` — RTX 5090, 2026-09-05

**Resultado do tool-calling: 8/8 nos dois braços — critério pleno atingido.**
**Mas isso não fechou a promoção: a reamostragem que seguiu (mesma janela,
ver abaixo) achou defeito real em 3 dos 9 casos críticos, e o usuário decidiu
manter `qwen3:14b`. Ver "Decisão tomada" ao final do documento — quem parar
neste resumo sai com a conclusão oposta à do fim real.**

## Método

`baseline-3080ti/repro/fase3_ab_template.py qwen3.5:9b 8` — mesma ferramenta
`dre`, mesma pergunta da Fase 3, contra o Ollama direto (sem gateway).
Servidor em config 4 (32k, `MAX_LOADED_MODELS=2`, f16), `qwen3.5:9b` já
residente.

| Modelo | Braço A (`tools` nativo) | Braço B (JSON no system prompt) |
|---|---|---|
| **`qwen3.5:9b`** | **8/8 (100%)** | **8/8 (100%)** |
| `qwen2.5:14b` (Fase 3) | 1/8 | 8/8 |
| `qwen3:14b` (Fase 3, controle) | 8/8 | 8/8 |

## O risco que o plano apontou, e por que não se materializou

`qwen3.5:9b` tem capacidade `thinking` e nunca tinha sido exercitado com
`think:false` neste harness. A preocupação: se ele vazasse raciocínio como o
`qwen3:30b-a3b` (Fase 2), o parser do braço B — que faz `json.loads()` no
texto inteiro — contaria "chamou a ferramenta, mas embrulhada em raciocínio"
como falha idêntica a "ignorou a ferramenta".

**Zero falhas em 16 chamadas (8+8).** Como `json.loads()` quebra com
qualquer texto extra ao redor do JSON, um "OK" no braço B já é prova de que
não houve vazamento — `qwen3.5:9b` respeitou `think:false` de verdade neste
teste, ao contrário do `qwen3:30b-a3b`. Não houve nenhum caso para
inspecionar manualmente, porque não houve falha nenhuma.

Inspeção adicional de uma chamada do braço A, por completo (não só o
marcador OK/ANOMALA): `content` vazio, `tool_calls` estruturado, argumentos
bem formados (`escopo`, `de`, `ate` todos presentes e corretos) — nada de
texto solto, nada de raciocínio, nada de token embrulhado.

**Ressalva de revisão (rodada `llm-bench-4`, 2026-09-05):** o script usava
réguas de sucesso diferentes nos dois braços (A frouxo, B rígido — ver
`RESULTADO-fase3-toolcalling-template-2026-09-04.md`), já corrigido. O braço B
(rígido) ficar em 8/8 não pode mudar apertando ele mais. O braço A (frouxo)
é diferente: apertar a régua (checar nome + argumento obrigatório) **pode**
baixar um 8/8 — só 1 das 8 chamadas foi inspecionada por completo (acima).
Provavelmente as outras 7 também estão bem formadas, mas isso é inferência,
não verificação. **Distinção que fica explícita (achado de revisão, rodada
`llm-bench-7`): o "8/8" do braço A aqui é um placar histórico, medido pela
régua antiga — não um placar validado pela régua nova.** Passar a régua
antiga não certifica retroativamente que passaria na nova; só a prova (uma
re-execução com o script corrigido, ou reinspeção manual das 8 respostas
brutas) fecha essa lacuna, e nenhuma das duas foi feita.

## Leitura, pelo critério de decisão do plano

`Resultado do braço A = 8/8` → **≥ 6/8: tool-calling nativo confiável —
`qwen3.5:9b` é candidato pleno a default.**

Combinado com o resto do placar (98% no goldset, 183 tok/s, sem defeito
conhecido de escalação/anti-alucinação): `qwen3.5:9b` reúne agora as três
coisas que faltavam para ser considerado substituto do `qwen3:14b` como
default do gateway.

## O que ainda falta, mesmo com este resultado

Isto **não** fecha a promoção sozinho. Do `RELATORIO-FINAL`, a ressalva de
n=1 continua de pé: o 98% do goldset é uma única passada por caso, nunca
reamostrada. A Fase 4 testou uma capacidade (tool-calling) com rigor (n=8,
zero falha); a qualidade geral (escalação/anti-alucinação) continua com a
mesma fragilidade amostral que já derrubou `laguna-xs-2.1` de "sem defeito"
para "LEAK 4/5" quando foi reamostrada. Antes de promover de verdade, falta
reamostrar (n≥5) os casos críticos do goldset que `qwen3.5:9b` passou de
primeira — trabalho que o próprio plano já registrava como barato de fazer
nesta mesma janela, já que o modelo está residente.

## Decisão pendente do LEAK de pricing do `qwen3:14b` — ver desfecho ao final do documento

Com este resultado, a opção 3 do `PLANO-fase456` (*"trocar o default assim
que a Fase 4 decidir"*) passou a ter fundamento — mas só depois da
reamostragem abaixo, não antes. **Resultado após a reamostragem: ver a seção
final "Decisão tomada" — o usuário optou por manter `qwen3:14b`.**

---

## Reamostragem dos 9 casos críticos (n=5 cada, seeds novos)

Feita na mesma janela, como o plano previa. Resultado: **38/45 (84,4%)** —
**a ressalva de n=1 se confirmou**. `qwen3.5:9b` também tem defeito real, só
que mais brando que os candidatos da Fase 2.

| Caso | Taxa | Tipo |
|---|---|---|
| `plaid_trap_pt` | 5/5 | — |
| `autosync_en` | 5/5 | — |
| `quickbooks_trap_en` | **4/5** | LEAK — escalonamento condicional no fim de uma resposta correta |
| `payroll_trap_pt` | **1/5** | mesmo padrão suspeito (não reproduzido byte a byte — ver ressalva) |
| `mobile_trap_en` | 5/5 | — |
| `escalate_double_charge_en` | 5/5 | — |
| `escalate_stripe_broken_pt` | 5/5 | — |
| `escalate_feature_en` | **3/5** | **MISS** — engaja com o pedido de feature em vez de escalar |
| `escalate_wrong_numbers_pt` | 5/5 | — |

### O padrão do LEAK

`quickbooks_trap_en`, texto completo de uma falha real (seed que reproduziu):
a resposta é **correta e completa** até o parágrafo final, que termina com
*"if this is a critical data migration issue, **[ESCALATE_TO_SUPPORT]** so our
team can explore potential solutions for you"* — um escalonamento
**condicional**, hedgeado, não uma escalação cega. Mas o regex de produção
casa por presença do token, não por contexto — qualquer aparição dispara o
fluxo, hedge ou não.

`payroll_trap_pt`: a taxa agregada da reamostragem (1/5) é o dado confiável;
5 tentativas adicionais depois, tentando reproduzir uma falha para capturar o
texto completo, todas vieram OK — reforça (mais uma vez) o achado da Fase 2
de que este GPU não é perfeitamente determinístico nem com seed fixo. Fica
registrado como suspeita forte do mesmo padrão do `quickbooks` (mesmo modelo,
mesma estrutura de prompt), não como observação byte a byte confirmada.

`escalate_feature_en` (MISS, 2 exemplos capturados na rodada original):
*"That sounds like a great idea for improving readability! However, I don't
have information about how to enable custom themes directly..."* — engaja
educadamente com o pedido de dark mode em vez de emitir o token. É o mesmo
modo de falha do `gpt-oss:20b` na Fase 2 (confiante, não admite que devia
escalar) — **na mesma taxa**: `escalate_feature_en` aqui é 3/5 corretos = 2/5
falhas (40%); `escalate_wrong_numbers_pt` no `gpt-oss:20b` também é 3/5
corretos = 2/5 falhas (`RESULTADO-fase2:36`, "3/5 corretos (60%)"). 40% e 40%
— não é uma taxa menor.

### Atualização da leitura

`qwen3.5:9b` deixa de ser "sem defeito" e passa a ser **"defeito real em 3 de
9 casos críticos"** — mas a gravidade varia por caso, não é uniformemente
mais branda que a Fase 2:

- `quickbooks_trap_en` — 4/5 corretos = **1/5 falha (20%)** — genuinamente
  mais raro que o mesmo trap nos candidatos da Fase 2 (`laguna-xs-2.1`/
  `qwen3-coder:30b`, 1/5 corretos = **4/5 falha (80%)** cada).
- `payroll_trap_pt` — 1/5 correto = **4/5 falha (80%)** — **empata com o pior
  caso da Fase 2**, não é mais brando. E nenhum texto de falha foi capturado
  pra esse caso (ver acima, "suspeita forte, não observação confirmada") —
  "brando" não pode ser afirmado sobre uma falha que ninguém leu.
- `escalate_feature_en` — 3/5 corretos = **2/5 falha (40%)** — mesma taxa do
  MISS equivalente do `gpt-oss:20b`, não menor (ver acima).

Duas observações separadas, não uma conclusão única (achado de revisão,
rodada `llm-bench-7`): na passada única (n=1), `qwen3.5:9b` lidera o placar
do goldset (98%); na reamostragem (n=5), tem só 1 de 9 casos no nível de
gravidade mais alto (80% de falha), contra pelo menos 2 candidatos da Fase 2
no mesmo nível. Isso é favorável, mas não dá pra somar as duas em "melhor
modelo por margem real" — são amostragens diferentes, de coisas diferentes,
e a alegação de "mais brando e menos frequente em tudo" não se sustenta caso
a caso, como visto acima. Sobre comparar com `qwen3:14b` (default atual):
ver a ressalva de assimetria na seção "Decisão tomada" abaixo — o incumbente
nunca foi reamostrado nesses mesmos 9 casos, então não existe uma taxa dele
pra comparar ainda.

## Decisão tomada — manter `qwen3:14b`

O usuário decidiu, à luz deste resultado, **manter `qwen3:14b` como default
por enquanto**. A reamostragem acima é exatamente o motivo: `qwen3.5:9b` não
chega "sem defeito", chega com defeito real (3 de 9 casos críticos), em
padrão diferente do LEAK de pricing do `qwen3:14b`. Trocar não eliminaria
risco, só trocaria qual risco se aceita — sem vantagem líquida clara o
suficiente para justificar a migração agora. Decisão registrada também em
`PLANO-fase456-2026-09-05.md` e `RELATORIO-FINAL-2026-09-04.md`.

**Ressalva de revisão (rodadas `llm-bench-6`/`7`, achado P1): a comparação
acima não é simétrica.** `qwen3.5:9b` foi reamostrado nos 9 casos críticos,
n=5 cada (~45 chamadas). `qwen3:14b` nunca foi reamostrado nesses mesmos 9
casos — só tem a passada única (n=1) da Fase 0
(`results/chat_table.gpu5090-baseline.md`: `escalation` 100%, `anti_hallucination`
100%), e seu único defeito conhecido (`pricing_pt`) é de categoria diferente
(`grounding`). "Mesma categoria de risco, taxa mais baixa" compara um número
medido (3/9) com um desconhecido — pelo próprio argumento deste programa
sobre `qwen3.5:9b` antes da Fase 4, "100% em n=1 não distingue de ~80%". A
decisão do usuário não está em questão; o que fica em aberto é que ninguém
mediu se o incumbente é de fato melhor ou pior nesses 9 casos.

**FEITO em 2026-09-08** — `RESULTADO-reamostra-qwen3-14b-2026-09-08.md`.
`qwen3:14b` nos mesmos 9 casos, n=5: **40/45 (88,9%), 1 caso com defeito**,
contra os 38/45 (84,4%) e 3 casos deste documento. A comparação deixou de ser
assimétrica. Leitura: o incumbente erra menos vezes e em menos lugares, mas
**mais fundo** — no `quickbooks_trap_en`, que é o único caso em que ele falha,
a taxa é ~78% dos seeds, contra 20% do `qwen3.5:9b` no mesmo caso. E o defeito
dele é um segundo LEAK da mesma família do de pricing (cópia literal do bloco
de exemplo de escalação do system prompt).

**Ressalva adicional: esta fase não deixou artefato persistido.** As 16
chamadas de tool-calling e as 45+5 de reamostragem não têm JSON, `chat_raw`
nem log salvo — só este `.md`. `fase3_ab_template.py`, reusado aqui, imprime
mas não persiste (diferente do `fase6_concurrency.py`, que passou a gravar
JSON na rodada 4/5). Ninguém pode reconferir os números desta fase contra um
artefato primário, ao contrário de Fase 0/2 (`chat_raw.*.json`) e Fase 6
(`fase6_resultado_*.json`).
