# Track A - Chat (auto-checks)

Referencia de qualidade: **qwen2.5:14b** (modelo de producao).
auto_score = fracao de checks objetivos aprovados (escalation, include, not_include, idioma, formato, sem aspas).
A nota subjetiva final sai do gabarito lendo `chat_raw.json`.

| Modelo | auto_score medio | tokens/s medio | anti_hallucination | escalation | greeting | grounding | howto |
|---|---|---|---|---|---|---|---|
| qwen3:14b | 92% | 140.6 | 100% | 100% | 80% | 40% | 92% |
| qwen3.5:9b | 97% | 186.0 | 100% | 100% | 100% | 80% | 94% |
| qwen2.5:14b | 92% | 137.2 | 100% | 80% | 80% | 100% | 97% |
