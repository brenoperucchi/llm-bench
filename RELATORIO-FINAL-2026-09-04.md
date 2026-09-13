# Relatório final — migração e parametrização RTX 5090

**Data:** 2026-09-04, com atualizações em 2026-09-05 (§2, §5 e pontos
marcados "Atualização")
**Escopo:** troca de placa (RTX 3080 Ti → RTX 5090), migração do servidor Ollama
(WSL2 → Windows nativo), e seis fases de medição (infra, qualidade, contexto/
residência, tool-calling do template, tool-calling+reamostragem do 6º
candidato, `NUM_PARALLEL`) no Ryzen9WSL.

---

## Respostas diretas

### Tivemos ganho de performance?

**Sim, em três frentes — mas com força de evidência diferente em cada uma,
e nenhuma delas de graça:**

| Frente | Antes (medido) | Depois (medido) | Força da evidência |
|---|---|---|---|
| Sistema operacional do servidor | 199,7 tok/s (WSL2) | 225,8 tok/s (Windows nativo) | **A/B controlado, 5 repetições** — +13,1% |
| Configuração do Ollama | 0,4–4,2 s de recarga por troca (config 1, nesta placa) | 0,00 s (config 4) | **medido nas duas pontas, nesta placa** |
| Placa (3080 Ti → 5090) | 100,5 tok/s (`qwen3:8b`, produção) | 197,8 tok/s | **~2×, e só para os 2 modelos com dado nos dois lados** — ver ressalva no §1.1 |

Nenhuma comparação de placa no repositório sustenta um número maior que ~2×
— um "~18×" chegou a circular numa versão anterior deste relatório e não
tinha lastro em nenhum artefato; removido.

Os dois primeiros vieram sem contrapartida de qualidade ou contexto. A
migração de SO, especificamente, **tem** um custo real: a observabilidade
regrediu (sem `journalctl`, sem rotação de log) e ela foi a origem do
vazamento de VRAM por processo órfão (§4) — um risco que só existe no
modelo de processo do Windows. Vale o ganho, mas não foi de graça.

### Qual LLM entrou no nosso escopo?

**Nenhum modelo novo foi promovido a default de produção.** O store cresceu de
14 para 18 modelos (os 4 pulls da Fase 2); 6 modelos passaram pelo goldset de
qualidade pela primeira vez — `qwen3.5:9b` (estreou na Fase 0) e os 5
candidatos da Fase 2. **Dos 5 candidatos da Fase 2, todos têm defeito real e
reproduzível** (n=5, não amostral) nas categorias que mais importam. Ver §2
para o motivo específico de cada um.

O 6º estreante, **`qwen3.5:9b`**, teve o melhor score do dia (98%) na
passada única — mas essa passada única (o mesmo método que, no
`laguna-xs-2.1`, escondeu um LEAK que só apareceu ao reamostrar) foi
seguida, no dia seguinte (Fase 4), das duas validações que faltavam: tool-calling
(8/8 nos dois braços, critério pleno atingido) e a reamostragem (n=5) dos 9
casos críticos que ele tinha passado de primeira. **A ressalva se confirmou**:
3 dos 9 casos mostraram defeito real (LEAK condicional num trap de
QuickBooks, e um MISS de escalação num pedido de feature) — `qwen3.5:9b`
deixou de ser "sem defeito" pra ser "defeito real, mais brando que os
candidatos da Fase 2". Mesmo assim, o usuário decidiu **manter `qwen3:14b`**
como default por ora — ver §5 e a ressalva sobre essa comparação logo abaixo
da atualização daquela seção.

### Qual LLM de programação se mostrou mais apto ao serviço?

**Pergunta que este lab não tem como responder com dado próprio ainda.** Os
dois candidatos de código (`laguna-xs-2.1`, `qwen3-coder:30b`) só foram
testados contra o goldset de **suporte ao cliente** (fora do domínio deles) —
não existe um goldset de programação neste projeto. Nesse teste fora de
domínio, os dois tiveram o **mesmo defeito, na mesma taxa**: escalam o trap
do QuickBooks incorretamente em 4 de 5 tentativas (20% de acerto) — não dá
para diferenciar os dois por esse resultado.

Por benchmark **publicado** (não medido aqui): `laguna-xs-2.1` tem 70,9% no
SWE-bench Verified, divulgado pela poolside. Não encontrei um número
equivalente para `qwen3-coder:30b` na pesquisa desta sessão. Isso é citação
de terceiro, não medição — **se decidir por uso de código de verdade, o passo
certo é montar um goldset de programação e repetir o mesmo processo usado
para o suporte**, não decidir por esse número solto.

---

## 1. Ganho de performance, em detalhe

### 1.1 — Placa (3080 Ti → 5090)

Não existe benchmark de tok/s dedicado da 3080 Ti (procurado e não
encontrado — ver `baseline-3080ti/README.md`). A comparação disponível é
contra telemetria real de produção da 3080 Ti (2.462 chamadas,
`content-insights-collector`, 24–31/08) e o primeiro benchmark de tok/s da
5090:

| Modelo | 3080 Ti (produção, `eval_count/total_duration`) | 5090 (`eval_count/eval_duration`) |
|---|---|---|
| qwen3:14b | 63,9–68,0 tok/s | 127,9 tok/s |
| qwen3:8b | 100,5 tok/s | 197,8 tok/s |

Ressalva que já ficou registrada, com a direção corrigida (achado de revisão,
rodada `llm-bench-7`): a coluna da 3080 Ti inclui o prefill no denominador,
então ela **subestima** a geração pura daquela placa — o denominador da razão
fica artificialmente pequeno. Isso torna a proporção acima um **teto**
otimista do ganho, não um piso: dividir por um número menor que o real
inflaciona a razão. Um exemplo numérico ilustra: se a 5090 gera a 200 tok/s,
a 3080 Ti gerasse de fato a 150 tok/s de decode puro mas medisse 100 tok/s
(prefill incluso), a razão publicada seria 200/100 = 2×, enquanto a razão
decode-a-decode real seria 200/150 ≈ 1,33×. Sem medir decode puro da 3080 Ti
(impossível agora, ela não existe mais), não dá pra saber se o ganho real
está mais perto de 2× ou bem menor. Fonte: `baseline-3080ti/baseline-3080ti.md`.

### 1.2 — Sistema operacional (WSL2 → Windows nativo)

A/B controlado, mesmo modelo (`qwen3:8b`), mesma placa, 5 repetições
alternadas:

| Prompt | WSL2 | Windows nativo | Δ |
|---|---|---|---|
| curto | 201,4 tok/s | 232,5 tok/s | +15,4% |
| médio | 199,7 tok/s | 225,8 tok/s | +13,1% |
| longo | 195,0 tok/s | 223,7 tok/s | +14,7% |

Confirmado em produção depois da migração: **225,9 tok/s** medidos no
servidor real. O runner CUDA (`cuda_v12` vs `cuda_v13`) foi descartado como
explicação — testado à parte, empate. Fonte:
`results/RESULTADO-wsl-vs-windows-2026-09-04.md`.

### 1.3 — Configuração (contexto × `MAX_LOADED_MODELS`)

7 configs testadas. A que ficou em produção (config 4: contexto 32k
inalterado, `MAX_LOADED_MODELS=2`, KV em f16):

| | Antes (config 1) | Depois (config 4) |
|---|---|---|
| Contexto | 32k | 32k (sem mudança) |
| Modelos residentes simultâneos | 1 | 2 (`qwen3:14b` + `qwen3.5:9b`) |
| Recarga entre os dois | 0,4–4,2s por troca (medido nesta placa) | **0,00s** |
| VRAM usada | — | 19,68 GiB de 30,3 |

O "antes" é o que a própria Fase 1 mediu na config 1, nesta placa — não uma
estimativa de outro hardware. E é a **Measure A** (alternância dentro da
janela de `keep_alive`, que é o que discrimina `MAX_LOADED_MODELS`): uma
chamada depois de >5 min de ociosidade recarrega em qualquer config desta
matriz, porque aí quem descarrega é o `keep_alive`, não o scheduler — essa
medida não foi feita (ver `results/RESULTADO-fase1-…md`, "O que ficou sem
medir").

Achado colateral que quase virou confusão: um vazamento de VRAM por processos
`llama-server.exe` órfãos (o restart matava só o supervisor `ollama.exe`)
chegou a derrubar a VRAM livre para 252 MiB e simular um "bug" de KV
quantizado que não existia. Corrigido no script de restart e no runbook de
migração. Fonte: `results/RESULTADO-fase1-contexto-maxloaded-2026-09-04.md`.

### 1.4 — Modelos MoE são consistentemente mais rápidos

Os 5 candidatos MoE testados na Fase 2 (`gpt-oss:20b` ~20B totais; os outros
quatro ~30B totais; todos 3–3,8B ativos) ficaram entre 204 e 293 tok/s — mais
rápidos que os densos de 14B/9B da Fase 0 (135–183 tok/s), confirmando de
novo, nesta placa, o achado central do benchmark de CPU: MoE fura o teto de
banda de memória. `qwen3:30b-a3b` foi o mais rápido do dia (293,4 tok/s).

---

## 2. Placar de qualidade — todos os modelos testados no goldset

18 casos (escalação, anti-alucinação, grounding, greeting, howto), mesma
config de servidor, `THINK=false`.

| Modelo | auto_score (n=1) | tok/s | Defeito real encontrado (n=5 onde houve reamostra) |
|---|---|---|---|
| **`qwen3.5:9b`** | **98%** | 183 | **defeito real 3/9** nos críticos reamostrados na Fase 4 (LEAK condicional + MISS de feature) — mais brando que os candidatos abaixo, mas não "sem defeito" |
| `qwen2.5:14b` | 97% | 138 | nenhum nesta rodada (mas ver §3, tool-calling histórico) |
| `laguna-xs-2.1` | 97% | 258 | **LEAK real 4/5** no trap do QuickBooks (o 97% de rodada única mascarava isso) |
| `qwen3:30b-a3b` | 93% | 293 | **vaza raciocínio em 18/18 casos**, mesmo com `THINK=false` — investigado a fundo, é o checkpoint, não corrigível por template |
| `qwen3-coder:30b` | 93% | 265 | mesmo LEAK do QuickBooks, mesma taxa (4/5) |
| `glm-4.7-flash` | 93% | 204 | mesmo LEAK do QuickBooks, menos frequente (2/5) |
| **`qwen3:14b`** (default atual) | 92% | 135 | **DOIS LEAKs reais de escalação**: em pergunta de preço (`pricing_pt`, 6/6 na forma original) e no trap do QuickBooks (`quickbooks_trap_en`, 0/5 na reamostragem de 08/09) — os dois reproduzem literalmente o bloco 87–89 do system prompt |
| `gpt-oss:20b` | 90% | 260 | **MISS real de escalação** (2/5, não 3/5 — `RESULTADO-fase2:36` registra "3/5 **corretos**") — deu troubleshooting fabricado num caso account-specific |

**Todo `auto_score` desta tabela é de uma única passada** (`run_chat.py`, 1
amostra por caso, `temperature=0,7`). As taxas de defeito da coluna da
direita (x/5) vêm de reamostragem — para a maioria dos modelos, só dos casos
que falharam na primeira passada (fine-check da Fase 2). `qwen3.5:9b` é a
exceção: passou de primeira em **todos** os 9 casos críticos do goldset, e a
Fase 4 (2026-09-05) reamostrou os 9 mesmo assim, n=5 cada — o teste mais
rigoroso que qualquer modelo deste programa recebeu. **A ressalva de n=1 se
confirmou**: 3/9 com defeito real (detalhe em
`results/RESULTADO-fase4-toolcalling-qwen35-2026-09-05.md`). Nenhum outro
modelo desta tabela foi reamostrado nesses mesmos 9 casos — inclusive
`qwen3:14b` — **até 2026-09-08, quando ele finalmente foi** (§5 e
`results/RESULTADO-reamostra-qwen3-14b-2026-09-08.md`): 40/45, com defeito em
1 dos 9 casos. Os dois números agora existem, e a diferença de agregado —
40 contra 38 em 45, **duas chamadas** — é pequena demais para ranquear: o que
se sustenta é que o desafiante erra em **mais lugares** (3 casos contra 1),
com profundidade máxima semelhante (~80% de falha no pior caso de cada um).

**Nenhuma linha desta tabela está livre de mas.** Isso não é acaso — é o
mesmo padrão que o benchmark de CPU já tinha encontrado em maio: a maioria
dos modelos erra a escalação numa direção ou na outra, e só um teste que
olha as duas direções (MISS e LEAK) separadamente enxerga isso. O
`auto_score` médio, sozinho, teria escondido cada um destes defeitos.

### O que aconteceu com o bug do `qwen3:14b` (default atual)

Investigado a fundo (causa raiz: cópia literal de um bloco de exemplo do
system prompt, depois um segundo problema de ambiguidade de instrução). Três
tentativas de correção (`v1`, `v2`, `v3`) — a `v2` resolveu 62,5% do bug
original mas **introduziu uma regressão pior** (token de escalação real
sumindo silenciosamente em outro modelo — 2 dos 4 casos de escalação real do
`qwen2.5:14b`, 50% das vezes, medido no artefato salvo daquela rodada).
**Revertido.** O
system prompt canônico está exatamente como estava antes da investigação.
Fonte: `ACHADO-qwen3-14b-pricing-leak-2026-09-04.md`.

---

## 3. Tool-calling — a pergunta pendente desde a 3080 Ti

A/B direto no Ollama (sem gateway), mesma pergunta e ferramenta do repro
original de 02/09:

| Modelo | Parâmetro `tools` nativo | Ferramenta em JSON no system prompt |
|---|---|---|
| `qwen2.5:14b` | 1/8 (12,5%) | **8/8 (100%)** |
| `qwen3:14b` (controle) | 8/8 | 8/8 |

**Os dois templates são idênticos, byte a byte**, no bloco de ferramentas —
a diferença não é o template estar quebrado só para um modelo. A leitura mais
precisa: `qwen3:14b` tolera uma renderização que pode ser imperfeita e
`qwen2.5:14b` não — "imperfeita" é inferência (da issue pública + do padrão
de falha), não algo que chegamos a observar byte a byte no prompt renderizado.
A troca
de default em setembro continua certa, agora por um motivo mais preciso:
fragilidade de geração de modelo a um formato específico, não "o modelo é
ruim em ferramentas". Workaround testado e funcional caso um modelo mais
antigo precise voltar a ser usado com ferramentas. Fonte:
`results/RESULTADO-fase3-toolcalling-template-2026-09-04.md`.

---

## 4. Achados operacionais (fora do escopo de comparar modelos)

1. **Vazamento de VRAM por processo órfão** — `Stop-ScheduledTask` sozinho
   não mata `llama-server.exe`. Corrigido no runbook e no script de restart.
   Sem essa correção, qualquer reinício futuro da tarefa `OllamaServer`
   corre o mesmo risco.
2. **App de bandeja disputava a porta 11434 com a tarefa de produção** —
   atalho de Startup removido durante a migração.
3. **CUDA funciona em session 0** — a tarefa sobe sem login, validado com
   reboot real da máquina.
4. **`OLLAMA_HOST=0.0.0.0:11434` no escopo Machine** deixou de ser risco
   (colidia com o WSL) e virou parte da configuração correta.

---

## 5. O que ainda não foi feito

Atualização 2026-09-05: os itens 1, 3 e 4 abaixo foram resolvidos nas Fases
4-6 (ver `PLANO-fase456-2026-09-05.md` e os `RESULTADO-fase4/6-*.md`
correspondentes). Ficam registrados aqui como estavam na versão original do
relatório, com a resolução anotada em cada um.

1. ~~**Tool-calling do `qwen3.5:9b`** — nunca testado.~~ **Resolvido na Fase
   4**: 8/8 nos dois braços, critério pleno de promoção atingido — mas ver o
   item 3 para o desfecho real (a promoção não aconteceu).
2. **Goldset de programação** — não existe. Necessário para responder a
   pergunta de qual modelo de código é mais apto, com dado próprio em vez de
   benchmark de terceiro. Bloqueado num pré-requisito de segurança: precisa
   de um sandbox de execução de código antes de rodar (Fase 5, não iniciada).
3. **`qwen3:14b` (default atual) segue com o LEAK de pricing sem correção
   aplicada** — revertido para o estado original, não consertado. **Decisão
   tomada em 2026-09-05: manter `qwen3:14b` como default por enquanto.** Mesmo
   com `qwen3.5:9b` passando em tool-calling (Fase 4), a reamostragem dos
   casos críticos revelou que ele também tem defeito real (3 de 9 casos,
   `RESULTADO-fase4-toolcalling-qwen35-2026-09-05.md`) — trocar não eliminaria
   risco, só mudaria qual risco se aceita, sem vantagem líquida clara o
   suficiente para justificar a migração agora.
   **Ressalva importante sobre esta justificativa** (achado de revisão,
   rodada `llm-bench-6`/`7`): a comparação acima não é simétrica.
   `qwen3.5:9b` foi reamostrado nos 9 casos críticos, n=5 cada (~45
   chamadas); `qwen3:14b` nunca foi reamostrado nesses mesmos 9 casos — só
   tem a passada única (n=1) da Fase 0. "Taxa mais baixa" compara um número
   medido (3/9) com um desconhecido. A decisão de manter `qwen3:14b` é do
   usuário e não está em questão; o que fica em aberto é que ninguém mediu
   se o incumbente é de fato melhor ou pior nesses 9 casos especificamente.

   **Lacuna FECHADA em 2026-09-08** —
   `results/RESULTADO-reamostra-qwen3-14b-2026-09-08.md`. O `qwen3:14b` foi
   reamostrado nos mesmos 9 casos, n=5: **40/45 (88,9%), 1 caso com defeito**,
   contra 38/45 (84,4%) e 3 casos do `qwen3.5:9b`. A frase "trocar só mudaria
   qual risco" passa a ter lastro, com a nuance que faltava: **o incumbente
   erra menos vezes e em menos lugares, porém mais fundo** — no único caso em
   que falha (`quickbooks_trap_en`) a taxa é ~78% dos seeds testados, contra
   20% do desafiante no mesmo caso. E é um **segundo LEAK da mesma família do
   de pricing**: reprodução literal do bloco de exemplo de escalação do system
   prompt (linha 87). O default carrega dois LEAKs conhecidos, não um.
4. ~~**`OLLAMA_NUM_PARALLEL`** — identificado como causa alternativa de fila,
   nunca medido.~~ **Resolvido na Fase 6**: medido, `NUM_PARALLEL=2` reduz 28%
   o tempo de lote e 38% por requisição sob concorrência real, com folga de
   VRAM — aplicado em produção. **Remediado em 2026-09-05** com prompt de
   produção real (2108 tokens de prefill, calibrado contra o
   `baseline-3080ti.md`) e checagem de VRAM (`size==size_vram`, sem spill) —
   ganho confirmado (−28%/−41%, re-medido após a rodada de revisão
   `llm-bench-5` achar e corrigir uma inconsistência de versão do harness
   entre os dois braços da 1ª tentativa), não mais circunstancial. Ressalva que
   continua: só testado com `qwen3:14b` sob carga isolada, não com os dois
   modelos recebendo carga concorrente juntos.
5. Os 5 candidatos da Fase 2 continuam no store, mas nenhum está pronto para
   promoção — todos com defeito real documentado. `qwen3.5:9b` (testado
   depois, fora da Fase 2) é o melhor do lote geral, mas também não está livre
   de defeito (ver item 3).

---

## Índice de fontes

- `MIGRACAO-windows-nativo-2026-09-04.md` — runbook completo da migração
- `PLANO-parametrizacao-2026-09-04.md` — plano revisado (2 rodadas de review)
- `results/RESULTADO-fase1-contexto-maxloaded-2026-09-04.md`
- `results/RESULTADO-fase2-modelos-novos-2026-09-04.md`
- `results/RESULTADO-fase3-toolcalling-template-2026-09-04.md`
- `results/RESULTADO-wsl-vs-windows-2026-09-04.md`
- `results/chat_table.gpu5090-baseline.md` / `.gpu5090-novos.md` / `.gpu5090-postfix.md`
- `ACHADO-qwen3-14b-pricing-leak-2026-09-04.md`
- `PLANO-fase456-2026-09-05.md` — plano de continuação (Fase 4-6)
- `baseline-3080ti/` — arquivo da placa anterior

## Histórico de revisão

**Rodada `llm-bench-3`** (2026-09-05, `llm-bench-rev` + `llm-bench-rev-2`,
cega e paralela): achou que o "~18×" de ganho de placa não existe em nenhum
artefato do repositório (removido), que o "antes" da recarga usava uma
anedota de outro hardware em vez do medido nesta placa, uma contradição
entre "6 candidatos com defeito" e o parágrafo seguinte, e que o candidato
`qwen3.5:9b` — o mais forte para virar default — tinha seu "sem defeito"
apoiado em n=1, a mesma falácia que este documento usa para explicar por que
`laguna-xs-2.1` enganou na primeira rodada. Também corrigiu a taxa de
regressão do `v2` (50%, não 25%) e uma ressalva epistêmica perdida no §3. Um
incidente de protocolo (contaminação parcial de cegueira, autodenunciado pelo
`rev-2`) foi levado ao usuário, que decidiu aceitar a rodada — os achados
mais fortes foram cruzados contra a fonte primária antes de aplicar. Detalhe
completo em `.herdr/review/llm-bench-3/*/verdict.md`.
