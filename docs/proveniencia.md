# Proveniência e integridade

[English](en/provenance.md) | **Português (Brasil)**

Esta organização começou pelo handoff indicado pelo usuário e consultou os
relatórios, scripts e resultados locais. Não buscou benchmarks na internet,
não leu integralmente o transcript anterior e não fez nova medição de GPU.

## Fontes preservadas

| Fonte | Tratamento |
|---|---|
| [Handoff](history/handoff-2026-09-12.md) | Cópia do arquivo disponível no momento da organização. Resumo de sessão, com afirmações que exigem conferência no raw. |
| [README anterior](history/README-before-organization.md) | Preservado antes de substituir a entrada do projeto; inclui atribuição do ensaio `chat_raw.gemma4` à CPU i7-14700KF. |
| [Resultados](../results/) | Relatórios e respostas históricas preservados, inclusive rodadas invalidadas. |
| [Prompts](../prompts/) | Canônico, backup e tentativas experimentais preservados. |
| [Sessões](../SESSOES.md) | Referências de origem; não representam arquivos de sessão incluídos no repositório. |
| [Manifesto](../artifacts/manifest.json) | Lista dos arquivos de evidência, tamanhos e SHA-256; tipo indica extensão, não validade ou hardware. |

O snapshot do handoff tem SHA-256
`1a76112cb51736b0d6c4683568321cd71428c26362b37569472549cb3f16beaa`.
A fonte local é `.herdr/handoff/llm-bench-20260912-220504-3731916.md`.
O arquivo foi atualizado externamente entre a primeira leitura da retomada e
esta cópia: o adendo final da Fase 6b, antes contraditório, já consta corrigido
no snapshot. As alegações PT→EN permanecem como estavam na fonte e são
qualificadas no [achado dedicado](achados/ACHADO-qwen3-14b-idioma-template-2026-09-12.md).

A sessão completa anterior foi indicada como JSONL de ID
`d5005acf-9e83-40c4-b68b-84d0e6feb85e`. Ela não está incluída na publicação.
Os relatórios também citam `.herdr/review/`, arquivos temporários e projetos
consumidores. Essas referências externas não equivalem a evidências completas
presentes neste repositório. O catálogo marca as lacunas de reprodução.

## Ordem de leitura e conflitos

Leia primeiro a consolidação em [experimentos](rtx5090/experimentos.md),
[achados](rtx5090/achados.md) e [decisões](decisoes.md), depois a fonte vinculada.
Alguns relatórios históricos preservam recomendações retiradas e números
substituídos; suas seções finais de correção são parte essencial da evidência.
Um documento chamado “FINAL” ou um handoff não dispensa essa conferência.

Quando resumo e raw divergem, a documentação nova registra ambos e explica
qual conclusão a inspeção sustenta. Não foram alterados os dados brutos para
fazê-los concordar com a narrativa. Se o raw não existe, o resultado é atribuído
ao relatório e a limitação é declarada.

Exemplos:

- PT→EN: “264 bytes” e “30/30 PT” do handoff não são reproduzidos pela inspeção
  registrada no [achado](achados/ACHADO-qwen3-14b-idioma-template-2026-09-12.md).
- Fase 6b: o truncamento é observado, mas a explicação de divisão por slots foi
  contradita pelo log, conforme [correção](../results/RESULTADO-fase6b-numparallel-contexto-longo-2026-09-12.md).
- Juízes e Fase 7: versões anteriores têm defeitos de harness e não devem ser
  agregadas às re-medições corrigidas. [Catálogo](rtx5090/experimentos.md).

## Publicação e manutenção

O repositório inclui documentação, scripts, prompts e evidências selecionadas
pelo inventário. Ambientes virtuais, caches, estado local do Herdr e arquivos
de credenciais ficam fora do Git. Os caminhos históricos dos artefatos foram
mantidos para preservar as referências e a resolução relativa dos scripts.

A regra `.gitattributes` preserva os bytes, inclusive em checkout no Windows.
O manifesto cobre evidências, não os índices editoriais em `docs/` ou READMEs.
A validação de links cobre os documentos novos e ignora os snapshots históricos;
não checa destinos externos nem fragmentos de seção.

Para acrescentar uma medição, use o [template](templates/experimento.md),
registre dados completos, atualize o catálogo apropriado e execute os comandos
de [verificação offline](metodologia.md). Corrigir a documentação não é corrigir
um sistema de produção; registre separadamente qualquer aplicação operacional.
