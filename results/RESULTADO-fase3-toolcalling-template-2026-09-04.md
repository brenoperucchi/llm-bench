# Fase 3 — tool-calling: modelo vs template — RTX 5090, 2026-09-04

Pergunta em aberto desde a 3080 Ti (`baseline-3080ti/tool-calling-ab-2026-09-02.md`):
o `qwen2.5:14b` chamava ferramenta em só 4/12 (33%) contra 12/12 do `qwen3:14b`
— era o modelo, ou o template de tool-calling do registry do Ollama? Nunca
tinha sido separado.

## Passo 1 — ler o template real (read-only, sem inferência)

`ollama show qwen2.5:14b --template`, bloco de ferramentas:

```
{{- if .Tools }}
# Tools
...
<tools>
{{- range .Tools }}
{"type": "function", "function": {{ .Function }}}
{{- end }}
</tools>
```

`{{ .Function }}` é interpolado **sem nenhum filtro de serialização JSON** —
exatamente o defeito descrito na issue pública
[ollama#14601](https://github.com/ollama/ollama/issues/14601) ("tool
definitions render using Go struct format instead of valid JSON").

**Mas o template do `qwen3:14b` tem a linha idêntica, byte a byte.** Isso
muda a hipótese: se os dois modelos recebem a mesma renderização (correta ou
não) do bloco de ferramentas — porque essa renderização é código do
**servidor** Ollama, não do modelo — a diferença de comportamento não pode
estar só no template. Isso só é decidido pelo passo 2.

## Passo 2 — A/B modelo vs template, direto no Ollama (sem gateway)

Mesma pergunta e mesma ferramenta `dre` do repro original de 02/09, agora
direto em `100.88.95.78:11434` (isolando qualquer coisa que o `llm-gateway`
pudesse estar fazendo). Dois braços:

- **A** — parâmetro `tools` nativo do `/api/chat` (o caminho de hoje);
- **B** — a mesma ferramenta descrita em JSON dentro do system prompt, com
  instrução explícita de formato de resposta, sem usar `tools` nenhum.

Script: [`baseline-3080ti/repro/fase3_ab_template.py`](../baseline-3080ti/repro/fase3_ab_template.py).

| Modelo | Braço A (tools nativo) | Braço B (JSON no prompt) |
|---|---|---|
| **`qwen2.5:14b`** | **1/8 (12,5%)** | **8/8 (100%)** |
| `qwen3:14b` (controle) | 8/8 (100%) | 8/8 (100%) |

O controle `qwen3:14b` sai limpo nos dois braços — confirma que o script
funciona (nenhum dos dois formatos quebra por si só) e que, **para um modelo
forte o bastante**, os dois são igualmente alcançáveis. Não confirma que os
dois braços têm a mesma dificuldade em geral: `SYSTEM_B` muda mais de uma
coisa ao mesmo tempo — troca o transporte da ferramenta (JSON no prompt em
vez do parâmetro `tools`) **e** acrescenta instruções explícitas de formato
("responda APENAS com um objeto JSON... não explique, não formate como
bloco de código") que o braço A não precisa, porque a API nativa já lida com
a estrutura. Um modelo mais fraco em tool-calling nativo poderia se sair
melhor em B só por causa dessas instruções extras, sem que a renderização de
A esteja de fato malformada — ver a ressalva sobre isso no veredito abaixo.

## Como o `qwen2.5:14b` falha no braço A

Não tenta uma chamada malformada — **ignora que existe uma ferramenta**.
Todas as 7 respostas anômalas seguem o mesmo padrão: o modelo raciocina sobre
"2026 ainda não chegou, não há dados" e sugere ao usuário perguntar de novo
com outro ano — como se a pergunta fosse só conversa, sem nenhuma ferramenta
disponível para consultar. Bate com a hipótese: se o bloco de ferramentas
chega ilegível, o modelo pode nem reconhecer que há algo para chamar.

## Veredito: workaround comprovado; causa é hipótese, não isolada

- **O workaround funciona, isso é medido, não hipótese**: o braço B resolve
  o defeito de 12,5% para 100% sem tocar no modelo. Responde a pergunta
  prática — o workaround de #14601 (ferramentas em JSON no system prompt)
  funciona de verdade para este modelo, nesta placa, hoje.
- **A causa ("é o template/servidor") é a hipótese mais provável, não uma
  isolação comprovada** (achado de revisão, rodada `llm-bench-7`): o desenho
  do A/B muda duas coisas de uma vez no braço B — o transporte da ferramenta
  *e* instruções explícitas de formato que o braço A não tem. O
  `qwen3:14b` recebendo a mesma renderização de ferramentas e nunca falhando
  é compatível com "o template está malformado, mas só incomoda modelos
  fracos" — só não **exclui** a explicação alternativa de que `qwen2.5:14b`
  é geralmente mais fraco em tool-calling nativo, e as instruções extras de B
  compensam essa fraqueza geral, independente de a renderização de A estar
  malformada ou não. Separar as duas exigiria um braço B com o mesmo
  transporte de A mas instruções equivalentes (ou vice-versa), o que este
  teste não fez.

Isso não foi confirmado a nível de bytes (não consegui capturar o prompt
exato renderizado — o log de debug do Ollama não expõe esse nível de
detalhe sem instrumentar o binário, e não persegui isso além do ponto de
retorno razoável). A afirmação "o texto renderizado é malformado" continua
sendo inferência da issue pública + do padrão de falha observado, não
observação direta byte a byte nesta sessão.

## O que isso muda

1. **A troca do default do gateway para `qwen3:14b` (02/09) continua sendo a
   decisão certa** — o dado prático (1/8 nativo, 8/8 com workaround) não muda.
   O motivo mais preciso continua em aberto: pode ser que `qwen2.5:14b` seja
   sensível a um jeito específico de apresentar ferramentas (hipótese mais
   provável, não isolada — ver veredito acima), ou que ele seja mais fraco em
   tool-calling nativo de forma geral e o workaround compense por dar
   instruções mais explícitas. As duas leituras concordam sobre o que fazer
   (usar `qwen3:14b`), só não sobre por quê.
2. **Se algum dia o `qwen2.5:14b` (ou outro modelo antigo/frágil) precisar
   voltar a ser usado com ferramentas**, o workaround do braço B
   (JSON no system prompt, sem o parâmetro `tools`) é uma alternativa viável e
   testada — 100% neste A/B, contra 12,5% do caminho nativo.
3. **Vale reportar a montante**: se a hipótese de fragilidade específica por
   geração de modelo (não por template quebrado universalmente) for
   confirmada por alguém com acesso ao código-fonte do Ollama, é um dado novo
   para a issue #14601, que hoje só descreve o sintoma no lado do template.

## Ressalva adicional — revisão de código (rodada `llm-bench-4`, 2026-09-05)

Os dois revisores confirmaram, independentemente, que os braços A e B do
`fase3_ab_template.py` usavam **réguas de sucesso diferentes**: A aceitava
qualquer `tool_calls` não-vazio (sem checar nome/argumento obrigatório), B
exigia `json.loads()` limpo do corpo inteiro (qualquer texto solto ao redor
do JSON contava como falha, mesmo que o modelo tivesse "a intenção" certa).
Script corrigido — ver o cabeçalho de
[`fase3_ab_template.py`](../baseline-3080ti/repro/fase3_ab_template.py).

**Isso não muda o veredito acima.** Checagem direta: com uma régua mais
frouxa em A e mais rígida em B, o viés só favoreceria A e desfavoreceria B —
e mesmo assim A ficou em 1/8 e B em 8/8 para o `qwen2.5:14b`, sem nenhum caso
limítrofe onde a diferença de régua poderia ter trocado o resultado (nem
`qwen3:14b`, 8/8 nos dois braços de qualquer jeito). O mesmo raciocínio vale
para a Fase 4 (`qwen3.5:9b`, 8/8 nos dois braços) — ver a ressalva já
registrada em `RESULTADO-fase4-toolcalling-qwen35-2026-09-05.md`.

## Estado final

Servidor confirmado na config 4 (Fase 1), 32k, `qwen3:14b` + `qwen3.5:9b`
residentes, sem recarga. Nada em produção foi alterado por esta fase — todas
as chamadas foram inferência normal contra o `/api/chat`.
