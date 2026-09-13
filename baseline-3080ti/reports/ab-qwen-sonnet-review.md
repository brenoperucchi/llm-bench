# Avaliação independente: qwen3:14b vs. leitura Sonnet — rodada de oportunidade (posts 47, 236, 287, 493, 656)

**Identidade do modelo avaliador:** Claude Sonnet 5 (`claude-sonnet-5`), executado via Claude Code, sessão de 2026-08-27.
**Papel neste documento:** revisor independente, sem acesso ao raciocínio interno do qwen3:14b (não persistido pelo pipeline) — a avaliação compara apenas o material de entrada (post, thread, métricas) contra o relatório validado e persistido em `analysis_runs.response_json`.

---

## 1. Metodologia

- Leitura direta do SQLite `data/local-staging.db` (tabelas `analysis_runs`, `posts`, `post_comments`, `classifications`, `curation_events`), sem alteração de código ou dados.
- Extração de `request_json` (evidence ledger determinístico + material bruto enviado ao modelo), `response_json` (relatório validado + `metadata.validation_warnings`) e `radar_projection_json` dos `analysis_runs` 1653–1657 (post_id 47, 236, 287, 493, 656; provider `ollama`, model `qwen3:14b`, adapter `ollama-investigator-v2-structured-schema`, prompt `opportunity-report-v1-ollama-v1`, `content_level=thread`).
- Leitura de `src/insights_collector/investigation.py` para entender exatamente o que é **determinístico pelo backend** (grade de evidência, `business_clarity`, validação de citações, gating de veredito para grade C/D) versus o que é **decisão do modelo** (verdict, recommended_path, hypotheses, quais trechos citar).
- Para cada post, comparação literal: texto original + comentários (via `post_comments`/`request_json.input`) contra `observed_facts`, `customer`, `offer`, `verdict`, `recommended_path`, `risks`, `not_answered` do relatório persistido.
- Separação explícita de **fato** (citação literal validada pelo backend, presente na fonte), **hipótese** (`hypotheses[]`, marcado como tal pelo próprio schema) e **ausência** (o que não foi dito, coberto por `missing_evidence`/`not_answered`).
- Tokens do qwen3:14b: valores reais de `metadata.prompt_eval_count`/`eval_count`/`total_duration` (Ollama). **Tokens do Sonnet nesta sessão: não disponíveis** — a ferramenta usada não expõe contagem própria de tokens por chamada; nenhum número é inventado.

Importante: o backend calcula o `evidence_grade` (A–D) **antes** de qualquer chamada ao modelo, a partir de sinais estruturais (profundidade do conteúdo, nº de comentários, comentários independentes, métricas, marcadores lexicais de produto/cliente/oferta/dinheiro). O grade **não avalia coerência ou veracidade do conteúdo** — apenas cobertura estrutural. Isso é relevante para várias divergências abaixo.

---

## 2. Tabela comparativa

| post_id | run_id | grade (determinístico) | verdict (qwen) | recommended_path | verdict_confidence | customer.status | offer.status | observed_facts válidos / enviados | tokens (prompt/eval) | duração |
|---|---|---|---|---|---|---|---|---|---|---|
| 47 (`saas01`, @brunobertolini) | 1653 | A (9 pts) | adaptable | replicate | 0.95 | hypothesis | hypothesis | 6/6 (com normalização) | 4096/1644 | 32.2s |
| 236 (`Cobrando.app`, @ThiagoMonechesi) | 1654 | A (10 pts) | serviceable | replicate | 0.95 | unknown | unknown | 1/6 (5 descartados) | 4096/2028 | 33.6s |
| 287 (@brunobertolini, texto truncado) | 1655 | A (8 pts) | evidence_insufficient | collect_evidence | 0.62 | unknown | unknown | 2/2 | 3894/1072 | 20.7s |
| 493 (`Aleth`, POC, @brunobertolini) | 1656 | A (10 pts) | replicable | replicate | 0.75 | unknown | unknown | 5/6 (1 alucinado descartado) | 4096/1538 | 29.6s |
| 656 (`Engravidei`, terceiro, @leonardoperin8) | 1657 | A (8 pts) | adaptable | adapt | 0.95 | **observed** | **observed** | 6/6 | 4096/1196 | 23.9s |

Todas as cinco amostras receberam grade **A** — o que confirma o enunciado do usuário, mas também expõe uma limitação: o grade determinístico mede volume/estrutura da evidência (thread + ≥3 comentários independentes + métricas + marcadores lexicais), não a qualidade, coerência ou verificabilidade do conteúdo. Os posts 287 (texto truncado) e 656 (números com hedge textual "estimado") também saíram como grade A.

---

## 3. Análise individual

### Post 47 — `saas01`, run 1653 — ⚠️ falha mais grave da amostra

**Fato:** o post afirma "228k de faturamento, 110k de lucro" em 6 meses; texto foi corretamente citado como `post_text`, `third_party: False` (autodeclaração, não confirmada por terceiros).
**Fato disponível e não usado:** o comentário `2084995480509919604` ("Manda o link do seu saas, vamos ver se é vdd mesmo") é imediatamente seguido pela resposta do próprio autor (`comment:2084998876952441288`, `is_author_reply=1`): **"é mentira, inventei tudo isso ai"**. Este comentário estava no `source_refs`/`text_source_refs` do ledger (citável) e não aparece em nenhum campo do relatório — nem em `observed_facts`, nem em `risks.false_positive`, nem em `not_answered`.
**Hipótese do qwen:** "O SaaS tem um modelo de negócios escalável e com margem de lucro atraente" (confiança 0.9), baseada diretamente no número não confirmado.
**Ausência:** nenhuma menção ao desmentido do próprio autor. `risks.false_positive` cita apenas um risco genérico ("faturamento e lucro podem estar inflados"), sem referenciar a evidência textual concreta disponível para essa suspeita.
**Contradição interna:** `verdict=adaptable`, `recommended_path=replicate`, `verdict_confidence=0.95` — a confiança mais alta da amostra — coexistindo com `customer.status=hypothesis` e `offer.status=hypothesis` (nenhuma das duas entidades confirmadas). O schema não impede essa combinação para grade A/B; só grade C/D força `evidence_insufficient`.
**Falso positivo/negativo:** trata-se de um **falso negativo grave** — evidência textual literal que desafia a alegação central do post foi ignorada, mesmo disponível e citável, e o relatório entregou o veredito mais assertivo da amostra em cima exatamente dessa alegação.
**Ruído no processo:** 3 itens de `missing_evidence` do qwen foram descartados por código inexistente no ledger (`code` fora dos permitidos), sinal de que o modelo aproxima o formato em vez de copiar os códigos do ledger.

### Post 236 — `Cobrando.app`, run 1654

**Fato:** thread com 39 comentários, `business_clarity.band=clear` (87/100) — a maior cobertura estrutural da amostra.
**Falha de citação:** 5 dos 6 `observed_facts` do qwen foram descartados na validação — 3 por `source` excedendo o limite de tamanho (o modelo colou um parágrafo inteiro no campo que deveria ser uma referência curta) e 2 por referenciar evidência inexistente. Restou apenas 1 fato, substituído pelo fallback determinístico do backend (citação do `post_text`). Ou seja: **o relatório persistido não tem nenhuma citação de comentário válida**, apesar de o thread ser o mais rico da amostra.
**Ausência:** o post afirma explicitamente "try it for free" — sem preço definido — e o qwen manteve corretamente `offer.status=unknown` e `monetization=unknown` (acerto). Porém `not_answered` inclui "What is the pricing model and monetization strategy" e "How does it differentiate" quando o material continha pistas parciais ignoradas: um comentário cita um concorrente direto e mais barato ("Yo uso https://fama.com.ar mas barato") e outro confirma publicação em diretório de terceiros ("It's already published on argentino.dev") — nenhum dos dois foi citado.
**Contradição interna:** `verdict=serviceable`, `recommended_path=replicate`, confiança 0.95, com `customer.status=unknown` **e** `offer.status=unknown` simultaneamente — recomendar replicação de um negócio cuja monetização é totalmente desconhecida, com confiança máxima, é logicamente inconsistente mesmo dentro das próprias categorias do schema.

### Post 287 — thread truncada, run 1655 — ✅ único acerto de julgamento holístico

**Fato:** `posts.truncated=1`, `truncation_reason='time_budget'`; o texto do post literalmente termina em "~50k dol" (cortado). Os 7 comentários capturados no thread (MCP, Ray Tracing, revisão de PR com Claude) **não têm relação temática aparente com o conteúdo do post** — possível problema de anexação de captura, não de leitura do modelo.
**Decisão do qwen:** `verdict=evidence_insufficient`, `recommended_path=collect_evidence`, confiança 0.62 (a mais baixa da amostra) — **escolha voluntária**, já que o grade era A (8 pts) e não força esse veredito (só C/D forçam). O modelo reconheceu a fragilidade real do material mesmo com um grade estruturalmente aprovado.
**Avaliação:** este é o único caso da amostra em que o julgamento do modelo divergiu do "grade permite mais" na direção conservadora certa. Vale registrar como achado operacional à parte: a possível incoerência tópica do thread capturado sugere revisão da etapa de captura/anexação de comentários para este post, independente da qualidade do modelo.

### Post 493 — `Aleth` (POC pré-venda), run 1656

**Fato:** o próprio autor declara estar em fase de prova de conceito, ainda testando por 7 dias antes de "empacotar pra venda", perguntando à comunidade se R$97 é "um bom valor" — ou seja, **não há preço fechado, cliente pagante ou venda realizada**.
**Ausência:** os 5 `observed_facts` válidos vêm exclusivamente de `post_text`; nenhum dos 8 comentários do thread foi citado, embora contenham sinais de mercado relevantes — concorrentes gratuitos nomeados ("basic memory, openhuman, gbrain"), um usuário cogitando construir produto similar e questionando escalabilidade como SaaS, e uma pergunta direta sobre uso B2B. `not_answered` lista "differentiate from other similar products" como pergunta aberta, quando parte da resposta (existência de alternativas gratuitas nomeadas) estava no material fornecido e não foi usada.
**Alucinação:** um `observed_facts[5]` foi descartado com o erro `quote is not an excerpt from its source` — citação fabricada, não presente literalmente na fonte. É o único caso de invenção literal de trecho na amostra (as demais falhas de citação em 236 foram formatação/referência errada, não texto inventado). Além disso, `observed_facts[1]` e `observed_facts[4]` são duplicados idênticos (mesma citação repetida), indicando baixa diversidade/qualidade na geração.
**Julgamento:** `verdict=replicable`, `recommended_path=replicate`, confiança 0.75, para um produto sem nenhuma venda confirmada. `customer.status` e `offer.status` corretamente `unknown`, mas o veredito/caminho recomendado ainda comunica "replicar" — uma leitura mais conservadora seria justificável dado o estágio pré-comercial explícito no próprio texto.

### Post 656 — `Engravidei` (app de terceiro), run 1657 — ⚠️ maior erro de rotulagem de status

**Fato central mal interpretado:** o post **não é do autor sobre o próprio produto** — é um post de terceiro (@leonardoperin8) comentando sobre o app de outra pessoa, citando "R$13k MRR **estimado**" e "71k downloads por mês" (linguagem de estimativa, provavelmente de ferramenta de tracking de app store), e mencionando que "@gabrielbuzziv já provou que esse nicho dá pra fazer grana" — outro terceiro, referência indireta.
**Erro de status:** apesar do hedge textual explícito ("estimado"), o qwen marcou `customer.status="observed"` e `offer.status="observed"` (não `hypothesis`), com `monetization="MRR estimado de R$13k"` — o próprio texto do campo contém a palavra "estimado", mas o `status` categórico foi elevado a "observado" mesmo assim. É a única amostra em que uma métrica auto-rotulada como estimativa foi tratada com o status de maior confiança do schema.
**Ausência mais significativa da amostra inteira:** entre os 17 comentários do thread há um testemunho de cliente pagante, independente e em primeira pessoa: **"Minha esposa usa esse ai e paga tbm. Ta gravida novamente e sempre sou esse."** (`is_author_reply=False`, terceiro genuíno). Esta é exatamente a categoria de evidência que o schema foi desenhado para capturar (`customer.status=observed` com origem de terceiro) — e é, no conjunto de 5 relatórios, a evidência de maior qualidade disponível para qualquer post da amostra. Não foi citada em `observed_facts`, `customer.who` nem em nenhuma hipótese.
**Resultado:** o relatório se apoiou em números estimados de terceiro para "observar" cliente e oferta, e ignorou o único depoimento real e verificável de um cliente pagante disponível em todo o lote.

---

## 4. Divergências onde uma leitura Sonnet mudaria a decisão

| post_id | decisão do qwen | mudaria com leitura Sonnet? | por quê |
|---|---|---|---|
| 47 | adaptable / replicate / 0.95 | **Sim — reversão forte** | Desmentido literal do autor disponível e ignorado; confiança deveria cair substancialmente e `recommended_path` não deveria ultrapassar `collect_evidence`/verificação até o desmentido ser resolvido. |
| 236 | serviceable / replicate / 0.95 | **Sim — parcial** | Recomendar replicação com confiança máxima sobre `customer.status=unknown` e `offer.status=unknown` é internamente inconsistente; confiança deveria ser mais baixa e a citação do concorrente (`fama.com.ar`) deveria aparecer para embasar diferenciação. |
| 287 | evidence_insufficient / collect_evidence / 0.62 | **Não** | Leitura Sonnet concorda com a cautela do qwen; adicionaria apenas uma nota operacional sobre possível desalinhamento do thread capturado. |
| 493 | replicable / replicate / 0.75 | **Sim — parcial** | Produto ainda em POC pré-venda, sem preço fechado nem cliente; veredito mais adequado seria `adaptable` ou `evidence_insufficient`, incorporando os concorrentes citados nos comentários ignorados. |
| 656 | adaptable / adapt / 0.95, customer/offer `observed` | **Sim — reversão de status** | Números com hedge textual ("estimado") de fonte de terceiro não deveriam virar `status=observed`; o testemunho real de cliente pagante disponível no thread deveria ser a evidência central, não os números estimados. |

Em 4 das 5 amostras (47, 236, 493, 656) uma leitura Sonnet chegaria a um veredito, `recommended_path` ou nível de confiança diferente do persistido — não porque o backend falhou (as regras determinísticas de grade C/D nunca precisaram ser acionadas, já que todos os grades eram A), mas porque **não existe hoje uma verificação determinística que impeça `recommended_path` de nível avançado (`replicate`/`offer_service`) quando `customer.status` e/ou `offer.status` permanecem `hypothesis`/`unknown`** — essa lacuna afeta justamente os relatórios de maior confiança da amostra.

---

## 5. Utilidade do qwen3:14b para este trabalho

**Onde funciona bem:**
- Segue o formato JSON estruturado (`format` schema do Ollama) com poucas violações estruturais graves — a maior parte dos avisos são normalizações cosméticas (`"post text"` → `"post_text"`, `"comments"` → `"comment:<id>"`), que o backend corrige silenciosamente.
- Em um caso (post 287), demonstrou julgamento holístico correto, rebaixando a confiança mesmo com grade A — evidência de que o modelo não segue cegamente o grade estrutural.
- Nunca violou o guardrail de grade C/D (não havia caso na amostra, mas as regras de validação em `investigation.py` estão testadas e o modelo não tentou burlar campos obrigatórios do schema).

**Onde falha, de forma recorrente:**
1. **Códigos de `missing_evidence` inventados em 100% das 5 rodadas** (todas tiveram itens descartados por `code` desconhecido) — o modelo não copia literalmente os códigos permitidos do ledger, apesar de instrução explícita no prompt.
2. **Citação de comentários é inconsistente e às vezes falha por completo**: 0/6 válidos em 236 (thread com 39 comentários — a mais rica da amostra), enquanto post_text-only (ignorando comentários disponíveis) ocorreu em 493 e 656.
3. **Uma alucinação literal de trecho** (493) e **um caso de rotulagem de status excessivamente confiante** sobre dado explicitamente hedgeado como estimativa (656).
4. **Omissão da evidência mais crítica da amostra** (o desmentido do autor no post 47) — o maior risco observado neste lote, pois o relatório resultante é também o de maior confiança e ação recomendada mais agressiva.
5. **Inconsistência entre veredito/caminho recomendado e o próprio `customer.status`/`offer.status`** que o modelo retornou — em 3 de 5 casos, `recommended_path=replicate` conviveu com entidades marcadas `hypothesis`/`unknown` pelo próprio relatório.

O trabalho pesado de segurança nesta arquitetura é feito pelo **backend determinístico** (grade, `business_clarity`, validação de citação, gating C/D) — não pelo modelo. Isso é desenhado corretamente para o pior caso (grade baixo), mas deixa os relatórios de **grade A**, que são justamente os que chegam a um humano com mais confiança e recomendação mais agressiva, sem verificação de coerência interna. É exatamente nesses relatórios de grade A que o qwen3:14b, nesta amostra, cometeu as falhas mais consequentes.

---

## 6. Conclusão executiva

Dos 5 relatórios avaliados (todos grade A determinístico), **1 concordância plena com uma leitura mais cuidadosa (post 287)**, **3 divergências parciais por inconsistência interna ou evidência ignorada mas não necessariamente perigosa (236, 493)**, e **2 falhas de alto risco** (47 — desmentido do autor ignorado sob a recomendação mais confiante da amostra; 656 — estimativa de terceiro elevada a "observado" enquanto o único testemunho real de cliente pagante do lote foi ignorado). Em nenhum caso o qwen produziu um relatório inválido ou fora do schema em definitivo — a rede de validação do backend sempre conseguiu normalizar ou descartar o que não se encaixava.

**Isto não é um teste com poder estatístico** — é uma auditoria qualitativa de 5 casos, não uma medição de taxa de erro generalizável ao pipeline inteiro.

## 7. Recomendação de pipeline

1. **Adicionar um gate determinístico de coerência entre `recommended_path`/`verdict` e `customer.status`/`offer.status`** para grade A/B, análogo ao já existente para C/D: por exemplo, impedir `recommended_path in {replicate, offer_service}` quando `customer.status != observed` ou `offer.status != observed`, rebaixando automaticamente para `adapt`/`collect_evidence`. Isso teria corrigido a inconsistência interna nos posts 47, 236 e 493 sem depender da qualidade do modelo.
2. **Adicionar checagem lexical determinística para linguagem de estimativa** ("estimado", "aproximadamente", dados de ferramentas de terceiros) que impeça `status=observed` nesses casos — teria corrigido o post 656.
3. **Registrar o `raw` retornado pelo modelo antes da validação** (hoje não persistido) — isso permitiria auditar exatamente o que o modelo tentou dizer versus o que foi descartado, em vez de inferir pelos `validation_warnings`.
4. Para decisões de alto impacto (grade A com `recommended_path` avançado), considerar uma segunda passada com um modelo maior/mais capaz — mesmo pequena, como reforça este lote, aumentaria a chance de captar contradições textuais explícitas (como o desmentido do post 47) que o qwen3:14b, nesta amostra, não captou nenhuma vez.
5. Investigar separadamente a possível incoerência de captura no post 287 (thread aparentemente não relacionada ao post) — item operacional, não de modelo.

---

### Referências para auditoria (run_ids)

- `analysis_runs.id` 1653 → post_id 47 (`SIG-X-2084824127462838454`)
- `analysis_runs.id` 1654 → post_id 236 (`SIG-X-2090224231183233346`)
- `analysis_runs.id` 1655 → post_id 287 (`SIG-X-2090851936178172146`)
- `analysis_runs.id` 1656 → post_id 493 (`SIG-X-2091946082758508547`)
- `analysis_runs.id` 1657 → post_id 656 (`SIG-X-2092733325836210327`)
- Comentário-chave do post 47: `post_comments.comment_id = 2084998876952441288` (autor, `is_author_reply=1`, texto: "é mentira, inventei tudo isso ai").
- Comentário-chave do post 656: `2092744841423646770` ("Minha esposa usa esse ai e paga tbm...", `is_author_reply=False`).
