# Track A - Chat (auto-checks)

Referencia de qualidade: **qwen2.5:14b** (modelo de producao).
auto_score = fracao de checks objetivos aprovados (escalation, include, not_include, idioma, formato, sem aspas).
A nota subjetiva final sai do gabarito lendo `chat_raw.json`.

| Modelo | auto_score medio | tokens/s medio | anti_hallucination | escalation | greeting | grounding | howto |
|---|---|---|---|---|---|---|---|
| qwen3:30b-a3b | 93% | 293.4 | 100% | 90% | 90% | 80% | 92% |
| gpt-oss:20b | 90% | 259.8 | 100% | 85% | 80% | 80% | 91% |
| laguna-xs-2.1 | 97% | 258.5 | 92% | 100% | 90% | 100% | 100% |
| qwen3-coder:30b | 93% | 265.2 | 96% | 90% | 90% | 100% | 92% |
| glm-4.7-flash | 93% | 204.4 | 92% | 100% | 80% | 80% | 94% |
