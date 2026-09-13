# Plano de parametrização — RTX 5090, pós-migração

**Data:** 2026-09-04 (revisado após rodada `llm-bench-1` de review, mesmo dia)
**Servidor:** Ollama 0.33.3, Windows nativo, tarefa `OllamaServer` (SYSTEM, boot).
Ver [`MIGRACAO-windows-nativo-2026-09-04.md`](MIGRACAO-windows-nativo-2026-09-04.md).
**Estado no momento de escrever:** nenhum modelo residente (`OLLAMA_KEEP_ALIVE=5m`
expirado), 14 modelos no store, 30,3 GiB de VRAM disponíveis.

## Onde estamos

Quatro itens do plano original já fechados, todos por medição, não por opinião:

| Item | Método | Resultado |
|---|---|---|
| Runner `cuda_v12` vs `cuda_v13` | A/B, duas instâncias Windows, mesmo modelo | **Empate** — decode −1,6% a +0,3% nos três tamanhos de prompt (a faixa completa, não só a melhor linha). A var forçada saiu na migração |
| Power limit | Números publicados (llama.cpp scoreboard, mesma placa) | **Descartado** — −1,2% em single-stream, mas −13,9% de prefill a 400 W importa para carga multi-batch. Placa em stock |
| WSL2 vs Windows nativo | A/B, harness `bench_engine_ab.py`, 5 reps alternadas | **+14% de decode** no Windows. Migração executada; 225,9 tok/s confirmados em produção |
| Flash attention | Números publicados (llama.cpp scoreboard) | Já ligada por default (`--flash-attn auto`); ganho medido pequeno (+3,7% decode). Sem ação |

O que falta não é mais sobre a placa — é sobre como o Ollama está configurado, e
sobre uma lacuna específica: **o harness de qualidade (`run_chat.py`, o goldset
de 18 casos com auto-checks de escalação/anti-alucinação/grounding) nunca rodou
em GPU nenhuma.** Todo o `RELATORIO_CONSOLIDADO.md` é CPU, maio/2026. Os A/B de
hoje mediram só tok/s. Isso não quer dizer que nada de qualidade foi medido em
GPU — a validação `phase7-qwen3-2026-08-24.md` avaliou 480 leituras do pipeline
do content-insights em GPU real — mas nenhuma delas usou o goldset que decide
entre modelos candidatos, e é essa régua específica que falta.

## Por que contexto e `MAX_LOADED_MODELS` são medidos juntos

Competem pela mesma VRAM. Sintoma observado nesta sessão: `qwen3:30b-a3b`
sozinho, a `ctx=32768` (o default por VRAM, `>24 GiB → 32k`), ocupou
**20,34 GiB de 30,3 disponíveis** (`ollama ps`). Sobram **9,96 GiB**.

O breakdown de memória do log do Ollama, no dia da troca de placa, dá o custo
real do KV — mas duas das três linhas originais estavam com os modelos
trocados. Corrigido com `/api/show` (metadata do GGUF, sem inferência):

| Modelo | camadas | kv-heads | pesos | KV @ 32k, f16 |
|---|---|---|---|---|
| `qwen3:14b` | 40 | 8 | 8,1 GiB | **5,0 GiB** |
| `qwen2.5:14b` | 48 | 8 | 8,2 GiB | **6,0 GiB** |
| `llama3.2:3b` | 28 | 8 | 1,9 GiB | 3,5 GiB |
| `qwen3:30b-a3b` | 48 | **4** | 17,3 GiB | **3,0 GiB** |

> A linha original tinha `qwen3:14b`→6,0 e `qwen2.5:14b`→5,0 GiB, invertida. O
> log de origem citava `(qwen2.5:14b, -c 32768) → contexto 5120 MiB`, que é
> 40 camadas (geometria do `qwen3:14b`, não do `qwen2.5:14b`, que tem 48) — ou
> o rótulo do log estava trocado, ou a leitura dele estava. Impacto pequeno nos
> totais (~1 GiB), mas essa tabela é a base de todos os cenários abaixo.

KV não escala com o tamanho do modelo — o `qwen3:30b-a3b` (48 camadas, mas só
4 kv-heads) gasta **menos** KV que o `llama3.2:3b`, sendo 10× maior em pesos. É
o melhor exemplo do próprio argumento, e reforça a leitura: contexto é
independente de "quão grande" o modelo é.

Cenários de VRAM, com os números corrigidos:

| Cenário | @32k | @16k | @8k |
|---|---|---|---|
| `qwen3:14b` + `qwen3.5:9b` | **~22 GiB, cabe com ~8 GiB de folga** | **~18 GiB** | **~16 GiB** |
| `qwen3:14b` + `qwen3.5:9b` + `qwen3:8b` | não cabe (31,6 GiB, falta 1,3) | **~25 GiB, cabe com ~5 GiB de folga** | **~22 GiB, cabe** (rodízio real de 3 modelos) |
| um 27B (16,8 GiB) + `qwen3.5:9b` | não cabe | **~27 GiB, apertado** | **~25 GiB** |
| dois 27B (≥ 33,6 GiB de pesos) | nunca cabe, em nenhum contexto ||

> `qwen3:8b` medido via `/api/show`: 36 camadas, 8 kv-heads, `key_length` 128 →
> 4,87 GiB de pesos, KV 4,5/2,25/1,125 GiB a 32k/16k/8k.
>
> `qwen3.5:9b` **não pôde ser medido por `/api/show`** — ver ressalva logo
> abaixo. As duas linhas que o incluem usam a mesma estimativa por proporção de
> antes (6,14 GiB de pesos, ~3/1,5/0,75 GiB de KV a 32k/16k/8k) e continuam
> tratadas como hipótese.
>
> A linha do 27B genérico usa 18 GB de *registry* = 16,8 GiB reais e um KV
> estimado por analogia com os modelos de 14B — não é um modelo específico, só
> ordem de grandeza para decidir se vale medir de verdade na Fase 2.

**Achado que muda a matriz da Fase 1:** a 16k, os **três** modelos do rodízio
real já cabem, com ~5 GiB de folga — não "não cabe", como uma versão anterior
desta tabela dizia (erro de não recalcular essa célula com o KV corrigido do
`qwen3:14b`). Isso torna 16k um candidato genuíno de meio-termo, não só 8k vs
32k — ver config 5 revisada abaixo.

> **`qwen3.5:9b` provavelmente tem atenção híbrida — não confiar na
> extrapolação linear para ele até medir de verdade.** `/api/show` não retorna
> `head_count_kv` para este modelo (nulo/ausente), e `key_length`/`value_length`
> vêm em **256** — o dobro dos outros quatro modelos desta tabela, que têm 128.
> Isso é assinatura de layout de atenção não-uniforme (kv-heads variando por
> camada, ou uma mistura de atenção completa com atenção linear/deslizante)
> — nesse caso o KV **não escala linearmente com o contexto**, e toda linha
> de cenário que inclui `qwen3.5:9b` (todas, menos "dois 27B") pode estar
> errada em qualquer direção. **Ação recomendada antes da Fase 1:** carregar
> `qwen3.5:9b` sozinho a 32k e a 8k e ler o delta real no `ollama ps` ou no
> `common_memory_breakdown_print` do log — é uma medição de ~2 minutos que
> destrava a confiabilidade de toda a tabela acima.

**Isto reverte a leitura anterior.** O par `qwen3:14b` + `qwen3.5:9b` — o que a
Fase 1 quer manter residente — **já cabe a 32k**, sem tocar em contexto nenhum.
`rtx5090-modelos-parametrizacao.md` §2e já dizia isso: *"Dois modelos residentes
cabem com folga mesmo com KV generoso."* A frase "fixar o contexto é o que
compra o segundo modelo residente" está forte demais para esse par — o que o
contexto compra é **um terceiro** (o rodízio real documentado é de três
modelos, não dois) ou folga para candidatos maiores. A matriz da Fase 1, abaixo,
foi redesenhada para testar isso de verdade em vez de presumir.

E **dois modelos de 27B nunca convivem**, não importa o contexto — se um 27B
vencer a Fase 2, o "segundo residente" vira necessariamente "um grande + um
pequeno com contexto curto", nunca "dois grandes".

## Por que isso é o item de maior evidência do plano — com uma ressalva

Duas fontes independentes, de projetos diferentes, apontam o mesmo sintoma na
3080 Ti:

- **A baseline de produção** (2.462 chamadas reais, `content-insights-collector`,
  24–31/08): p5 de ~24 tok/s contra mediana de 64–100 — cauda pesada, não
  degradação uniforme.
- **`acervo/backlog/tasks/task-97`** (01/09, projeto diferente, sessão
  diferente): `nvidia-smi` + `journalctl` confirmaram a GPU a **1–4% de
  utilização durante chamadas lentas** — assinatura de espera na fila, não de
  placa saturada.

GPU ociosa com latência alta é fila — mas "fila" tem pelo menos duas causas
possíveis, e o plano não as separava:

1. **Recarga entre modelos diferentes** (`MAX_LOADED_MODELS=1` despeja o
   anterior) — é o que a Fase 1 ataca.
2. **Serialização de requisições ao mesmo modelo** (`OLLAMA_NUM_PARALLEL=1` —
   configuração atual, herdada da migração sem mudança). A mesma segunda
   testemunha citada acima (`acervo/task-97`) atribui a causa provável a isso:
   *"causa provável é fila de concorrência (`OLLAMA_NUM_PARALLEL=1` num
   serviço compartilhado)"* — citação preservada em
   `baseline-3080ti/baseline-3080ti.md`, mas a origem é a mesma task-97, não
   uma terceira fonte.

`MAX_LOADED_MODELS=2` resolve (1) e não toca (2). Se o gargalo real for
concorrência de múltiplos clientes chamando o *mesmo* modelo ao mesmo tempo, a
Fase 1 vai medir latência de troca melhor sem mexer na causa que mais dói. Isto
não está no escopo de medição desta rodada — `NUM_PARALLEL` multiplica VRAM por
slot e merece sua própria fase — mas fica registrado para não vender
`MAX_LOADED_MODELS` como a causa resolvida quando pode ser só metade dela.

## O plano

### Fase 0 — régua de qualidade (não toca a infra)

O goldset (18 casos, `escalation`=4, `anti_hallucination`=5, `grounding`
presente) nunca rodou em GPU. Sem isso, a Fase 2 não tem como comparar modelos.

```bash
MODELS_OVERRIDE="qwen3:14b,qwen3.5:9b,qwen2.5:14b" THINK=false \
  OUT_SUFFIX=".gpu5090-baseline" \
  OLLAMA_URL=http://100.88.95.78:11434 python3 run_chat.py
```

Congela o "antes" e produz a régua de qualidade que falta.

> **Ressalva de amostra:** `run_chat.py` roda cada caso **uma vez**, a
> `temperature=0.7` (fixado em `OPTIONS`, linha 51 do harness). O `seed=42`
> torna o resultado reproduzível, não representativo — cada MISS/LEAK de
> escalação é uma amostra única de uma distribuição estocástica. Isto é
> aceitável para a Fase 0 (é só o "antes"), mas pesa mais na Fase 2, onde a
> mesma amostra única decide qual modelo sobrevive. Ver nota na Fase 2.

### Fase 1 — contexto × `MAX_LOADED_MODELS`, medidos juntos

Modelos fixados nesta fase: **`qwen3:14b` + `qwen3.5:9b`**, o par que a análise
acima mostrou já caber a 32k — e, na config 5, **+ `qwen3:8b`**, o terceiro do
rodízio real documentado em produção.

Uma config por vez, cada uma exigindo reiniciar a tarefa `OllamaServer`.
`OLLAMA_KEEP_ALIVE` fica fixo em `5m` (o valor atual) em todas as linhas —
mudar isso junto invalidaria a comparação:

| # | `OLLAMA_CONTEXT_LENGTH` | `OLLAMA_MAX_LOADED_MODELS` | KV cache | O que responde |
|---|---|---|---|---|
| 1 (atual) | 0 (auto → 32768) | 1 | f16 | baseline pós-migração |
| 2 | 8192 | 1 | f16 | custo do contexto sozinho |
| 3 | 8192 | 2 | f16 | os dois cabem? scheduler mantém os dois residentes? |
| **4** | **0 (auto → 32768)** | **2** | f16 | **célula que faltava**: `MAX_LOADED_MODELS=2` isolado, sem mexer no contexto — separa "foi o contexto" de "bastava subir MAX" |
| 5 | 16384 | **3** | f16 | meio-termo: os três do rodízio real cabem a 16k (~25 GiB, ~5 de folga) — testa se dá para ter três residentes **sem** cortar para 8k |
| **6** | **0 (auto → 32768)** | 2 | **q8_0** | **corrigida:** KV quantizado *substituindo* o corte de contexto, não somado a ele — só assim testa a hipótese de "manter 32k gastando menos VRAM por token" |
| 7 (bônus, se 6 passar) | 0 (auto → 32768) | **3** | **q8_0** | os três modelos, contexto cheio, KV quantizado — ~25,4 GiB pela tabela; se couber, esvazia o argumento inteiro de cortar contexto |

> **Correção de um erro desta própria revisão:** a versão anterior deste plano
> tinha a config 6 como `(8192, 2, q8_0)` — testando `q8_0` *a 8k*, quando a
> ideia era testar `q8_0` *como alternativa a* ir para 8k. A comparação certa
> é config 6 vs config 4 (mesmo `MAX=2`, mesmo contexto 32k, só o tipo de KV
> muda).
>
> **`q8_0` nos modelos-alvo é hipótese por analogia de família, não medição
> direta.** Os números de divergência KL citados na seção "Fora do escopo"
> (0,039 / 0,024) são de `Qwen3.6-27B` e `Qwen3.6-35B-A3B` — **não** dos
> modelos fixados nesta fase (`qwen3:14b`, `qwen3.5:9b`). Mesma família,
> gerações e tamanhos diferentes; o doc-fonte já avisa que o efeito depende do
> modelo específico. Tratar como "risco provavelmente baixo, não confirmado" —
> a config 6 é o que confirma ou derruba isso, não o texto desta seção.

**Critério de sucesso — duas medidas, para duas variáveis diferentes, não uma
prova geral:**

1. **Discrimina `MAX_LOADED_MODELS`:** alternar chamadas entre os modelos-alvo
   **dentro** da janela de `keep_alive` (ex.: A, B, A, B, com poucos segundos
   entre cada) e observar `ollama ps`. Com `MAX=1`, a segunda chamada despeja o
   primeiro modelo **na hora** — o despejo é por limite de slots, não por
   tempo — então essa alternância mostra 1 modelo residente em todas as
   configs com `MAX=1` (1, 2, 5-parcial) e 2+ nas com `MAX=2`/`3` (3, 4, 5, 6,
   7). **Esta é a medida que prova se `MAX_LOADED_MODELS` resolveu algo** — ao
   contrário do que uma versão anterior deste plano afirmava.
2. **Mede `OLLAMA_KEEP_ALIVE`, não `MAX_LOADED_MODELS`:** uma chamada depois
   de > 5 min de ociosidade sempre recarrega, em **qualquer** config desta
   matriz — é o `keep_alive` de 5m expirando, não o scheduler despejando. Não
   é critério de sucesso desta fase; serve só para confirmar que o
   comportamento é o esperado (todas as configs devem mostrar o mesmo tempo de
   recarga aqui). Se o objetivo for atacar esse caso especificamente, é
   `OLLAMA_KEEP_ALIVE` que precisa mudar, numa fase própria — misturar as duas
   perguntas na mesma matriz foi o erro do desenho anterior.

### Fase 2 — modelos novos, com a régua da Fase 0 e a config da Fase 1

**Pré-requisito não cumprido ainda: pull.** `gemma4:26b`, `qwen3.6:27b` e
`qwen3.6:35b-a3b` **não estão** no store (verificado via `/api/tags` — os 14
modelos atuais são qwen3.5:9b, o GGUF Ministral, llama3.2, ministral-8b,
qwen2.5:14b, qwen3:14b, qwen3:8b, gemma3n:e2b, dolphin-llama3:8b,
nomic-embed-text, qwen3:30b-a3b, qwen2.5-coder:14b, llama3.2-vision:11b,
contabil). Pelos tamanhos de registry (18+17+24 GB) são **~59 GB de
download**. O store atual já ocupa ~77 GiB — checar espaço livre em
`C:\Users\Breno Perucchi\.ollama\models` antes de iniciar, e rodar o pull como
passo isolado, fora da janela de medição:

```powershell
foreach ($m in 'gemma4:26b','qwen3.6:27b','qwen3.6:35b-a3b') {
  & "C:\Users\Breno Perucchi\AppData\Local\Programs\Ollama\ollama.exe" pull $m
}
```

(`qwen2.5:14b`, usado na Fase 0 e pressuposto pela Fase 3, já está no store —
não precisa pull.)

Depois do pull:

```bash
MODELS_OVERRIDE="gemma4:26b,qwen3.6:27b,qwen3.6:35b-a3b,qwen3:30b-a3b" \
  THINK=false OUT_SUFFIX=".gpu5090-novos" \
  OLLAMA_URL=http://100.88.95.78:11434 python3 run_chat.py
```

`qwen3:30b-a3b` já está no store (herdado do Windows) e nunca passou pelo
goldset — entra na lista por já estar pago em disco, não por recomendação
prévia.

> **`THINK=false` aqui não é neutro.** Todos os quatro candidatos têm
> capacidade `thinking`, e o critério de eliminação (escalação + traps
> anti-alucinação) é exatamente onde raciocínio costuma mudar o resultado.
> `THINK=false` dá paridade com o comportamento de produção — é provavelmente a
> escolha certa — mas é uma decisão, não um default neutro, e deveria ser
> testada com `THINK=true` num segundo run se o resultado de qualidade for
> disputado entre dois candidatos.

> **`num_ctx` não muda entre Fase 1 e Fase 2.** `run_chat.py` fixa
> `num_ctx: 8192` nas `OPTIONS` de toda requisição (linha 51), independente do
> `OLLAMA_CONTEXT_LENGTH` do servidor. Ou seja: "Fase 2 com a config vencedora
> da Fase 1" afeta **residência e VRAM disponível**, não o que o goldset
> efetivamente vê — o goldset sempre roda a 8k. Isto é esperado (o goldset não
> precisa de mais que 8k), mas vale deixar explícito para não ler a Fase 2 como
> um teste do contexto escolhido.

Critério de eliminação: o fine-check de escalação (token exato, caractere a
caractere, nos 4 casos que devem escalar e nos 5 traps que não devem) — o
`auto_score` médio esconde MISS e LEAK, como já documentado no relatório de
CPU. **Dado o n=1 por caso (ver ressalva na Fase 0), tratar qualquer MISS ou
LEAK isolado como sinal de "investigar", não de eliminação automática** — repetir
o caso específico 3–5 vezes antes de descartar um candidato só por um único
resultado. É a decisão mais cara do plano (define o executor do parque); os A/B
de infra deste mesmo lab usaram 5 repetições por ponto, e o critério de
qualidade merece o mesmo padrão.

### Fase 3 — tool-calling: modelo vs template (controle pendente desde a 3080 Ti)

**Não é independente da Fase 1** — a Fase 1 reinicia a tarefa `OllamaServer`
várias vezes, deixando "produção sem servidor por segundos a cada restart"; uma
corrida da Fase 3 durante isso acumula erros de conexão que se parecem com
falha de tool-calling. Rodar depois da Fase 1 fechar, ou numa janela isolada.

O doc-fonte (`baseline-3080ti/tool-calling-ab-2026-09-02.md`) propõe dois
passos nessa ordem — o plano anterior só herdava o segundo, mais caro:

1. **Primeiro, read-only e barato:** `ollama show --template qwen2.5:14b`
   comparado ao template oficial da Qwen. Pode confirmar ou matar a hipótese do
   template antes de qualquer inferência.
2. **Se a hipótese sobreviver, o A/B de dois braços**, mesmos casos:
   - **A** — ferramentas via parâmetro `tools` (como hoje);
   - **B** — ferramentas definidas em JSON dentro do system prompt.

Há evidência pública (issues #14601, #14493) de que o template do registry
Ollama é problemático para Qwen. Se B subir a taxa do qwen2.5, o veredito "é do
modelo" precisa ser revisado. `qwen2.5:14b` e `qwen3:14b` seguem instalados —
reproduzível sem pull.

## Fora do escopo desta rodada

- **KV cache quantizado permanece fora do escopo geral**, mas **entra na Fase 1
  como config 6**, não fica totalmente de fora como na versão anterior deste
  plano. Correção do argumento: "com 30 GiB não há necessidade de economizar
  VRAM" e "VRAM é a restrição que impede o segundo modelo residente" não podem
  ser verdadeiras ao mesmo tempo — o documento inteiro existe porque VRAM é a
  restrição. `q8_0` corta o KV pela metade sem tirar contexto de ninguém, e para
  Qwen (os dois modelos da Fase 1) a divergência medida é ruído — KL 0,039
  (Qwen3.6-27B) e 0,024 (Qwen3.6-35B-A3B) contra f16. A família `gemma4` é onde
  isso dói (KL 0,377 no MoE) — **9,7× mais sensível que Qwen**, não 3,5×; o
  3,5× do relatório original comparava o MoE gemma4 contra o **irmão denso da
  mesma família** (0,377/0,108), não contra Qwen (0,377/0,039 = 9,7×). Como
  `gemma4` só entra na Fase 2, a Fase 1 pode testar `q8_0` em Qwen sem esse
  risco.
- **llama-server direto / MTP**: 1,73× medido no Qwen3.6-27B denso é grande
  demais para ignorar, mas só compensa se um modelo virar executor principal —
  prematuro antes da Fase 2 escolher esse modelo.
- **`OLLAMA_NUM_PARALLEL`**: identificado acima como causa alternativa da fila,
  não medido nesta rodada. Candidato a fase própria depois que
  `MAX_LOADED_MODELS` estiver resolvido — os dois compostos tornam difícil
  atribuir qual resolveu o quê.
- **Observabilidade** (`journalctl` → `ProgramData\ollama-server\*.log`): é
  pendência operacional do runbook de migração, não parametrização.

## Ordem de execução

1. Fase 0 (zero risco, só leitura da API)
2. Fase 1, configs 2–6 (mexe na tarefa; produção fica sem servidor por segundos
   a cada restart)
3. Pull dos modelos da Fase 2 (janela separada, ~59 GB — checar espaço e tempo
   antes de agendar)
4. Fase 2, com a config vencedora da Fase 1
5. Fase 3, depois da Fase 1 fechar — não em paralelo com ela

## Histórico de revisão

**Rodada `llm-bench-1`** (2026-09-04, `llm-bench-rev` + `llm-bench-rev-2`, cega
e paralela): 18 achados distintos (15 de `rev-2`, 4 de `rev`, 1 sobreposto) —
nenhum CONFLITO entre os dois revisores. Achados de maior impacto: a tese
central "contexto compra residência" estava contradita pela própria
aritmética do documento (o par-alvo já cabia a 32k); a matriz da Fase 1 não
tinha a célula que isolaria essa tese; duas linhas de KV medido estavam
trocadas (corrigido via `/api/show`); e o descarte de `q8_0` contradizia a
premissa do documento.

**Rodada `llm-bench-2`** (2026-09-04, mesma dupla): checou se a correção da
rodada 1 resolveu de fato — **15 de 18 fechados**. Três continuavam abertos e
mais 6 erros novos apareceram nas partes reescritas (nenhum em texto que já
estava correto antes). Os dois mais graves: o critério de sucesso da Fase 1
tinha o sinal invertido (a medida "dentro do `keep_alive`" é que discrimina
`MAX_LOADED_MODELS`, não a de "> 5 min", que só testa `keep_alive`); e a config
6 (`q8_0`) testava a hipótese errada — combinava contexto curto **e** KV
quantizado em vez de usar `q8_0` como alternativa ao corte de contexto. Também
corrigiu a extrapolação de VRAM para os três modelos a 16k (cabe, não "não
cabe") e sinalizou que a geometria de atenção do `qwen3.5:9b` pode não ser
linear (`/api/show` não retorna `head_count_kv` para ele). Ambas as rodadas
completas em `.herdr/review/llm-bench-{1,2}/*/verdict.md`.

**Rodadas de correção esgotadas (máximo 2 por protocolo).** As correções acima
não passaram por uma terceira rodada de revisão cega — ficam para o dono do
plano conferir, ou para a próxima vez que este documento for revisado.
