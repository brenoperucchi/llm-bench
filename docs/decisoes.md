# Decisões e limites de aplicação

Estado documentado até 12/09/2026. Não é uma consulta em tempo real ao servidor.
Fonte principal: [decisão de produção](../results/DECISAO-producao-2026-09-09.md),
lida junto ao [handoff](history/handoff-2026-09-12.md) e às correções dos relatórios.

| Assunto | Decisão registrada | Evidência e limite |
|---|---|---|
| Default de atendimento | Manter `qwen3:14b` | 40/45 na reamostragem dos 9 casos críticos; defeitos de escalação concentrados em um caso. Não significa ausência de falhas de idioma ou cobertura geral. |
| Segundo residente | `qwen3.5:9b` | Cabe junto do default; 0/4 no contrato completo de pesquisa multi-rodada corrigido, portanto essa função exige outra avaliação. |
| KV cache | `q8_0` | Redução registrada de 4,62 GiB no `qwen3:14b`; 40/45 nos mesmos nove casos sob f16 e q8. Neutralidade fora dessa amostra não demonstrada. |
| Concorrência | `NUM_PARALLEL=2` | [Fase 6](../results/RESULTADO-fase6-numparallel-2026-09-05.md), com um modelo por vez e prompts de 2.108 tokens. |
| Residência | `MAX_LOADED_MODELS=2` | [Fase 1](../results/RESULTADO-fase1-contexto-maxloaded-2026-09-04.md); efeito medido sobre recarga, não dois residentes atendendo simultaneamente. |
| Flash Attention | Variável não definida | A/B on/off sem efeito observável; não isola se o recurso estava efetivamente ativado internamente. |
| Juiz no goldset | Não usar | [Comparação rotulada](../results/comparacao-check-vs-juiz-2026-09-10.json): check 12/12, 0 FP; melhor juiz 11/12, 3 FP. |
| Juiz em produção | Possível, não implementado | A medição habilita uma opção, nenhum consumidor a pediu. Não há juiz a desligar. |
| Juiz contra rubricas | Não medir neste desenho | [Sondagem e extensão dos checks](../results/RESULTADO-juiz-familia-2026-09-10.md): redundância em grande parte e ausência de gabarito automático para o restante. |
| Prompt canônico | Preservar | [Tentativas de correção](../ACHADO-qwen3-14b-pricing-leak-2026-09-04.md) v1/v2/v3 não resolveram o conjunto; a v2 perdeu token em 50% das escalações reais do `qwen2.5:14b` na medição citada. |
| Contexto longo | Mecanismo pendente; nenhuma mudança de config | [Correção da Fase 6b](../results/RESULTADO-fase6b-numparallel-contexto-longo-2026-09-12.md): não demonstra benefício de trocar `NUM_PARALLEL` para 1. |

## Recomendações retiradas

**Guarda baseada em texto literal de escalação:** a coincidência com o bloco
do prompt não distingue LEAK de escalação legítima. Na reamostragem, os mesmos
267 bytes ocorriam em 5 erros e 20 escalações legítimas; a guarda teria precisão
de 20%. O sinal depende da pergunta e de sua expectativa.
[Registro da retratação](../results/DECISAO-producao-2026-09-09.md).

**Juiz offline e alegações sobre família:** a primeira recomendação confundiu
família com tamanho, e outra versão usou respostas truncadas pelo próprio
harness. A re-medição corrigida é preservada; o check rotulado elimina a
justificativa para juiz offline. [Relatório com correções](../results/RESULTADO-juiz-familia-2026-09-10.md).

**“`NUM_PARALLEL` divide o contexto de cada slot”:** o log registra
98.304 tokens por slot e 196.608 no total com dois slots. O truncamento existe,
mas essa explicação de alocação foi contradita. As previsões de duas hipóteses
coincidem no cenário observado. [Correção causal](../results/RESULTADO-fase6b-numparallel-contexto-longo-2026-09-12.md).

## Pendências que qualificam a decisão

Os 196 pares de avaliação de juízes vêm de nove perguntas, e uma concentra
oito dos doze defeitos. A aplicação desse critério de agrupamento à própria
escolha do modelo continua em aberto. A documentação conserva a decisão
operacional e a limitação estatística; não declara um vencedor geral.
Veja [pendências](pendencias.md) e [modelos](rtx5090/modelos.md).
