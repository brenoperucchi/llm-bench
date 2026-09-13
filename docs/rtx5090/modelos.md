# Modelos medidos e limites de uso

[English](../en/models.md) | **Português (Brasil)**

Inventário documental até o [handoff de 12/09/2026](../history/handoff-2026-09-12.md). Não é uma lista de recomendações atuais do mercado nem inventário consultado ao vivo. Tags são preservadas como aparecem nos artefatos. Modelo disponível, pesquisado ou mencionado num plano não significa modelo medido.

## Decisão registrada

`qwen3:14b` continua default; `qwen3.5:9b` é o segundo residente previsto pela [decisão de produção](../../results/DECISAO-producao-2026-09-09.md). No instante do handoff, só o `qwen3:14b` é explicitamente confirmado como residente. Nenhum juiz LLM foi adotado. O goldset de programação continua pendente: os resultados de suporte não escolhem um modelo para escrever código.

## RTX 5090 — geração e suporte

As duas colunas de velocidade são **experimentos diferentes**: “bench” são três prompts sem system prompt × duas execuções, na primeira medição de 04/09; “chat” é a média da rodada de suporte canônica indicada. Não combiná-las para calcular um único ranking. Não se publica ranking de `auto_score`: o denominador mudou em 10/09 e uma passada por caso não estima robustez.

| Modelo/tag medido | Bench, tok/s | Chat, tok/s | Qualidade/uso observado e limite |
|---|---:|---:|---|
| `qwen3:14b` | 127,77 | 135,2 | Default mantido. 40/45 nos 9 críticos; LEAK QuickBooks, além do pricing. Multirrodada corrigida 5/5. PT→EN nos três casos PT de passos: 15/15. Não é “sem defeito”. |
| `qwen3.5:9b` | 162,23 | 183,2 | 38/45 nos críticos, defeitos em 3 casos. Multirrodada corrigida 0/4 no contrato completo por citações/protocolo; inadequado para tratar 8/8 single-shot como garantia de cadeias. |
| `qwen2.5:14b` | 128,37 | 138,5 | Ferramenta nativa 1/8; JSON no prompt 8/8. Mesmo bloco de template do controle; causa não isolada. Não confundir boa rodada de suporte com robustez no transporte nativo. |
| `qwen3:8b` | 198,10 | — | Medido em velocidade, A/B de SO/CUDA e matriz de residência. Sem rodada de qualidade 5090 equivalente à Fase 0 localizada. |
| `qwen3:30b-a3b` | — | 293,4 | Raciocínio exposto em 18/18 respostas, apesar de `think:false`. Duas intervenções testadas não resolveram; conteúdo após eventual remoção não foi revalidado sistematicamente. |
| `qwen3-coder:30b` | — | 265,2 | LEAK QuickBooks 4/5. Testado em suporte e contexto longo de handoff; não existe goldset de programação concluído. |
| `laguna-xs-2.1` | — | 258,5 | LEAK QuickBooks 4/5; nota alta na passada inicial escondia a falha. Especialista de código testado fora do domínio. |
| `glm-4.7-flash` | — | 204,4 | LEAK QuickBooks 2/5 na reamostragem selecionada. Nenhuma promoção registrada. |
| `gpt-oss:20b` | — | 259,8 | MISS de escalação em números errados 2/5 (3/5 corretos), não 3/5 falhas. Resposta fabricava troubleshooting específico. |
| `qwen3.8:27b` | — | 126,0 | 38/45 nos críticos, 4 casos defeituosos, incluindo MISS; contrato multirrodada corrigido 5/5. Sem vantagem demonstrada que tenha motivado substituir o default. |
| `deepseek-r1:32b` | — | 68,6 | Rodada de 18 casos contém 1 HTTP 500; média de chat não transforma 17 respostas em 18 êxitos. Sem reamostragem equivalente nem Fase 7 concluída. |
| `llama3.2:latest` | 319,30 | — | Geração e julgamento medidos; velocidade não atesta qualidade de suporte. |
| `gemma3n:e2b` | 197,18 | — | Geração e julgamento medidos; sem evidência suficiente de capacidade como juiz nesta amostra. |
| `ministral-8b:latest` | 206,19 | — | Tag presente no benchmark de geração. Relatório de juiz usa `ministral-8b`; não se deduz identidade de digest só pelo nome. |
| `hf.co/bartowski/Ministral-8B-Instruct-2410-GGUF:Q4_K_M` | 202,49 | — | Tag distinta no benchmark. Não unir as duas linhas Ministral sem digest que comprove equivalência. |

Fontes: [bench com hardware e médias](../../results/bench_20260904_043001.json); [Fase 0](../../results/chat_raw.gpu5090-baseline.json); [novos MoE](../../results/chat_raw.gpu5090-novos.json); [27B](../../results/chat_raw.gpu5090-qwen38.json); [R1 32B](../../results/chat_raw.gpu5090-deepseekr1.json); [Fase 2 corrigida](../../results/RESULTADO-fase2-modelos-novos-2026-09-04.md); [reamostragem do incumbente](../../results/RESULTADO-reamostra-qwen3-14b-2026-09-08.md); [Fase 4 e ausência de raw](../../results/RESULTADO-fase4-toolcalling-qwen35-2026-09-05.md); [Fase 7 corrigida](../../results/RESULTADO-fase7-multirodada-schema-2026-09-07.md); [PT→EN](../../results/reamostra_pt_escalacao_1789114271.json).

## RTX 5090 — modelos como juízes de escalação

É outra tarefa: julgar 196 pares rotulados de 9 perguntas, com 12 defeitos. Não mede geração de respostas ao cliente. A tabela usa a rodada sem corte de resposta, com complemento do único erro HTTP.

| Juiz | Defeitos detectados / 12 | Falsos positivos | Leitura válida |
|---|---:|---:|---|
| `llama3.2:latest` | 8 | 126 | Acusa 134/196; sem sinal além do acaso. |
| `gemma3n:e2b` | 4 | 121 | Sem sinal nesta amostra. |
| `deepseek-r1:8b-llama-distill-q4_K_M` | 3 | 26 | Tag real documentada; relatório abrevia o nome. Precisa de orçamento para `thinking`; sem sinal demonstrado. |
| `ministral-8b` | 0 | 0 | Aprova todos os 196; não detecta defeitos. |
| `qwen3.5:9b` | 7 | 0 | Precisão 100% sobre sete acusações; só pega LEAK, nenhum dos três MISS. |
| `qwen3:14b` | 3 | 1 | Precisão 75%; teste por pergunta dá p=0,069, sem significância nesse ajuste. |
| `gemma4:26b` | 11 | 3 | Precisão 79%; pega 9/9 LEAK e 2/3 MISS. Não coexiste com o default na VRAM. |
| Check `run_auto` (não é LLM) | 12 | 0 | Rótulos já informam se deveria escalar. Foi a solução mantida para este goldset, sem inferência/GPU. |

O agrupamento importa: uma pergunta concentra 8/12 defeitos. Tamanho e família variam juntos, portanto não há prova de que tamanho **cause** a diferença. Não interpretar 0 FP em 61 escalações legítimas como taxa populacional zero: são somente quatro perguntas. [Relatório completo](../../results/RESULTADO-juiz-familia-2026-09-10.md), [medição válida](../../results/juiz_grande_1789065587.json), [complemento](../../results/juiz_grande_1789065587_complemento.json), [check × juiz](../../results/comparacao-check-vs-juiz-2026-09-10.json).

## Memória e coexistência: configuração faz parte do número

| Modelo/par | Medição documentada | Consequência |
|---|---|---|
| `qwen3:14b` | 13,55 GiB em f16/NP=1; 18,55 em f16/NP=2 na Fase 6; 13,93 GiB no estado q8_0 posterior | Não tratar VRAM como constante do modelo. Contexto, paralelismo e KV devem acompanhar o número. |
| `qwen3.5:9b` | 5,73 GiB em q8_0 | Par com `qwen3:14b`: 19,66 GiB na configuração documentada, abaixo dos ~30,3 utilizáveis. |
| `qwen3.8:27b` | 16,33 GiB documentados | Soma com o 14B de 30,26 GiB foi considerada sem margem operacional na decisão; não afirmar coexistência segura a partir da soma arredondada. |
| `gemma4:26b` | ~17,5 GiB, alvo 25,23B + rascunho 419,71M | Soma com default ~31,4 GiB; carregar expulsou o `qwen3:14b`. `/api/ps` reporta só ~1,38 GiB do rascunho e não é evidência suficiente de residência total. |

Fontes: [Fase 6 remediada](../../results/RESULTADO-fase6-numparallel-2026-09-05.md), [decisão](../../results/DECISAO-producao-2026-09-09.md), [capacidade corrigida no relatório do juiz](../../results/RESULTADO-juiz-familia-2026-09-10.md). Carregar modelos grandes é uma operação sobre a GPU compartilhada, não uma consequência automática de consultar este catálogo.

## Separação de hardware e dados históricos

- **CPU i7-14700KF:** [chat_raw.gemma4.json](../../results/chat_raw.gemma4.json) e [tabela gemma4](../../results/chat_table.gemma4.md), 16,9 tok/s e nota histórica de 99%, pertencem à execução em CPU identificada pelo [README anterior preservado](../history/README-before-organization.md). Não são números da RTX 5090. O `gemma4:26b` foi medido na 5090 **como juiz** em setembro, tarefa e instrumento diferentes. O relatório consolidado de CPU é citado no acervo como arquivo de outro projeto; não está incorporado aqui.
- **RTX 3080 Ti:** [baseline preservada](../../baseline-3080ti/baseline-3080ti.md) traz telemetria de produção de `qwen3:14b` (63,9–68,0 tok/s) e `qwen3:8b` (100,5 tok/s), com duração total no denominador. Não há benchmark dedicado recuperável de decode dessa placa; não comparar como se fosse o mesmo método do bench 5090.
- **Propostas e números de terceiros:** [estudo inicial de modelos e parametrização](../../rtx5090-modelos-parametrizacao.md) contém candidatos, limites de hardware e benchmarks publicados por terceiros. Estar nesse estudo não coloca um modelo nas tabelas de medições próprias acima.

As lacunas de raw, versões invalidadas e fases pendentes estão reunidas no [catálogo de experimentos](experimentos.md).
