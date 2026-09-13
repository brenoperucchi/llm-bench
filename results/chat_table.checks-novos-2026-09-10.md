# Track A - Chat (auto-checks)

Referencia de qualidade: **qwen2.5:14b** (modelo de producao).
auto_score = fracao de checks objetivos aprovados (escalation, include, not_include, idioma, formato, sem aspas).
A nota subjetiva final sai do gabarito lendo `chat_raw.json`.

| Modelo | auto_score medio | tokens/s medio | anti_hallucination | escalation | greeting | grounding | howto |
|---|---|---|---|---|---|---|---|
| qwen3:14b | 93% | 133.3 | 100% | 100% | 83% | 50% | 93% |
| qwen3.5:9b | 94% | 169.0 | 97% | 92% | 100% | 50% | 98% |
