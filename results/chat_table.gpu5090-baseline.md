# Track A - Chat (auto-checks)

Referencia de qualidade: **qwen2.5:14b** (modelo de producao).
auto_score = fracao de checks objetivos aprovados (escalation, include, not_include, idioma, formato, sem aspas).
A nota subjetiva final sai do gabarito lendo `chat_raw.json`.

| Modelo | auto_score medio | tokens/s medio | anti_hallucination | escalation | greeting | grounding | howto |
|---|---|---|---|---|---|---|---|
| qwen3:14b | 92% | 135.2 | 100% | 100% | 80% | 40% | 92% |
| qwen3.5:9b | 98% | 183.2 | 100% | 100% | 100% | 100% | 94% |
| qwen2.5:14b | 97% | 138.5 | 100% | 100% | 80% | 100% | 97% |
