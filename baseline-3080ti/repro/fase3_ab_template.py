#!/usr/bin/env python3
"""Fase 3 - A/B modelo vs template: tools nativo (A) vs JSON no system prompt (B).

Mesma pergunta e mesma ferramenta 'dre' do repro_tool.py original (sessao
43f68058, 2026-09-02), agora direto no Ollama (nao pelo gateway), para isolar
o template de registry do Ollama de qualquer coisa que o gateway faca.

Revisado (rodada llm-bench-4, 2026-09-05): braco A agora valida nome da
funcao e presenca do argumento obrigatorio 'escopo' (antes, bastava
tool_calls nao-vazio); braco B tenta extrair o primeiro objeto {...}
balanceado quando o corpo inteiro nao e um JSON puro, e reporta "chamou" e
"chamou em formato limpo" como contagens separadas; ordem dos bracos agora
alterna por repeticao (era todo A, depois todo B); erros de infra (timeout,
conexao) saem do denominador em vez de contar como falha do modelo.

Uso: python3 fase3_ab_template.py <modelo> <n_por_braco>
"""
import json
import os
import sys
import urllib.error
import urllib.request

# Default aponta pro localhost porque esta sessao so alcanca o servidor via
# tunel SSH (100.88.95.78:11434 direto parou de responder em 2026-09-05,
# causa do lado do cliente, nao identificada -- ver
# MIGRACAO-windows-nativo-2026-09-04.md). Passe OLLAMA_URL se sua sessao
# alcancar o tailnet/LAN direto, sem precisar de tunel.
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
PROMPT = "Qual foi o resultado do KCO em 2026? Use a ferramenta dre."

TOOL = {"type": "function", "function": {
    "name": "dre", "description": "Consulta o DRE consolidado de um escopo e periodo",
    "parameters": {"type": "object", "properties": {
        "escopo": {"type": "string"}, "de": {"type": "string"}, "ate": {"type": "string"}},
        "required": ["escopo"]}}}

SYSTEM_B = """Voce tem acesso a esta ferramenta:

{tool_json}

Quando precisar usa-la, responda APENAS com um objeto JSON nesta forma exata,
sem nenhum texto antes ou depois:
{{"tool": "dre", "arguments": {{"escopo": "...", "de": "...", "ate": "..."}}}}

Nao explique, nao formate como bloco de codigo, nao adicione comentario.
Se nao precisar da ferramenta, responda normalmente em texto.""".format(
    tool_json=json.dumps(TOOL, ensure_ascii=False, indent=2))

# Parametros de amostragem deliberadamente NAO pinados (sem temperature, sem
# seed, sem num_ctx no payload) -- ficam no default do servidor, que muda com
# a config de fase em fase. Documentado aqui em vez de forcado porque este
# script tambem serve para reproduzir falhas em condicao "de producao", onde
# o cliente real (llm-gateway) tambem nao pina esses valores.


def _extract_balanced_json(content):
    """Acha o primeiro objeto {...} balanceado em content e tenta parsear.
    Usado quando o corpo inteiro nao e JSON puro (cerca de markdown, frase
    antes, raciocinio vazado) -- sem isso, qualquer texto extra em volta do
    JSON derruba a chamada inteira para ANOMALA mesmo quando o modelo
    realmente decidiu chamar a ferramenta."""
    start = content.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(content[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(content[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def call_a(model):
    """Braco A: parametro tools nativo do Ollama.

    Retorna (chamou, limpo, content). 'chamou' exige nome correto e
    argumento obrigatorio 'escopo' presente -- antes bastava tool_calls
    nao-vazio, o que aceitava nome errado ou chamada sem argumento
    obrigatorio como sucesso. 'limpo' = chamou sem nenhum texto solto
    (content vazio) junto da chamada estruturada.
    """
    payload = {"model": model, "messages": [{"role": "user", "content": PROMPT}],
               "tools": [TOOL], "stream": False, "think": False}
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps(payload).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        b = json.load(r)
    calls = b["message"].get("tool_calls") or []
    content = (b["message"].get("content") or "").strip()
    if not calls:
        return False, False, content
    fn = calls[0].get("function", {})
    args = fn.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    chamou = fn.get("name") == "dre" and isinstance(args, dict) and "escopo" in args
    limpo = chamou and not content
    return chamou, limpo, content


def call_b(model):
    """Braco B: ferramenta descrita em JSON dentro do system prompt, sem 'tools'.

    Retorna (chamou, limpo, content). 'limpo' = o corpo inteiro ja era JSON
    puro (json.loads direto). 'chamou' tambem aceita o objeto extraido via
    _extract_balanced_json quando o corpo nao e JSON puro -- sem isso, um
    "OK, aqui esta:" antes do JSON ou um bloco de raciocinio vazado conta
    como "o modelo ignorou a ferramenta", quando na verdade ele so nao
    obedeceu ao formato de saida exigido.
    """
    payload = {"model": model, "messages": [
        {"role": "system", "content": SYSTEM_B},
        {"role": "user", "content": PROMPT}],
        "stream": False, "think": False}
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps(payload).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        b = json.load(r)
    content = (b["message"].get("content") or "").strip()
    limpo = False
    parsed = None
    try:
        parsed = json.loads(content)
        limpo = True
    except json.JSONDecodeError:
        parsed = _extract_balanced_json(content)
    chamou = False
    if isinstance(parsed, dict):
        args = parsed.get("arguments")
        chamou = parsed.get("tool") == "dre" and isinstance(args, dict) and "escopo" in args
    return chamou, limpo, content


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:14b"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 8

    print(f"modelo={model} n={n} (ordem alternada A/B por repeticao)\n")
    arms = (("A (tools nativo)", call_a), ("B (JSON no system prompt)", call_b))
    stats = {label: {"chamou": 0, "limpo": 0, "erro_infra": 0, "n": 0} for label, _ in arms}

    for i in range(1, n + 1):
        for label, fn in arms:
            s = stats[label]
            try:
                chamou, limpo, content = fn(model)
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                s["erro_infra"] += 1
                print(f"  [{label}] {i}. ERRO_INFRA -> {type(e).__name__}: {e}")
                continue
            except Exception as e:  # noqa: BLE001 - falha inesperada, nao classificada
                chamou, limpo, content = False, False, f"ERRO_INESPERADO: {type(e).__name__}: {e}"
            s["n"] += 1
            s["chamou"] += chamou
            s["limpo"] += limpo
            marca = "OK " if chamou else "ANOMALA"
            print(f"  [{label}] {i}. {marca}")
            if not chamou:
                print(f"       -> {content[:500]!r}")

    print()
    for label, s in stats.items():
        print(f"{label}: {s['chamou']}/{s['n']} chamou a ferramenta corretamente "
              f"({s['limpo']}/{s['n']} em formato limpo)"
              + (f"; {s['erro_infra']} erro(s) de infra descartado(s) da amostra"
                 if s["erro_infra"] else ""))


if __name__ == "__main__":
    main()
