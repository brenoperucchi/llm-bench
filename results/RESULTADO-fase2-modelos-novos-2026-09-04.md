# Fase 2 — modelos novos no goldset — RTX 5090, 2026-09-04

5 candidatos pesquisados na internet (verificados contra o registry real do
Ollama, não contra listas de blog — ver ressalva sobre "Laguna XS" abaixo),
baixados e rodados contra o mesmo goldset da Fase 0. `THINK=false`,
`temperature=0.7`, `num_ctx=8192`, mesma config de servidor da Fase 1
(32k/`MAX_LOADED_MODELS=2`/f16).

## Placar de rodada única (não confiar sozinho — ver Fase Fine-check abaixo)

| Modelo | Origem | auto_score | tok/s | anti_halluc | escalation | greeting | grounding | howto |
|---|---|---|---|---|---|---|---|---|
| `laguna-xs-2.1` | poolside (EUA) | 97% | 258,5 | 92% | 100% | 90% | 100% | 100% |
| `qwen3:30b-a3b` | Alibaba | 93%* | 293,4 | 100% | 90% | 90% | 80% | 92% |
| `qwen3-coder:30b` | Alibaba | 93% | 265,2 | 96% | 90% | 90% | 100% | 92% |
| `glm-4.7-flash` | Z.ai | 93% | 204,4 | 92% | 100% | 80% | 80% | 94% |
| `gpt-oss:20b` | OpenAI | 90% | 259,8 | 100% | 85% | 80% | 80% | 91% |

Para comparação, a régua da Fase 0 (mesmo goldset, mesma config, modelos
menores): `qwen3.5:9b` 98% / 183 tok/s, `qwen2.5:14b` 97% / 138 tok/s,
`qwen3:14b` 92% / 135 tok/s (com o LEAK de pricing documentado à parte).

`*` `qwen3:30b-a3b` — ver achado de vazamento de raciocínio abaixo; o
`auto_score` de 93% está contaminado por texto de pensamento em inglês
incluído na resposta, não reflete a qualidade da resposta final sozinha.

## Fine-check — por que o placar acima não decide nada sozinho

Todo caso com falha (score < 1,0) nas categorias `escalation` e
`anti_hallucination` foi lido byte a byte, e os quatro mais graves foram
repetidos 5× com seeds diferentes (`temperature=0.7`, sem repetir os seeds já
vistos):

| Modelo | Caso | Tipo | Taxa real (n=5) |
|---|---|---|---|
| **`gpt-oss:20b`** | `escalate_wrong_numbers_pt` | **MISS** (devia escalar, não escalou) | **3/5 corretos (60%)** |
| **`laguna-xs-2.1`** | `quickbooks_trap_en` | **LEAK** (não devia escalar, escalou) | **1/5 corretos (20%)** |
| **`qwen3-coder:30b`** | `quickbooks_trap_en` | LEAK, mesmo caso | **1/5 corretos (20%)** |
| `glm-4.7-flash` | `quickbooks_trap_en` | LEAK, mesmo caso | 3/5 corretos (60%) |

**`laguna-xs-2.1` empatava com o melhor score do dia numa rodada só (97%),
mas erra o trap do QuickBooks 4 vezes em 5 quando reamostrado.** O
`auto_score` de rodada única escondeu isso — exatamente o risco que a Fase 0
já tinha registrado como ressalva metodológica, agora confirmado com dado.

`gpt-oss:20b` — o modelo com fama de "tool-calling mais limpo" — tem o **pior
tipo de falha do goldset inteiro**: confiante e errado. Na resposta real
(ver fonte), ele deu um passo-a-passo de 9 itens de troubleshooting genérico
para "por que meu P&L está com números errados" — um caso `account-specific`
que o próprio system prompt manda escalar — sem nunca admitir que não pode
verificar os dados da conta do usuário. Não é falta de informação, é
diagnóstico fabricado com aparência de autoridade.

## Achado técnico: `qwen3:30b-a3b` vaza raciocínio em 100% dos casos

Apesar de `THINK=false` enviado em toda chamada, `qwen3:30b-a3b` incluiu um
bloco de raciocínio (terminado em `</think>`, sem abertura `<think>` visível)
**em 18 de 18 respostas**. Nenhum dos outros 4 modelos testados hoje faz isso.

A resposta **depois** do `</think>` costuma ser boa — no caso `pricing_pt`,
por exemplo, a conclusão final é exatamente correta (direciona a Settings →
Billing, não inventa preço, em português) — mas o texto inteiro entregue ao
usuário inclui o raciocínio cru em inglês antes disso, o que:

1. Contamina o `auto_score`: o check de idioma conta o texto todo, não só a
   resposta final, e o raciocínio em inglês derruba `lang_ok` mesmo quando a
   resposta de verdade está em português.
2. É inutilizável em produção como está — um agente de suporte não pode expor
   "Okay, the user is asking about... Let me recall the product knowledge
   section..." para o cliente.

**Investigado a fundo — não é bug de template, é o checkpoint mesmo.**

Comparei o template de chat real (`ollama show --template`) do
`qwen3:30b-a3b` com o do `qwen3:14b` (que respeita `think:false`
perfeitamente). O `qwen3:14b` implementa dois mecanismos que o
`qwen3:30b-a3b` não tem: (1) um sufixo `/think` ou `/no_think` anexado à
última mensagem do usuário, e (2) um bloco `<think>\n\n</think>\n\n` **já
fechado e vazio** pré-inserido no prompt antes da geração começar, quando
`think:false` é pedido — o truque padrão para "enganar" um modelo de
raciocínio híbrido a pular direto para a resposta.

Criei um Modelfile local (`qwen3-30b-thinkfix`) copiando os dois mecanismos
do `qwen3:14b` para o `qwen3:30b-a3b` (mesmos pesos, só o template mudou) e
testei — **ainda vazou raciocínio**, agora citando literalmente o
`/no_think` que recebeu e ignorando. Para eliminar de vez a hipótese de erro
no meu template, testei o caso mais extremo possível: montei o prompt à mão,
via `/api/generate` com `raw:true`, com o bloco `<think>\n\n</think>\n\n`
**já perfeitamente pré-fechado**, sem depender de nenhum template — o
próprio checkpoint, com um prompt logicamente idêntico ao que funciona no
`qwen3:14b`, **gerou um novo bloco de pensamento por conta própria depois do
bloco vazio**, como se o vazio não estivesse lá.

**Conclusão: as duas intervenções testadas (Modelfile com os mecanismos do
`qwen3:14b`; prompt bruto via `raw:true` com o bloco já fechado, sem
depender de nenhum template) não corrigiram o vazamento** — a segunda em
particular elimina qualquer participação do template de renderização,
já que `raw:true` não passa pelo sistema de templates do Ollama. Isso aponta
fortemente para uma característica do próprio checkpoint `qwen3:30b-a3b`
(ao que tudo indica, esta variante MoE foi treinada/afinada sem o sinal de
"desligar pensamento" que a variante densa `qwen3:14b` tem), mas não esgota
todo o espaço possível de intervenções — é a leitura mais provável dado o
teste mais rigoroso que se conseguiu montar, não uma prova exaustiva de
impossibilidade. Isto é uma investigação diferente e não relacionada ao LEAK
de pricing do `qwen3:14b` (`ACHADO-qwen3-14b-pricing-leak-2026-09-04.md`) —
aquele é um problema no *system prompt* da aplicação
(`prompts/system_prompt.txt`), não no template de registry do Ollama, e
**segue sem correção adotada** (três tentativas fracassaram, revertido para o
original) — não "resolvido/revertido em horas" como uma versão anterior
deste parágrafo dizia.

**Único caminho viável de uso**: pós-processamento — quem integrar este
modelo precisa cortar tudo até e incluindo o último `</think>` antes de usar
ou pontuar a resposta. Isso não é algo que o Ollama resolve por padrão para
este checkpoint específico; teria que entrar como lógica no lado do cliente
(gateway, ou este próprio harness). Não implementado nesta sessão — a
resposta real do modelo (depois do corte) parece boa, mas isso não foi
validado com o corte aplicado, só inspecionado manualmente em poucos casos.

## Verificação de proveniência dos candidatos

Antes de baixar, cruzei os nomes citados por blogs de SEO com o registry real
do Ollama — dois nomes ("Qwen3-Coder 32B", "GLM-4.6 Air") não batiam com
nenhuma tag real; os nomes corretos são `qwen3-coder:30b` e (a família mais
próxima) `glm-4.7-flash`. Um terceiro nome, "Laguna XS 2.1", parecia
fabricado por soar genérico demais — **confirmado real**: é da poolside
(startup americana, fundada por Jason Warner, ex-CTO do GitHub), publicado
oficialmente no Hugging Face e no registry do Ollama.

Três dos cinco candidatos são de origem chinesa (`qwen3:30b-a3b`,
`qwen3-coder:30b` — Alibaba; `glm-4.7-flash` — Z.ai/Zhipu), refletindo onde
está a maior parte da oferta aberta de MoE pequeno hoje, não escolha
deliberada.

## Velocidade — todos os MoE muito mais rápidos que os densos da Fase 0

| Classe | tok/s |
|---|---|
| MoE novos (20-30B totais conforme o modelo — `gpt-oss:20b` é 20B, não 30B —, 3-3,8B ativos) | 204–293 |
| Densos da Fase 0 (14B/9B) | 135–183 |

`qwen3:30b-a3b`, apesar de "30B", foi o mais rápido do dia inteiro
(293,4 tok/s) — confirma de novo, empiricamente e nesta placa, o achado
central do relatório de CPU: MoE fura o teto de banda de memória.

## Pendências antes de qualquer decisão de produto

1. **Nenhum destes 5 modelos deveria substituir o default do gateway ainda.**
   Todos têm pelo menos um defeito real e reproduzível (não amostral) nas
   categorias que mais importam (escalação/anti-alucinação).
2. Se `qwen3:30b-a3b` for revisitado, primeiro resolver o vazamento de
   `<think>` (Modelfile customizado ou versão de Ollama diferente) antes de
   julgar sua qualidade de conteúdo — o `auto_score` medido hoje o subestima.
3. `laguna-xs-2.1` e `qwen3-coder:30b` são especialistas em código rodando
   fora do próprio domínio (suporte ao cliente) — o LEAK no trap de
   QuickBooks pode ser característico de modelos afinados para
   ferramentas/código, que tendem a escalar mais fácil qualquer coisa fora do
   escopo claro. Vale testar goldset de código com eles antes de descartar.
4. Nenhum caso de `howto` ou `greeting` foi investigado a fundo nesta rodada
   — o foco foi nos dois tipos de erro que o plano trata como críticos
   (MISS/LEAK de escalação).
