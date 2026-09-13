# Fase 7 — tool-calling multi-rodada com schema fechado — RTX 5090, 2026-09-07

**Resultado principal: não consegui reproduzir a falha relatada pela sessão
acervo.** O `qwen3:14b` — o mesmo modelo que lá produziu **0 conclusões
válidas em 51 casos** — passa aqui em **5/5 no cenário difícil**, sob validação
de contrato completo, sem inventar URL e sem escrever JSON em texto
(bateria de 08/09, depois de o harness ser corrigido; ver o aviso na seção de
resultados sobre o que foi invalidado).

> ## ⚠️ Causa raiz resolvida em 2026-09-07 — pela própria sessão acervo
>
> **A premissa original do relato estava errada, e a correção veio deles.** A
> URL "fictícia" (`zoneamento.campinas.sp.gov.br`) **não era alucinação**: era
> resultado real do buscador deles. O defeito estava na *query*, não na
> resposta do modelo.
>
> **Causa real: fome de informação.** O reasoner deles recebia só um
> `case_id` opaco (`1100205:dossie_municipal::` — código IBGE + tipo de
> documento) e **nunca o nome do município**. Sem saber que 1100205 é "Porto
> Velho, RO", o modelo buscava "zoneamento" genérico, o buscador devolvia
> resultados reais porém genéricos (o portal de Campinas domina busca
> genérica por "zoneamento"), e ele seguia o topo da lista.
>
> **Teste que confirma (deles):** injetaram o nome do município no prompt —
> mapeamento que já existia no repo, só não chegava ao reasoner — e
> rerodaram os mesmos 5 casos com o **mesmo `qwen3:14b`, mesmo perfil "local"
> do gateway**. As buscas viraram "zoneamento Porto Velho RO", "zoneamento
> Belém PA", etc., **5 de 5 acertando o município**, e as URLs seguidas
> viraram legislação real e correta de cada um. Desfecho mudou de 3
> `acao_invalida` para 3 `teto_iteracoes` (pesquisa legítima que não converge
> em 20 rodadas) + 2 `erro_de_provider` (JSON malformado, problema separado e
> ainda aberto).
>
> **Consequência para este documento:** o 10/10 daqui **não** foi falso
> negativo por cenário fácil. Meu cenário sempre deu ao modelo um alvo
> identificável ("Vila Serrana, estado de São Paulo"); o pipeline deles não
> dava. Não era uma tarefa mais difícil — era uma tarefa **impossível**, para
> qualquer modelo ou humano: pesquisar um município cuja identidade foi
> sonegada. A lista de hipóteses que este documento trazia (inchaço de
> contexto, comprimento da cadeia, `think:false`, guardrails no prompt) está
> **descartada como explicação** — ficou preservada abaixo apenas como
> registro do que eu supunha antes da correção.

## O que foi construído

`baseline-3080ti/repro/fase7_multiround_schema.py` — reproduz a **forma** do
desafio do estudo-massa-app, não o código deles: 5 ações em enum fechado
(`search_term`, `follow_url`, `check_revocation`, `conclude`, `escalate`),
rodadas sequenciais até `conclude`/`escalate`/teto, e um executor real onde
**URL fora dos resultados de busca devolve 404 de verdade** — o ponto que
motivou o teste, já que nenhum modelo local tem acesso à web.

Dois cenários:

- **fácil** — 1 busca, 2 resultados, resposta quase casando por palavra-chave.
- **difícil** — município homônimo em MG (valor errado 1,6), lei revogada com
  valor plausível (2,0), notícia sem parâmetros, e a lei vigente (2,4) só
  aparecendo em busca **refinada**. Exige refinar a busca e usar
  `check_revocation` para descobrir que a lei de 2015 foi superada.

Amostragem: `temperature=0.7`, **seed variando por execução**. A primeira
versão usava `temperature=0` com seed fixo — os tempos idênticos denunciaram
que era 1 execução repetida 5 vezes, não uma amostra. **Ressalva que faltava
(achado `llm-bench-8`): a correção veio depois da bateria do cenário fácil, não
antes.** Os artefatos do fácil (`fase7_*-A_17887513*.json`) são da versão
antiga — seed único no topo, `seed: None` por run, mesma sequência de ações nas
cinco. Só a bateria do difícil usa seeds variados.

## Resultados — braço A (`tools` nativo), cenário difícil, n=5

> ## ⚠️ Estes números foram invalidados e refeitos em 2026-09-08
>
> A rodada de revisão `llm-bench-8` achou **três defeitos no harness** que
> produziu a tabela abaixo. Todos confirmados por mim na fonte:
>
> 1. **O avaliador aprovava conclusão semanticamente errada** (P1). Só o
>    **primeiro item** de cada lista era checado; `estado` e `fonte_url` nunca
>    eram olhados; e o valor casava por **substring** — então `"12,4"` passava
>    como se fosse `"2,4"`. Uma conclusão com valor errado, campo errado e
>    fonte inventada passava nos três critérios com `detalhe` vazio.
> 2. **`follow_url` entregava o documento antes de checar proveniência** —
>    adivinhar a URL pulava a busca inteira sem ser marcado como fabricação,
>    contrariando o contrato que o próprio prompt anuncia.
> 3. **O cenário "difícil" nunca exigiu refinamento**: a palavra "vigente"
>    está na própria pergunta e o gatilho de busca casava com ela, então a
>    primeira busca já entregava o alvo. Nos artefatos, 4 das 5 runs concluíam
>    com uma única busca.
>
> Os três foram corrigidos e a bateria foi **refeita**. Resultados válidos na
> seção seguinte; a tabela abaixo fica como registro do que foi publicado
> antes — inclusive porque eu já a havia reportado à sessão acervo.

| Modelo | Conclusão válida | Sem URL inventada | Valor da lei vigente | Rodadas (mediana) | Observação |
|---|---|---|---|---|---|
| `qwen3:14b` | 5/5 | 5/5 | 5/5 | 4 | usou `check_revocation` em 5/5 |
| `qwen3.8:27b` | 5/5 | 5/5 | 5/5 | 7 | mais rodadas, mesmo acerto |
| `qwen3.5:9b` | 2/3 | 3/3 | 2/3 | 6 | 2 erros HTTP 500 fora da amostra + 1 falha de protocolo |

### Bateria refeita com o harness corrigido — 2026-09-08

Contrato completo: **todas** as fontes com `url`+`sha256`+`trecho` conferindo
byte a byte contra documento lido na sessão, **todos** os achados dentro do
enum e com `fonte_url` presente entre as fontes citadas, `estado` correto, e
valor comparado **numericamente** (não por substring).

| Modelo | Contrato completo | Chegou a conclude | Valor certo | URL inventada | Rodadas (mediana) |
|---|---|---|---|---|---|
| `qwen3:14b` | **5/5** | 5/5 | 5/5 | 0 | 6 |
| `qwen3.8:27b` | **5/5** | 5/5 | 5/5 | 0 | 7 |
| `qwen3.5:9b` | **0/4** | 3/4 | 3/3 | 0 | 6 |

A mediana de rodadas do `qwen3:14b` subiu de 4 para 6 — efeito direto de
remover o atalho da palavra "vigente": agora o refinamento é obrigatório.

**O que a validação estrita revelou, e a antiga não podia ver:** o
`qwen3.5:9b` acerta o valor em todas as conclusões (2,4, campo correto), mas
**fabrica o conteúdo das citações a partir da segunda fonte** — `fonte[1]` com
trecho que não existe no documento (runs 2 e 4), `fonte[3]` com `url` vazia
(run 3). Como o avaliador antigo só examinava `fontes[0]`, isso passava
invisível, e era exatamente o furo que o revisor previu.

Para um pipeline que valida `url+sha256+trecho` byte a byte — o do
estudo-massa-app — este é o defeito mais relevante dos três modelos: a
resposta está certa, a primeira fonte está certa, e as fontes de apoio são
inventadas.

Cenário fácil: **3/3 com n=1 efetivo**, repetido cinco vezes, nos três
modelos — não "15/15 com n=5", como uma versão anterior desta linha dizia; os
artefatos mostram seed único e sequência de ações idêntica nas cinco execuções.
Além disso rodou no harness antigo, com o avaliador furado. **Um teste em que
todos passam não discrimina nada** — fica só como piso, e agora com a régua
certa declarada.

## A falha que apareceu — e que é a ponte com o relato do acervo

Uma execução do `qwen3.5:9b` fez **toda a pesquisa corretamente**:
`search_term` → `follow_url` → `check_revocation` → `search_term` (refinada) →
`follow_url` → `check_revocation`, chegou à LC 2.847/2019, valor 2,4, URL e
sha256 certos — e então **respondeu em prosa em vez de chamar `conclude`**:

> *"Agora tenho todas as informações necessárias para concluir: **Resposta:**
> O coeficiente de aproveitamento máximo da zona ZR-3 em Vila Serrana/SP é
> **2,4**… **Fonte exata:** https://legis.vilaserrana.sp.gov.br/… (sha256:
> 3de1bd31…)"*

Trabalho certo, canal errado. Num pipeline que valida `conclude` estruturado,
isso conta como **zero conclusão válida** mesmo o modelo tendo achado a
resposta — que é exatamente a classe de falha relatada pelo acervo ("às vezes
escreve a ação como JSON solto em texto normal"). O modo de falha é real; meu
cenário só o dispara raramente.

## Defeito residual real — confusão de schema (medido pelo acervo, 2026-09-07)

Depois de corrigirem a fome de informação, sobrou um defeito de protocolo do
próprio modelo, este sim atribuível a ele: em **2 de 5 casos**, o `qwen3:14b`
passou um **termo de busca dentro do campo `url` do `follow_url`** —
`follow_url(url="Ananindeua zoneamento")` — em vez de uma URL.

É a mesma família da falha que vi uma vez aqui (`qwen3.5:9b` fazendo a
pesquisa certa e respondendo em prosa em vez de chamar `conclude`): **o
raciocínio está certo, o canal está errado**. Mas é uma classe distinta de
"inventar URL": não é fabricação de conteúdo, é uso errado do schema.

**Meu harness estava classificando as duas coisas juntas** — qualquer
`follow_url` fora dos resultados de busca virava "URL inventada". Corrigido:
agora `nao_url_no_campo_url` é contado separado de `urls_fabricadas`, e o
executor devolve `400 Bad Request` com a orientação certa ("para buscar por um
termo, use `search_term`") em vez de um 404 genérico.

**Reclassificando retroativamente meus artefatos com o critério novo: zero
ocorrências** nos três modelos, nos dois cenários (o único 404 registrado foi
o `qwen3.8:27b` seguindo um link morto que a *busca ofertou* — comportamento
correto, não defeito). Ou seja, meu cenário não reproduz esse defeito também.

Hipótese, marcada como hipótese: pode haver ligação causal entre as duas
coisas — um modelo cujas buscas não estão trazendo nada útil (porque não sabe
o que buscar) pode derivar para usar as ferramentas de forma errada,
tentando "buscar" via `follow_url`. Se for isso, o defeito de schema
diminuiria junto com a correção da query. Os dados deles pós-correção (2/5
ainda com o defeito) sugerem que **não** desaparece por completo, mas não sei
qual era a taxa antes para comparar.

## O que eu supunha antes da correção (registro histórico — hipóteses descartadas)

> As hipóteses abaixo foram escritas **antes** de a sessão acervo achar a
> causa raiz real (fome de informação, ver o box no topo). Nenhuma delas era a
> explicação. Ficam registradas porque algumas continuam sendo diferenças
> reais entre os dois ambientes, e portanto seguem valendo como cuidado
> metodológico para reproduções futuras — só não eram *a* causa.

Em ordem de suspeita, para quem for investigar do lado do estudo-massa-app:

1. **Tamanho e sujeira do retorno das ferramentas.** Meus "documentos" têm
   1–2 KB de texto limpo. Uma página real de site de prefeitura traz dezenas
   ou centenas de KB de HTML, menu, script. Isso incha o contexto rodada a
   rodada e é o candidato número um a degradar a emissão de `tool_calls`.
2. **Comprimento da cadeia.** Aqui a mediana foi 4–7 rodadas; lá são ~20. A
   falha de protocolo acima apareceu justamente na execução mais longa da
   bateria (6 rodadas, contra 4 das que passaram).
3. **`think:false`.** Eu envio explicitamente em toda chamada. Se o gateway
   não envia, o bloco de raciocínio do `qwen3:14b` pode competir com a
   emissão de `tool_calls` — hipótese barata de testar do lado de vocês.
4. **Guardrails no system prompt.** O meu diz, literalmente, "nunca invente
   uma URL: só use `follow_url` em URLs que apareceram num resultado de
   `search_term`", e avisa sobre homônimos e revogação. Se o prompt de vocês
   não tem essas linhas, a diferença pode ser só essa.
5. **Transporte da ferramenta.** Braço B (JSON no system prompt) não foi
   rodado nesta fase — na Fase 3 ele levou o `qwen2.5:14b` de 1/8 para 8/8.
   Se o problema for de renderização de `tools` no lado do Ollama, é o
   contorno já medido neste laboratório.

## Ressalvas desta fase

- **Executor é stub.** Busca e fetch devolvem conteúdo fixo. Mede protocolo,
  grounding e disciplina de citação — **não** mede pesquisa real na web.
- **n=5 por modelo, um cenário.** É o mínimo defensável deste laboratório,
  não uma medida robusta.
- **Só o braço A.** Braço B e o `deepseek-r1:32b` (que está na instância D:,
  porta 11435) ficaram de fora por tempo.
- Os 2 erros HTTP 500 do `qwen3.5:9b` ficaram fora da amostra (tratados como
  infra, não como falha do modelo) — causa não investigada.
- **O teste sempre entrega ao modelo um alvo identificável** (nome do
  município + estado na pergunta). Essa é justamente a variável que, no
  pipeline do estudo-massa-app, estava faltando e explicava tudo. Uma versão
  futura útil seria um cenário "alvo opaco" (só código IBGE, sem nome) — não
  para medir o modelo, mas para medir se ele **reconhece que não tem
  informação suficiente e escala**, em vez de buscar às cegas. Nenhum dos
  três modelos foi testado nisso.

Artefatos: `results/fase7_*.json`, um por modelo/cenário, com as ações de
cada execução, seeds e a avaliação de cada critério.
