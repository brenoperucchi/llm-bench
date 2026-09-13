# Pendências e lacunas

[English](en/open-questions.md) | **Português (Brasil)**

Registro derivado do [handoff](history/handoff-2026-09-12.md), das fontes
citadas abaixo e da conferência offline feita na organização do repositório.
Uma pendência não autoriza executar medições no servidor de produção.

| Tema | O que falta | Critério para fechar |
|---|---|---|
| Fase 6b: causa do truncamento | Separar hipóteses com `num_ctx=98304` e `NUM_PARALLEL=1` | Janela autorizada, log de alocação e truncamento, contagem efetiva e raw persistido; a medição ainda não foi feita. |
| Goldset e escolha do default | Avaliar concentração e agrupamento por pergunta também na comparação dos modelos | Análise que preserve clusters e explicite alcance do desempate; nove perguntas não equivalem a 196 observações independentes. |
| Spill especulativo | Corrigir e validar o check cego ao alvo do Gemma | Detector que não aceite como prova suficiente os 1,38 GiB de `/api/ps`; TODO continua no harness. |
| Fase 5: programação | Resolver sandbox de execução e realizar goldset | Resultado de execução verificável com contrato de avaliação, não apenas score textual. |
| Dois residentes sob carga | Medir dois modelos atendendo simultaneamente | Cenário e artefato próprios; a Fase 6 mediu um modelo por vez. |
| `keep_alive=5m` | Investigar efeito no padrão real de chamadas | Experimento que meça cold loads e latência para a carga-alvo. |
| PT→EN | Revisar alcance do diagnóstico com base no raw | [Achado documentado](achados/ACHADO-qwen3-14b-idioma-template-2026-09-12.md) registra divergências do handoff; nenhuma correção de prompt aplicada. |
| Check de idioma | Examinar falsos negativos quando detector retorna `tie` | Casos de controle e verificação sobre o corpus; comportamento encontrado no achado PT→EN. |
| Detector de promessa de suporte | Examinar cobertura da formulação “criar um ticket de suporte” | Validar contra respostas completas e token de escalação; veja [achados](rtx5090/achados.md). |
| Reprodutibilidade histórica | Recuperar dados não persistidos das fases e disco, se existirem | Artefatos originais com proveniência; não reconstruir dados a partir de médias publicadas. |

Fontes: [Fase 6b](../results/RESULTADO-fase6b-numparallel-contexto-longo-2026-09-12.md),
[decisão de produção](../results/DECISAO-producao-2026-09-09.md),
[relatório dos juízes](../results/RESULTADO-juiz-familia-2026-09-10.md),
[catálogo de experimentos](rtx5090/experimentos.md).

## Encerrado nesta organização

O PT→EN ganhou documento próprio, o acervo ganhou índice, e as evidências
disponíveis passaram a ter um manifesto de integridade. Isso não encerra lacunas
experimentais nem altera decisões de modelo, prompt ou servidor.
O encaminhamento ao `llm-exec` mencionado no handoff não foi realizado como
parte da publicação; não há confirmação de recebimento a registrar.
