# `qwen3:14b`: respostas em inglês e reprodução do exemplo do prompt

[English](../en/findings/qwen3-14b-language-template.md) | **Português (Brasil)**

Data da documentação: 2026-09-12. Estado: **comportamento confirmado nos dados salvos; mecanismo causal não isolado**. Esta consolidação apenas inspecionou arquivos locais; não executou inferência nem modificou o prompt de produção.

## Resultado e correção do handoff

O `qwen3:14b` respondeu em inglês às 15 perguntas em português dos três casos de passo a passo da reamostragem. Em `howto_invoice_pt`, todas as respostas começam com o exemplo de invoice presente no system prompt. A evidência confirma reprodução literal nesse caso e associação entre formato e idioma na amostra. Não prova que a prioridade das instruções seja a causa exclusiva.

O [handoff de partida](../history/handoff-2026-09-12.md) registra “264 bytes literais” e “30/30 respostas em português” nos casos sem `expect_steps_format`. A inspeção do [JSON original](../../results/reamostra_pt_escalacao_1789114271.json) **não confirma esses dois números**:

- O exemplo completo de invoice tem **326 caracteres, 328 bytes UTF-8**, sem a quebra de linha final. Quatro respostas são exatamente esse exemplo; a quinta começa com ele e acrescenta um fechamento. Não foi identificado no handoff um recorte que permita reproduzir a alegação específica de 264 bytes.
- Das outras 30 respostas, 15 são classificadas `pt` e 15 são classificadas `tie`. Estas últimas reproduzem **em inglês** o bloco de escalação de 267 bytes. Portanto, `lang_ok=true` em 30/30 não significa 30/30 respostas em português.

Não se deve transportar a igualdade do exemplo de invoice para os três casos: as respostas sobre Schedule C e importação CSV variam e adaptam os passos à tarefa.

## Amostra e proveniência

Fonte primária: [reamostra_pt_escalacao_1789114271.json](../../results/reamostra_pt_escalacao_1789114271.json).

SHA-256 do arquivo verificado: `6e92ab90aaabd0ba53ccdc499fef3c4d389b15462509b7c3c5d3227e1dcc60ae`.

O [harness](../../baseline-3080ti/repro/reamostra_pt_e_escalacao.py) registra cinco chamadas por caso, seeds `1000, 1017, 1034, 1051, 1068`, `temperature=0.7`, `num_ctx=8192`, `think=false`. O JSON contém 45 registros de idioma do `qwen3:14b` e 20 registros de escalação do `qwen3.5:9b`, sem erros de chamada. O campo global `options.seed` contém a última seed; cada registro preserva a seed efetivamente usada.

| Caso do `qwen3:14b` | `expect_steps_format` | Detector salvo | Inspeção do texto |
|---|---|---|---|
| `howto_invoice_pt` | true | 5/5 `en` | Inglês; exemplo de invoice no início das cinco |
| `howto_schedule_c_pt` | true | 5/5 `en` | Inglês; passos adaptados a Schedule C |
| `howto_import_csv_pt` | true | 5/5 `en` | Inglês; passos adaptados à importação |
| `plaid_trap_pt` | false | 5/5 `pt` | Português |
| `payroll_trap_pt` | false | 5/5 `pt` | Português |
| `greet_pt` | false | 5/5 `pt` | Português |
| `escalate_stripe_broken_pt` | false | 5/5 `tie` | Inglês; bloco literal de escalação |
| `escalate_wrong_numbers_pt` | false | 5/5 `tie` | Inglês; bloco literal de escalação |
| `pricing_pt` | false | 5/5 `tie` | Inglês; bloco literal de escalação, indevida neste caso |

São **30 respostas em inglês e 15 em português** neste recorte, por inspeção do conteúdo. Não é uma estimativa da taxa de erro de idioma em produção: os nove casos foram escolhidos para investigação e só há cinco amostras por caso.

## O que o prompt permite concluir

O [system prompt](../../prompts/system_prompt.txt) tem a instrução de usar o idioma do cliente sob `Your Personality`. A seção `Response Format Rules (VERY IMPORTANT)` pede `Always` e `this exact pattern`, seguida de padrão e exemplo em inglês. O exemplo de invoice é reproduzido nas respostas verificadas.

Essa organização é **compatível com influência do exemplo sobre o idioma**. Não houve aqui intervenção controlada separando idioma do exemplo, força das instruções, caso da pergunta e demais elementos. A redação “causa confirmada byte a byte” do handoff mistura a observação de igualdade com uma explicação causal que ela, sozinha, não estabelece.

O paralelo com o [LEAK de pricing](../../ACHADO-qwen3-14b-pricing-leak-2026-09-04.md) é observável: blocos literais do prompt reaparecem nas respostas. Entretanto, o texto de escalação aparece tanto quando a escalação é correta quanto quando é indevida. Reprodução literal não é um detector suficiente de erro de roteamento.

## Limitações dos detectores encontradas na leitura

### Idioma: empate aceito como acerto

Em [run_chat.py](../../run_chat.py), `detect_lang` conta poucos marcadores textuais; quando as contagens empatam, retorna `tie`. `run_auto` aceita esse empate para qualquer idioma esperado. O bloco inglês de escalação produz esse resultado e passa em `lang_ok` mesmo em perguntas PT. Assim, o split correto do detector é **15 `en`, 15 `pt`, 15 `tie`**; ler `lang_ok` como classificação linguística produz a afirmação incorreta de 30/30 PT.

Esse é um limite verificado do avaliador, não uma alteração aplicada nesta organização. Um eventual ajuste precisa preservar os resultados históricos e a versão da régua.

### Escalação: promessa não reconhecida pelo regex

Nos 20 registros do `qwen3.5:9b`, há **1 MISS**, em `escalate_wrong_numbers_pt`, seed `1051`; os outros 19 têm o token esperado. O registro sem token diz precisar escalar a questão e pede e-mail para “criar um ticket de suporte”. Mesmo assim, `promete_escalar=false` e `falha_silenciosa=false`: o regex `PROMETE` do harness não cobre essa formulação.

O `escalation_ok=false` detectou o MISS. O campo especializado `falha_silenciosa` perdeu a promessa no texto; seu zero não comprova ausência de promessa sem token. No caso `escalate_double_charge_en`, que motivou a reamostragem, foram 5/5 com token nesta rodada. Isso não apaga a ocorrência histórica relatada no cabeçalho do harness.

## Decisão preservada e pendências

O prompt canônico permaneceu byte-idêntico ao [backup anterior às tentativas](../../prompts/system_prompt.pre-fix-2026-09-04.txt), conferido nesta documentação. Não foi editado: as variantes v1/v2/v3 anteriores já tiveram resultados incompatíveis, incluindo omissão de token em escalações reais. A propriedade do sistema de atendimento e a decisão de mudança continuam no Contábil.

Este documento fecha a pendência de **documentar** o achado. Não houve encaminhamento a outro agente nem aplicação em produção. Permanecem sem teste controlado: causa do idioma, taxa fora destes casos, correção do detector de idioma e ampliação do detector de promessa.

## Como reconferir sem inferência

O trecho abaixo apenas lê JSON e texto; não importa nem executa o runner de inferência.

```python
import json
from collections import Counter
from pathlib import Path

root = Path('.')  # executar na raiz do projeto
data = json.loads((root / 'results/reamostra_pt_escalacao_1789114271.json').read_text())
rows = [r for r in data['registros'] if r['modelo'] == 'qwen3:14b']
prompt = (root / 'prompts/system_prompt.txt').read_text()
example = prompt.split('Example for creating an invoice:\n', 1)[1].split('\n\n## Navigation Reference', 1)[0]
invoice = [r['resposta'] for r in rows if r['id'] == 'howto_invoice_pt']
print(len(example), len(example.encode('utf-8')))       # 326, 328
print(sum(t == example for t in invoice))               # 4
print(sum(t.startswith(example) for t in invoice))      # 5
print(Counter(r['lang_detectado'] for r in rows))        # en:15, pt:15, tie:15
```
