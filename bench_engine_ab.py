#!/usr/bin/env python3
"""A/B entre dois endpoints Ollama — mesma GPU, mesmo modelo, mesmo prompt.

Feito para a pergunta "quanto custa rodar sob WSL2 em vez de Windows nativo?",
mas serve para qualquer par de endpoints (cuda_v12 vs cuda_v13, num_ctx X vs Y,
duas versões do Ollama).

Desenho:
  - Alterna A/B/A/B a cada repeticao, em serie. NUNCA em paralelo: os dois
    disputam a mesma GPU e o numero sai sem sentido.
  - Descarta um warmup por (endpoint, prompt) para nao medir o load do modelo.
  - Tres tamanhos de prompt. O longo reusa o system_prompt.txt real (~1,3k
    tokens), proximo dos ~2,1k tokens do trafego de producao medido na baseline.
  - Separa prefill de decode: no decode o WSL2 tende a doer mais, porque a
    geracao e' um lacao de muitos kernel launches pequenos, e e' em launch
    latency que a paravirtualizacao cobra.

Uso:
  ENDPOINT_A=http://127.0.0.1:11434 LABEL_A=wsl \
  ENDPOINT_B=http://127.0.0.1:11435 LABEL_B=windows \
  MODEL=qwen3:8b REPS=5 python3 bench_engine_ab.py

Saidas: results/engine_ab_<timestamp>.json  e  results/engine_ab_<timestamp>.md
"""
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

A_URL = os.environ.get("ENDPOINT_A", "http://127.0.0.1:11434").rstrip("/")
B_URL = os.environ.get("ENDPOINT_B", "http://127.0.0.1:11435").rstrip("/")
A_LABEL = os.environ.get("LABEL_A", "A")
B_LABEL = os.environ.get("LABEL_B", "B")
MODEL = os.environ.get("MODEL", "qwen3:8b")
REPS = int(os.environ.get("REPS", "5"))
NUM_PREDICT = int(os.environ.get("NUM_PREDICT", "256"))
TIMEOUT = int(os.environ.get("TIMEOUT", "300"))

# num_ctx fixo nos dois lados: sem isso cada servidor escolhe pela VRAM que ve,
# e a comparacao vira "contexto diferente", nao "engine diferente".
NUM_CTX = int(os.environ.get("NUM_CTX", "8192"))

OPTIONS = {
    "temperature": 0.0,
    "seed": 42,
    "num_ctx": NUM_CTX,
    "num_predict": NUM_PREDICT,
}


def load_system_prompt():
    path = os.path.join(HERE, "prompts", "system_prompt.txt")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


_SYS = load_system_prompt()

PROMPTS = {
    "curto": "Liste tres cores primarias.",
    "medio": (_SYS[: len(_SYS) // 2] + "\n\nResuma as regras acima em tres linhas.")
    if _SYS else "Explique fotossintese em tres paragrafos.",
    "longo": (_SYS + "\n\nResuma as regras acima em tres linhas.")
    if _SYS else "Explique fotossintese em dez paragrafos, com exemplos.",
}


def generate(url, prompt):
    """Uma chamada /api/generate. Devolve as metricas cruas do Ollama."""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": OPTIONS,
        "think": False,
        "keep_alive": "10m",
    }
    req = urllib.request.Request(
        f"{url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    wall = time.perf_counter() - t0

    ev = body.get("eval_count", 0) or 0
    ev_ns = body.get("eval_duration", 0) or 0
    pe = body.get("prompt_eval_count", 0) or 0
    pe_ns = body.get("prompt_eval_duration", 0) or 0
    ld_ns = body.get("load_duration", 0) or 0

    return {
        "wall_s": round(wall, 3),
        "eval_count": ev,
        "prompt_eval_count": pe,
        # decode: o numero que importa para latencia percebida
        "decode_tok_s": round(ev / (ev_ns / 1e9), 2) if ev_ns else None,
        # prefill: throughput real, so confiavel com prompt grande
        "prefill_tok_s": round(pe / (pe_ns / 1e9), 2) if pe_ns else None,
        "ttft_s": round((ld_ns + pe_ns) / 1e9, 3),
        "load_s": round(ld_ns / 1e9, 3),
    }


def server_info(url):
    out = {"url": url}
    try:
        with urllib.request.urlopen(f"{url}/api/version", timeout=15) as r:
            out["version"] = json.loads(r.read().decode("utf-8")).get("version")
    except (urllib.error.URLError, OSError, ValueError) as e:
        out["version"] = f"ERRO: {type(e).__name__}"
    return out


def main():
    endpoints = [(A_LABEL, A_URL), (B_LABEL, B_URL)]

    print(f"modelo={MODEL}  reps={REPS}  num_ctx={NUM_CTX}  num_predict={NUM_PREDICT}")
    for label, url in endpoints:
        info = server_info(url)
        print(f"  {label:<10} {url}  ollama {info.get('version')}")
        if str(info.get("version", "")).startswith("ERRO"):
            raise SystemExit(f"endpoint {label} inacessivel — abortando antes de medir")
    print()

    # Warmup: carrega o modelo nos dois lados e descarta o resultado.
    print("warmup (descartado)...")
    for label, url in endpoints:
        for name in PROMPTS:
            try:
                generate(url, PROMPTS[name])
            except Exception as e:  # noqa: BLE001 - warmup nao deve abortar a run
                print(f"  aviso: warmup {label}/{name} falhou: {type(e).__name__}")
    print()

    rows = []
    for rep in range(1, REPS + 1):
        # Ordem alternada por repeticao: dilui deriva termica e de clock.
        order = endpoints if rep % 2 else list(reversed(endpoints))
        for label, url in order:
            for name, prompt in PROMPTS.items():
                try:
                    m = generate(url, prompt)
                    err = None
                except Exception as e:  # noqa: BLE001
                    m, err = {}, f"{type(e).__name__}: {e}"
                rows.append({"rep": rep, "endpoint": label, "prompt": name,
                             "error": err, **m})
                d = m.get("decode_tok_s")
                p = m.get("prefill_tok_s")
                flag = "ERR" if err else f"{d:6.1f}"
                print(f"  rep{rep} {label:<10} {name:<6} decode={flag} "
                      f"prefill={p if p else '-':>9} ttft={m.get('ttft_s','-')}")
    print()

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    outdir = os.path.join(HERE, "results")
    os.makedirs(outdir, exist_ok=True)

    raw = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL, "reps": REPS, "options": OPTIONS,
        "endpoints": {A_LABEL: server_info(A_URL), B_LABEL: server_info(B_URL)},
        "prompts": {k: len(v) for k, v in PROMPTS.items()},
        "runs": rows,
    }
    raw_path = os.path.join(outdir, f"engine_ab_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    md_path = os.path.join(outdir, f"engine_ab_{ts}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render(rows))

    print(f"bruto  -> {raw_path}")
    print(f"resumo -> {md_path}")
    print()
    print(render(rows))


def _med(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return statistics.median(vals) if vals else None


def render(rows):
    ok = [r for r in rows if not r.get("error")]
    lines = [f"# A/B de engine — {MODEL}", ""]
    lines.append(f"`{A_LABEL}` = {A_URL} · `{B_LABEL}` = {B_URL}")
    lines.append(f"num_ctx={NUM_CTX}, num_predict={NUM_PREDICT}, temperature=0, seed=42, "
                 f"{REPS} repeticoes alternadas, warmup descartado.\n")
    lines.append("| prompt | metrica | " + A_LABEL + " | " + B_LABEL + " | delta |")
    lines.append("|---|---|---|---|---|")

    for name in PROMPTS:
        a = [r for r in ok if r["endpoint"] == A_LABEL and r["prompt"] == name]
        b = [r for r in ok if r["endpoint"] == B_LABEL and r["prompt"] == name]
        for key, rotulo in (("decode_tok_s", "decode tok/s"),
                            ("prefill_tok_s", "prefill tok/s"),
                            ("ttft_s", "TTFT s")):
            ma, mb = _med(a, key), _med(b, key)
            if ma is None or mb is None:
                continue
            delta = f"{100*(mb-ma)/ma:+.1f}%" if ma else "-"
            lines.append(f"| {name} | {rotulo} | {ma:.2f} | {mb:.2f} | {delta} |")

    errs = [r for r in rows if r.get("error")]
    if errs:
        lines.append(f"\n**{len(errs)} chamadas falharam.** Ver o JSON bruto.")
    lines.append("\n> `prefill tok/s` do prompt `curto` nao e' throughput — sao poucos "
                 "tokens, dominados por overhead fixo. Leia so as linhas `medio`/`longo`.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
