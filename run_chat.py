#!/usr/bin/env python3
"""
Track A - Chatbot benchmark harness (Lana / Isafi).

Compara modelos leves candidatos contra o modelo de producao (qwen2.5:14b)
usando o system prompt REAL de producao e um gold set de perguntas.

Sem dependencias externas: usa apenas urllib da stdlib.
Roda como usuario `app`. Fala com o Ollama em http://localhost:11434.

Saidas:
  results/chat_raw.json   -> todas as respostas cruas + metricas + auto-checks
  results/chat_table.md   -> tabela resumo (auto-score + tokens/s) para leitura rapida

A nota subjetiva (gabarito) e dada depois, lendo chat_raw.json.
"""
import json
import os
import re
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Referencia (regua de qualidade) = modelo de producao atual.
REFERENCE = "qwen2.5:14b"
# Candidatos leves a avaliar.
# NOTA (run local, host Ryzen 7 3800X): o apps usava `ministral-3:3b`, um modelo
# CUSTOM que so existe no store do host apps (nao esta no registry publico).
# Aqui ele foi substituido pelo proxy publico mais proximo da MESMA linhagem
# Mistral: Ministral-8B-Instruct-2410 (GGUF Q4_K_M, comunidade), aliasado como
# `ministral-8b`. ATENCAO: e 8B, nao 3B -> a linha de tok/s dele nao e comparavel
# 1:1 com o apps; serve pra avaliar comportamento (escalacao/alucinacao/idioma)
# da familia Mistral, nao velocidade do 3B.
CANDIDATES = ["gemma3n:e2b", "ministral-8b", "llama3.2:latest"]
MODELS = [REFERENCE] + CANDIDATES
# Override opcional da lista de modelos por env (run GPU pula a regua qwen14b,
# que nao cabe nos 8GB de VRAM da RX 580):
#   MODELS_OVERRIDE="gemma3n:e2b,ministral-8b,llama3.2:latest"
_models_env = os.environ.get("MODELS_OVERRIDE", "").strip()
if _models_env:
    MODELS = [m.strip() for m in _models_env.split(",") if m.strip()]

# Sufixo opcional dos arquivos de saida (ex.: OUT_SUFFIX=".gpu" -> chat_raw.gpu.json)
# para nao sobrescrever runs anteriores (apps/local/gpu).
OUT_SUFFIX = os.environ.get("OUT_SUFFIX", "")

# Opcoes deterministas o suficiente pra comparar (seed fixa).
OPTIONS = {"temperature": 0.7, "num_ctx": 8192, "seed": 42}
TIMEOUT = 300  # CPU-only: modelos grandes podem demorar

# Modelos "thinking" (qwen3.x etc.): por padrao o Ollama gera um bloco de
# raciocinio antes da resposta -> latencia alta e desnecessaria pro widget de
# suporte (a Lana deve responder direto; a regua qwen2.5:14b nao "pensa").
# THINK=false desliga via campo /api/chat; THINK=true forca ligado.
# Default (nao setado): nao manda o campo -> comportamento padrao do modelo.
_think_env = os.environ.get("THINK", "").strip().lower()
THINK = False if _think_env in ("0", "false", "no", "off") else (
    True if _think_env in ("1", "true", "yes", "on") else None)


def load(path):
    with open(os.path.join(HERE, path), encoding="utf-8") as f:
        return f.read()


def chat(model, system_prompt, user_msg):
    """Uma rodada de chat. Retorna (texto, metrica) ou levanta excecao."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        "stream": False,
        "options": OPTIONS,
    }
    if THINK is not None:
        payload["think"] = THINK
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA}/api/chat", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    wall = time.time() - t0

    text = body.get("message", {}).get("content", "")
    eval_count = body.get("eval_count", 0)
    eval_dur_ns = body.get("eval_duration", 0) or 0
    tok_s = (eval_count / (eval_dur_ns / 1e9)) if eval_dur_ns else 0.0
    metric = {
        "wall_s": round(wall, 1),
        "eval_count": eval_count,
        "tokens_per_s": round(tok_s, 1),
        "load_duration_s": round((body.get("load_duration", 0) or 0) / 1e9, 1),
    }
    return text, metric


# --- Auto-checks -------------------------------------------------------------

STEP_RE = re.compile(r"(?m)^\s*\d+[\.\)]\s+")  # "1. " ou "1) " no inicio da linha


def detect_lang(text):
    """Heuristica boba PT vs EN por marcadores fortes."""
    t = text.lower()
    pt = sum(t.count(w) for w in (" você", " vá ", "passos", "siga", " não ",
                                  " clique", " em seguida", "configura"))
    en = sum(t.count(w) for w in (" you ", " go to", "steps", "follow", " click",
                                  " then ", " settings"))
    if pt == en:
        return "tie"
    return "pt" if pt > en else "en"


# Vazamento de raciocinio. Duas formas: o bloco com tag, e o raciocinio em
# texto puro que alguns modelos emitem sem tag nenhuma. Medido em 2026-09-10:
# as 18 ocorrencias do corpus usavam tag, mas o padrao sem tag existe e nao
# custa cobrir.
REASONING_RE = re.compile(
    r"</?think>|^\s*(okay,? the user|we are given|let me recall|first,? we check|"
    r"the user is asking|according to the guidelines,? we)",
    re.I | re.M)


def run_auto(text, auto, expected_lang):
    out = {}
    has_token = "[ESCALATE_TO_SUPPORT]" in text

    # Escalation
    out["escalation_ok"] = (has_token == auto["expect_escalation"])

    # Step format
    has_steps = bool(STEP_RE.search(text))
    if auto["expect_steps_format"]:
        out["steps_ok"] = has_steps
    else:
        out["steps_ok"] = None  # nao exigido

    # must_include_any: lista de grupos; cada grupo precisa de >=1 termo presente
    inc_ok = True
    for group in auto.get("must_include_any", []):
        if not any(term.lower() in text.lower() for term in group):
            inc_ok = False
            break
    out["include_ok"] = inc_ok

    # must_not_include
    not_ok = all(term.lower() not in text.lower()
                 for term in auto.get("must_not_include", []))
    out["not_include_ok"] = not_ok

    # Language
    detected = detect_lang(text)
    out["lang_detected"] = detected
    out["lang_ok"] = (detected in (expected_lang, "tie"))

    # Nao envolver em aspas (regra do system prompt)
    stripped = text.strip()
    out["no_wrap_quotes"] = not (stripped.startswith('"') and stripped.endswith('"'))

    # Vazamento de raciocinio: o modelo entrega o proprio raciocinio ao usuario.
    # Check GLOBAL, nao por caso -- vale para qualquer pergunta. Acrescentado em
    # 2026-09-10 depois de medir 18 de 251 respostas com o bloco vazado, TODAS do
    # qwen3:30b-a3b e 11 delas com auto_score 1.0: passavam em tudo. Mediana de
    # 3020 chars contra 530 nas limpas, e foi o que produziu as respostas de
    # 12,5 KB que quebraram o harness do juiz.
    out["no_reasoning_leak"] = not bool(REASONING_RE.search(text))

    # Score automatico: fracao de checks objetivos que passaram
    # ATENCAO: este denominador MUDOU em 2026-09-10 com a entrada de
    # no_reasoning_leak. auto_score de artefatos anteriores a essa data nao e
    # diretamente comparavel com os de depois -- eram 5 ou 6 checks, agora sao
    # 6 ou 7. Os campos individuais continuam comparaveis.
    checks = [out["escalation_ok"], out["include_ok"],
              out["not_include_ok"], out["lang_ok"], out["no_wrap_quotes"],
              out["no_reasoning_leak"]]
    if out["steps_ok"] is not None:
        checks.append(out["steps_ok"])
    out["auto_score"] = round(sum(1 for c in checks if c) / len(checks), 3)
    return out


def main():
    system_prompt = load("prompts/system_prompt.txt")
    goldset = json.loads(load("goldset_chat.json"))

    results = []
    print(f"Gold set: {len(goldset)} casos | Modelos: {MODELS}\n")

    for model in MODELS:
        print(f"=== {model} ===")
        for case in goldset:
            cid = case["id"]
            try:
                text, metric = chat(model, system_prompt, case["prompt"])
                auto = run_auto(text, case["auto"], case["lang"])
                err = None
            except (urllib.error.URLError, TimeoutError, Exception) as e:
                text, metric, auto, err = "", {}, {}, f"{type(e).__name__}: {e}"

            flag = "ERR" if err else f"{auto['auto_score']:.0%}"
            ts = metric.get("tokens_per_s", 0)
            print(f"  [{flag:>4}] {cid:<26} {ts:>5.1f} tok/s")

            results.append({
                "model": model, "id": cid, "category": case["category"],
                "lang": case["lang"], "prompt": case["prompt"],
                "response": text, "metric": metric, "auto": auto,
                "judge_hint": case["judge"], "error": err,
            })
        print()

    out_raw = os.path.join(HERE, "results", f"chat_raw{OUT_SUFFIX}.json")
    with open(out_raw, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Respostas cruas -> {out_raw}")

    write_table(results, goldset)


def write_table(results, goldset):
    """Tabela markdown: auto-score medio por modelo + tokens/s + por categoria."""
    by_model = {}
    for r in results:
        m = by_model.setdefault(r["model"], {"scores": [], "tok": [], "cats": {}})
        if r["error"]:
            continue
        m["scores"].append(r["auto"]["auto_score"])
        if r["metric"].get("tokens_per_s"):
            m["tok"].append(r["metric"]["tokens_per_s"])
        c = m["cats"].setdefault(r["category"], [])
        c.append(r["auto"]["auto_score"])

    cats = sorted({c["category"] for c in goldset})
    lines = ["# Track A - Chat (auto-checks)", ""]
    lines.append("Referencia de qualidade: **qwen2.5:14b** (modelo de producao).")
    lines.append("auto_score = fracao de checks objetivos aprovados "
                 "(escalation, include, not_include, idioma, formato, sem aspas).")
    lines.append("A nota subjetiva final sai do gabarito lendo `chat_raw.json`.\n")

    header = "| Modelo | auto_score medio | tokens/s medio | " + \
             " | ".join(cats) + " |"
    sep = "|" + "---|" * (3 + len(cats))
    lines.append(header)
    lines.append(sep)
    for model in MODELS:
        m = by_model.get(model, {"scores": [], "tok": [], "cats": {}})
        avg = sum(m["scores"]) / len(m["scores"]) if m["scores"] else 0
        tok = sum(m["tok"]) / len(m["tok"]) if m["tok"] else 0
        row = [model, f"{avg:.0%}", f"{tok:.1f}"]
        for cat in cats:
            cs = m["cats"].get(cat, [])
            row.append(f"{(sum(cs)/len(cs)):.0%}" if cs else "-")
        lines.append("| " + " | ".join(row) + " |")

    out = os.path.join(HERE, "results", f"chat_table{OUT_SUFFIX}.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Tabela resumo  -> {out}")


if __name__ == "__main__":
    main()
