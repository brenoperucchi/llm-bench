# Track A - Chat (auto-checks)

Referencia de qualidade: **qwen2.5:14b** (modelo de producao).
auto_score = fracao de checks objetivos aprovados (escalation, include, not_include, idioma, formato, sem aspas).
A nota subjetiva final sai do gabarito lendo `chat_raw.json`.

| Modelo | auto_score medio | tokens/s medio | anti_hallucination | escalation | greeting | grounding | howto |
|---|---|---|---|---|---|---|---|
| deepseek-r1:32b | 94% | 68.6 | 100% | 100% | 70% | 80% | 97% |
