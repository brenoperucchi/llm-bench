# Avaliação de capacidade — qwen3:14b no relatório estruturado de oportunidade

**Escopo:** leitura read-only de `data/local-staging.db` e de `src/insights_collector/investigation.py`. Nenhum código ou configuração foi alterado. Amostra: posts 287, 656, 575, 571, 569; `analysis_runs` com `analysis_kind='opportunity_probe'`, `model='qwen3:14b'`.

**Nota sobre a amostra:** a query `SELECT ... WHERE analysis_kind='opportunity_probe' AND model='qwen3:14b'` retorna exatamente 5 linhas no banco inteiro — os 5 runs pedidos são **100% do universo já executado** deste probe, não uma seleção de um conjunto maior. Isso é relevante para toda avaliação de "consistência entre sinais" abaixo: não há repetição, não há segunda passada sobre o mesmo post, e não há nenhum caso de `evidence_grade` A ou B ainda observado.

---

## 1. Contrato implementado (leitura de `investigation.py`)

- **Schema de resposta** (`INVESTIGATION_RESPONSE_SCHEMA`, linha 420): 14 campos obrigatórios, `additionalProperties: False`. Passado como `format` no `POST /api/chat` do Ollama (linha 742), isto é, JSON-schema-constrained decoding — não é só instrução em prompt.
- **Gate C/D é aplicado no backend, não confiado ao modelo** (`validate_investigation_report`, linhas 682–713): se `ledger.grade` ∈ {C, D}, o backend **sobrescreve incondicionalmente** `verdict`, `recommended_path`, `headline`, `customer`, `offer`, `next_test`, `risks` (com defaults se vazios) e completa `not_answered` com os itens do `missing_evidence` do ledger. O modelo pode propor o que quiser nesses campos; é descartado se o grade não permite.
- **`observed_facts` exige literalidade e autoria corretas** (`_validate_fact`, linhas 458–504):
  - `source` precisa estar em `source_refs` do ledger (`post_text`, `comment:<id>`, `public_metrics`) — linha 470.
  - `source_text` precisa existir de fato como texto citável (metadados de captura, ex. mídia, não contam) — linha 473.
  - `third_party` precisa bater exatamente com `source in third_party_refs` (autor nunca é terceiro) — linha 480.
  - `quote` precisa ser um trecho normalizado (espaços colapsados, casefold) que seja **substring literal** do `source_text` — linha 487. É esta checagem que gerou o erro do post 569.
  - Para `source == "public_metrics"`, a citação precisa conter um par `chave=valor` normalizado (ex. `like_count=585`) — linha 491.
  - Mesmo aprovado, o `claim` final é reescrito deterministicamente pelo backend como `"A fonte registrou: " + quote` (linha 500) — a paráfrase do modelo nunca chega ao relatório persistido.
- **Hipóteses** (`_validate_hypothesis`) não são checadas contra o texto-fonte — são especulação assumida, com `confidence` numérica 0–1 e `depends_on`/`falsifiable_by` textuais.
- **`customer`/`offer`** exigem `status ∈ {observed, hypothesis, unknown}`; campos textuais só são obrigatórios se `status != unknown`.
- **`missing_evidence`** do modelo precisa usar `code` presente no ledger e `how_to_get` em um enum fechado; o backend completa com qualquer código do ledger que o modelo não tenha citado.
- **Retry**: até `OPPORTUNITY_MAX_RETRIES = 3` (constante em `analysis.py:14`), com backoff `60 * 2^retry_count` segundos (`investigator.py:108`). Falha de validação (`InvestigationValidationError`) é `retryable=True` — conta para o orçamento de retries.
- **Ausência de log do output bruto**: quando a validação falha, o backend nunca persiste o JSON que o modelo devolveu — `response_json` fica `{}` no run `failed`. Isso é uma limitação do experimento, não do modelo: não há como auditar forense o texto exato que violou a regra de literalidade no post 569.

---

## 2. Tabela por sinal

| Post | Grade (backend) | Attempts (chamadas ao modelo) | Status final | Erro / causa |
|---|---|---|---|---|
| 287 | D | 3 (2 retries) | succeeded | 2 tentativas anteriores falharam na validação; causa exata não recuperável (response_json não persistido em tentativas falhas) |
| 656 | C | 1 | succeeded | — |
| 575 | C | 1 | succeeded | — |
| 571 | D | 1 | succeeded | — |
| 569 | D | 4 (3 retries) | **failed** | `observed_facts[1].quote is not an excerpt from its source` nas 4 tentativas; esgotou `OPPORTUNITY_MAX_RETRIES=3` |

### 2.1 Completude do schema

| Post | 14 campos presentes | `additionalProperties` violado | Enums inválidos |
|---|---|---|---|
| 287 | sim | não | não |
| 656 | sim | não | não |
| 575 | sim | não | não |
| 571 | sim | não | não |
| 569 | n/a (nunca persistiu um JSON válido) | n/a | n/a |

Nos 4 runs com sucesso, o schema foi cumprido sem exceção detectável — todos os campos obrigatórios vieram no formato esperado (objeto/lista conforme o schema), sem campos extras. Isso é esperado dado que o Ollama recebeu `format: INVESTIGATION_RESPONSE_SCHEMA` como grammar de decodificação, não apenas instrução textual — o modelo estava estruturalmente impedido de sair do shape.

### 2.2 Obediência estrutural (regras que o schema JSON *não* força, mas o prompt/validador sim)

| Post | `depends_on` bem formado (lista de itens distintos) | `missing_evidence.code` ∈ ledger | `how_to_get` no enum | Observação |
|---|---|---|---|---|
| 287 | **não** — 1 hipótese com `depends_on: ["customer.problem_paid_for, offer.shape, offer.monetization"]`, três referências coladas numa única string em vez de 3 itens de lista | sim | sim | violação de forma silenciosa: passa na validação (`_list_of_text` só exige lista de strings) mas descumpre a intenção do campo |
| 656 | sim (1 item, correto) | sim | sim | — |
| 575 | sim | sim | sim | — |
| 571 | sim | sim | sim | — |
| 569 | n/a | n/a | n/a | nunca chegou a esse ponto da validação (falhou antes, em `observed_facts`) |

Em todos os 4 runs bem-sucedidos, o `missing_evidence` retornado pelo modelo é **idêntico item-a-item** ao `missing_evidence` já presente no `evidence_ledger` enviado no prompt — o modelo não adicionou, removeu nem reformulou nenhum item; apenas ecoou o que o backend já havia calculado deterministicamente. Isso mostra obediência ao ledger, mas indica que o modelo não está de fato sintetizando lacunas — está copiando.

### 2.3 Literalidade e autoria das evidências (`observed_facts`)

| Post | Nº fatos | Todas as quotes são substring literal da fonte | `third_party` correto | Fonte usada |
|---|---|---|---|---|
| 287 | 1 | sim (quote = íntegra do post) | sim (`false`, post_text) | post_text |
| 656 | 4 | sim (cada quote é um trecho contíguo do post, incl. `"R$13k MRR estimado"`) | sim | post_text |
| 575 | 2 | sim | sim | post_text |
| 571 | 3 | sim (inclui quebras de linha normalizadas corretamente) | sim | post_text, `@LangChain` citado como parte do texto do próprio autor, não third-party |
| 569 | ≥2 (índice 1 falhou) | **não** — `observed_facts[1]` rejeitado 4 vezes seguidas | não avaliável (rejeitado antes) | fonte disponível era só `post_text` e `public_metrics` (nenhum comentário) |

Nos 4 sucessos, todas as citações que persistiram no banco são trechos literais e corretamente atribuídos (nenhuma alegação do autor foi marcada como terceiro). Isso é o resultado do gate, não uma alegação sobre o texto que o modelo originalmente gerou antes da reescrita determinística de `claim` — o `claim` final ("A fonte registrou: ...") é sempre reescrito pelo backend, então **não há evidência no banco sobre a qualidade da paráfrase original do modelo**, só sobre a citação literal, que é o único ponto controlado.

Para o post 569 não há nenhum dado factual recuperável — o JSON que falhou não foi persistido. O único fato observável é o **padrão do erro**: a mesma causa (`observed_facts[1].quote`) se repetiu de forma idêntica em texto de erro nas 4 tentativas, o que sugere um viés sistemático do modelo para aquele input específico (post sem comentários e sem alegação comercial explícita, com `public_metrics` como única fonte de terceiros), não uma falha aleatória que o retry corrigiria por variância de amostragem.

### 2.4 Respeito ao gate C/D

| Post | Grade | `verdict` final | `recommended_path` final | `customer.status` | `offer.status` |
|---|---|---|---|---|---|
| 287 | D | evidence_insufficient | collect_evidence | unknown | unknown |
| 656 | C | evidence_insufficient | collect_evidence | unknown | unknown |
| 575 | C | evidence_insufficient | collect_evidence | unknown | unknown |
| 571 | D | evidence_insufficient | collect_evidence | unknown | unknown |
| 569 | D | — | — | — | — |

Nos 4 sucessos, o campo persistido está sempre em conformidade com o gate — mas **isso é garantido pelo `validate_investigation_report`, que sobrescreve esses campos incondicionalmente quando `grade ∈ {C, D}`, independentemente do que o modelo tenha proposto originalmente**. Não é possível, a partir do banco, saber se o modelo *já* respeitava o gate por conta própria ou se seria necessário o override em algum desses 4 casos — o dado persistido é sempre pós-gate. O único sinal indireto de alinhamento espontâneo é o `verdict_confidence`, que **não é forçado pelo validador** e ainda assim veio baixo em todos os 4 casos (0.1, 0.3, 0.3, 0.2) — condizente com a incerteza que o gate impõe, mesmo sem ser exigido.

**Risco remanescente identificado aqui:** nada no schema ou no validador impede `verdict_confidence` alto (ex. 0.9) simultâneo a `verdict=evidence_insufficient` forçado. Não há inconsistência nesta amostra, mas também não há garantia estrutural contra ela em runs futuros.

### 2.5 Utilidade para decidir replicar/adaptar/oferecer

| Post | Verdict | Path | Utilidade prática |
|---|---|---|---|
| 287 | evidence_insufficient | collect_evidence | Baixa como decisão de negócio, mas correta: post é 1 frase sobre faturamento sem produto, cliente, preço ou mídia lida — nenhuma decisão de replicar/adaptar seria responsável com esse material |
| 656 | evidence_insufficient | collect_evidence | Post tem MRR, %, downloads — mas grade C (sem discussão independente, sem identidade de produto) trava o path em `collect_evidence`; corretamente conservador, mesmo com sinais comerciais fortes no texto |
| 575 | evidence_insufficient | collect_evidence | Produto de nicho (gerador de screenshots) sem preço nem cliente citado — path correto |
| 571 | evidence_insufficient | collect_evidence | Projeto WIP, sem produto lançado — path correto |
| 569 | (nenhum relatório) | (nenhum) | Zero utilidade: o sistema não produziu nada utilizável; o operador só vê que a análise falhou |

**Nenhum dos 5 posts chegou a um verdict acionável (`replicable`/`adaptable`/`serviceable`).** Isso não é um problema do modelo — é esperado, já que todos os 5 têm `evidence_grade` C ou D no ledger, que é calculado deterministicamente pelo backend antes de o modelo ser chamado. A amostra, por construção, não testa se o qwen3:14b sabe produzir um relatório útil e correto quando o grade é A ou B (customer/offer com `status=observed` reais, hipóteses concretas, `next_test` não genérico). **Essa é a maior lacuna de cobertura do experimento.**

### 2.6 Consistência entre sinais

- Os 4 runs bem-sucedidos são estruturalmente idênticos em padrão: mesmo `headline`, mesmo `next_test` (default do backend), `missing_evidence` = eco do ledger, `verdict_confidence` sempre baixo. Isso é **consistência esperada e desejável** dado o gate, não uma evidência independente da qualidade do modelo nesses campos — o backend absorve a maior parte da variância.
- Os campos onde o modelo teve liberdade real e foi de fato avaliado — `observed_facts` (literalidade) e `hypotheses`/`risks` (conteúdo livre, não validado contra fonte) — mostram: literalidade 100% correta em 4/4 sucessos, mas falha sistemática e repetida em 1/1 caso de input "pobre" (569, sem comentários, sem alegação comercial, métricas apenas de engajamento).
- Cruzando com a classificação de triagem (`classifications`, mesmo `input_hash`/post): post 569 foi categorizado pela triagem como `omarchy.improvement` (não é sequer `saas.*`) — ou seja, é um post sobre ferramenta de sistema, não uma alegação de oportunidade de negócio. Isso é consistente com a hipótese de que o modelo teve mais dificuldade em ancorar uma citação de "fato observado" em um texto que não contém nenhuma alegação comercial/quantitativa clara no corpo (as únicas métricas eram engajamento social, exigindo o formato estrito `chave=valor`).

### 2.7 Falhas de validação e custo de retries

| Post | Chamadas ao Ollama | Retries consumidos | Backoff acumulado (teórico) | Resultado |
|---|---|---|---|---|
| 287 | 3 | 2 de 3 | 60s + 120s = 180s | sucesso na 3ª |
| 656 | 1 | 0 | 0s | sucesso na 1ª |
| 575 | 1 | 0 | 0s | sucesso na 1ª |
| 571 | 1 | 0 | 0s | sucesso na 1ª |
| 569 | 4 | 3 de 3 (esgotado) | 60s + 120s + 240s = 420s | falha definitiva |

Total da amostra: **10 chamadas ao modelo para 5 posts** (2× a taxa ingênua de 1 chamada/post), com 1 post sem relatório algum ao final. O custo de retry não é uniforme: 3 posts (60%) tiveram sucesso de primeira, 1 post precisou de esforço extra e ainda assim convergiu, 1 post não convergiu dentro do orçamento configurado.

---

## 3. Fatos do banco vs. limitações do experimento vs. recomendação

**Fatos do banco:**
- 4 de 5 runs produziram um JSON estruturalmente válido, com literalidade de citação 100% correta nos campos verificáveis.
- 1 de 5 runs falhou de forma persistente e idêntica (mesmo erro nas 4 tentativas) por violação de literalidade em `observed_facts[1]`.
- O gate C/D, tal como persistido, nunca foi violado nos 4 sucessos — mas essa garantia vem do override incondicional do backend, não de uma prova de que o modelo já respeitava o gate sozinho.
- Nenhum post da amostra (nem do universo total de `opportunity_probe` já executado) atingiu grade A/B — o caminho de decisão acionável (`replicable`/`adaptable`/`serviceable`) nunca foi exercitado por este probe.

**Limitações do experimento (não conclusões sobre o modelo):**
- O `response_json` de runs `failed` não é persistido — não há forma de auditar o texto exato que o modelo produziu no post 569, só o nome do campo que falhou e o número de tentativas.
- Amostra de 5 posts, todos grade C/D, é pequena demais e enviesada para avaliar a "utilidade para decidir" nos casos de maior interesse (grade A/B).
- Não há repetição do mesmo post com seeds/temperaturas diferentes para medir variância intrínseca do modelo — a taxa de erro observada (1/5 falha total, 1/5 com retry) é uma amostra única, não uma taxa estimada com confiança estatística.
- O `depends_on` mal-formado no post 287 foi observado uma única vez; não sabemos se é recorrente ou um evento isolado.

**Recomendação (opinião, não fato do banco):**

O qwen3:14b é **aceitável para uso em produção com os guardrails atuais**, sob a condição de que o sistema trate falha após 3 retries como caminho normal esperado (post permanece sem relatório, sinalizado para revisão manual ou reprocessamento — não como erro do pipeline). A razão central é que o design do contrato já assume que o modelo é não confiável: o gate C/D é aplicado no backend, não delegado ao modelo, e a checagem de literalidade é mecânica (substring, não semântica) — isso significa que mesmo quando o qwen3:14b falha, ele falha de forma **segura** (bloqueando a persistência) em vez de **silenciosa** (persistindo uma citação inventada). O caso do post 569 é exatamente esse guardrail funcionando como projetado: 4 tentativas, 4 rejeições, zero dado fabricado no banco.

## 4. Riscos remanescentes

1. **Cobertura zero em grade A/B.** O experimento não testa a parte do contrato onde o modelo tem mais liberdade e mais chance de causar dano de negócio (afirmar `customer.status=observed`, propor `next_test` não genérico, escolher `recommended_path` diferente de `collect_evidence`). É a lacuna mais importante antes de confiar o probe em decisões reais de replicar/adaptar/oferecer.
2. **`verdict_confidence` não é validado contra o gate.** Nada impede um `evidence_grade=D` forçado a `evidence_insufficient` vir acompanhado de `verdict_confidence=0.9`. Não ocorreu na amostra, mas não há barreira estrutural.
3. **Falha silenciosa de auditoria.** Runs `failed` não guardam o JSON bruto rejeitado — impede diagnosticar padrões de alucinação a posteriori (o que exatamente o modelo tentou citar no post 569) e dificulta melhorar o prompt com base em exemplos reais de erro.
4. **Obediência estrutural mascarando cópia, não síntese.** Em 4/4 sucessos, `missing_evidence` do modelo é um eco literal do ledger. Isso é seguro (não pode citar um código inválido), mas significa que o valor agregado do modelo nesse campo específico é ~nulo nos casos de grade baixo — a "inteligência" do relatório nesses casos vem inteiramente do backend determinístico.
5. **Taxa de retry desconhecida em escala.** 2 de 5 posts (40%) precisaram de pelo menos 1 retry, e 1 desses 2 esgotou o orçamento. Se essa taxa se mantiver em produção, o custo de latência/chamadas de opportunity_probe pode dobrar ou mais em relação ao caso ingênuo.

## 5. Próximo experimento sugerido

Rodar o mesmo probe (`opportunity_probe`, qwen3:14b) sobre uma amostra deliberadamente construída para atingir `evidence_grade` A e B — ou seja, posts com `content_level=thread`/`full_post`, ≥3 comentários independentes e métricas públicas presentes — para observar pela primeira vez o comportamento do modelo nos campos que o gate atual nunca exercitou (`customer.status=observed`, `offer.status=hypothesis`/`observed`, `recommended_path` fora de `collect_evidence`, `next_test` não-genérico). Em paralelo, considerar persistir o `response_json` bruto (ou ao menos os campos que falharam a validação) mesmo em runs `failed`, para permitir auditoria forense de futuras rejeições de literalidade sem precisar reexecutar o experimento.
