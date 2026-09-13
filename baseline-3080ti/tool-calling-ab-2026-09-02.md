# A/B de tool-calling na 3080 Ti — 2026-09-02

Medição real, feita dois dias antes da troca de placa. **Nunca foi salva como
resultado** — vivia só como comentário no código do `llm-gateway` e como
docstring de teste. Recuperada e congelada aqui em 2026-09-04.

## Os números

| Teste | qwen2.5:14b | qwen3:14b |
|---|---|---|
| tool-calling — chamou a ferramenta | **4/12 (33%)** | **12/12 (100%)** |
| latência mediana (tool-calling) | 2075 ms | 391 ms |
| structured output — JSON válido | 8/8 | 8/8 |
| structured output — `confidence` correta | 8/8 | 8/8 |
| latência (structured output) | 1472 ms | 1454 ms |

Método: 12 chamadas com 3 perguntas diferentes (tool-calling); 8 execuções do
caso real de backtest do MFC (structured output).

**Modo de falha do qwen2.5:** devolve a chamada de ferramenta como **texto** —
às vezes com tokens espúrios em outro alfabeto grudados — e o Ollama não a
reconhece como `tool_call`. Reproduzido também sem o gateway, direto no Ollama.

## Onde estava (fontes originais)

`~/Devs/llm-gateway/src/llm_gateway/profiles.py`, perfil `LOCAL_CHAT`:

```python
    # qwen3 e não qwen2.5 como default: medido em 2026-09-02 com 12 chamadas e 3
    # perguntas diferentes, o qwen2.5:14b emitiu tool_calls em 4/12 (33%) contra
    # 12/12 do qwen3:14b, e com mediana de 2075ms contra 391ms. Nas falhas o
    # qwen2.5 devolve a chamada como TEXTO — às vezes com tokens espúrios em
    # outro alfabeto grudados —, e o Ollama não a reconhece como tool_call.
    # Reproduzido também sem o gateway, direto no Ollama: é do modelo.
    default_model="ryzen9-qwen3-14b",
```

Mesmo arquivo, perfil `BACKTEST_ANALYSIS`:

```python
    # qwen3 e não qwen2.5: medido em 2026-09-02 com 8 execuções do caso real de
    # backtest, os dois empatam em saída estruturada (8/8 JSON válido, 8/8
    # confidence correta, ~1460ms) — mas o qwen3 é o único confiável em
    # tool-calling (12/12 contra 4/12). Convergir os perfis num modelo só reduz
    # a recarga no Ryzen9, que roda com OLLAMA_MAX_LOADED_MODELS=1.
```

`~/Devs/llm-gateway/tests/test_profiles.py`, `test_local_default_is_the_model_that_actually_calls_tools`:

> Regressão de uma medição, não de uma preferência. O perfil `local` existe para
> conversa COM ferramentas. Em 12 chamadas com 3 perguntas diferentes, o
> qwen2.5:14b emitiu tool_calls em 4 (33%) contra 12/12 do qwen3:14b — nas
> falhas devolvendo a chamada como texto, que o Ollama não reconhece. Trocar o
> default de volta reintroduz o defeito.

## A anomalia que ficou sem investigação

Do relato do `dre-exec` em `relatos-originais-2026-09-02.md` (item f):

> **RESPOSTA EM TAILANDÊS**: qwen2.5:14b, perfil local, primeira chamada depois
> de um restart do gateway; sem tool call, cifra inventada (R$ -6.546.567, certo
> era -971.553,41), e 2,3 s de latência quando o normal dele é 11-15 s. NÃO
> INVESTIGOU. Reapareceu no A/B dele: 1 de 8 respostas fora do alfabeto latino.
> Duas ocorrências, zero investigação.

E o verdict do revisor, em `llm-gateway/.herdr/review/llm-1/llm-rev-2/verdict.md`:

> DRE: "EM LUGAR NENHUM: a resposta em tailandês e a latência 2,3 s; o A/B
> inconclusivo; as duas limitações."

Somando com a medição de tool-calling: **saída anômala em 7 de 18 chamadas (39%)**
— `tool_calls=0`, ocasionalmente em alfabeto não-latino. Descartado que fosse o
gateway (6/6 falharam direto no Ollama) e que fosse o system_prompt.

## Hipótese não testada: pode ser o template, não o modelo

O veredito registrado foi "é do modelo". Os testes feitos separam *gateway vs
Ollama* e *com vs sem system_prompt* — mas **nenhum separa o modelo do template
de tool-calling do registry do Ollama**. Três issues abertas descrevem exatamente
esses sintomas:

- [ollama#14601](https://github.com/ollama/ollama/issues/14601) — definições de
  ferramenta renderizadas com o formato de struct do Go em vez de JSON: o modelo
  recebe `{get_weather Get the current...}`. Tool calls do assistente também são
  removidas do histórico antes do template. Aberta em 03/03/2026, Ollama 0.17.5.
- [ollama#14493](https://github.com/ollama/ollama/issues/14493) — Qwen3.5 mapeado
  para o pipeline errado (Hermes-style JSON quando o modelo foi treinado no XML
  do Qwen3-Coder); `</think>` não fechado corrompendo o histórico multi-turn.
- [ollama#15783](https://github.com/ollama/ollama/issues/15783) — o sampler Go
  (`ollamarunner`) aceita e descarta silenciosamente `repeat_penalty`,
  `frequency_penalty` e `presence_penalty`.

Verificado em 2026-09-04: **os modelos do Ryzen9 rodam no `llamarunner`**, não no
`ollamarunner` — o log mostra todos subindo via `llama-server`. Então #15783 não
explica estas anomalias. Mas o Ollama sobe o servidor com
`--no-jinja --chat-template chatml`: o template do GGUF é ignorado e o prompt é
renderizado do lado Go, pelo template do registry — que é o que #14601 e #14493
dizem estar quebrado para Qwen.

**Teste que fecharia a questão** (não feito):

1. `ollama show --template qwen2.5:14b`, comparado ao template oficial da Qwen;
2. repetir o A/B com as ferramentas embutidas no system prompt como JSON, em vez
   do parâmetro `tools` (o workaround de #14601).

Se a taxa subir no passo 2, o veredito "é do modelo" precisa ser revisado — e a
troca de default para qwen3:14b terá sido a decisão certa pelo motivo errado.
Não é mais reproduzível na 3080 Ti, mas é reproduzível na 5090 com os mesmos
modelos, que continuam instalados.

## Scripts de reprodução

Em [`repro/`](repro/) — recuperados do scratchpad efêmero da sessão
`43f68058-337d-4e8a-9da0-44ad61102744` (`/tmp`, que não sobrevive a reboot):

| Script | O que isola |
|---|---|
| `repro_tool.py` | 6 chamadas ao perfil `local` do gateway com uma ferramenta `dre`; marca cada resposta como OK/ANOMALA por `tool_calls` |
| `repro_direto.py` | mesma coisa, direto no Ollama, sem o gateway |
| `repro_sysprompt.py` | com e sem system_prompt, para descartá-lo como causa |
| `repro_hipotese.py` | teste da hipótese levantada na sessão |
| `repro.py`, `rc.py`, `rm.py`, `rs.py`, `rs2.py` | variações menores do mesmo laço |

Todos apontam para `127.0.0.1:8080` (gateway) ou o Ollama do Ryzen9 e são
read-only do ponto de vista da infra — só fazem inferência.
