#!/usr/bin/env python3
"""Benchmarks tok/s for local Ollama models on this machine's GPU."""
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

OLLAMA_URL = "http://localhost:11434"
PROMPTS = [
    "Explique em 3 paragrafos como funciona a fotossintese.",
    "Escreva uma funcao em Python que verifica se um numero e primo, com comentarios.",
    "Liste 10 ideias de nomes para uma cafeteria e explique cada uma em uma frase.",
]
RUNS_PER_PROMPT = 2
RESULTS_DIR = Path(__file__).parent / "results"


def get_gpu_info():
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader"],
            capture_output=True, text=True, timeout=15,
        )
        line = out.stdout.strip().splitlines()[0]
        name, mem, driver = [p.strip() for p in line.split(",")]
        return {"name": name, "vram": mem, "driver": driver}
    except Exception as e:
        return {"error": str(e)}


def list_models():
    r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
    r.raise_for_status()
    return [m["name"] for m in r.json()["models"]]


def run_once(model, prompt):
    payload = {"model": model, "prompt": prompt, "stream": False}
    t0 = time.perf_counter()
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=600)
    wall = time.perf_counter() - t0
    r.raise_for_status()
    d = r.json()
    eval_count = d.get("eval_count", 0)
    eval_duration_ns = d.get("eval_duration", 0)
    prompt_eval_count = d.get("prompt_eval_count", 0)
    prompt_eval_duration_ns = d.get("prompt_eval_duration", 0)
    tok_s = eval_count / (eval_duration_ns / 1e9) if eval_duration_ns else None
    prompt_tok_s = (
        prompt_eval_count / (prompt_eval_duration_ns / 1e9)
        if prompt_eval_duration_ns else None
    )
    return {
        "wall_s": round(wall, 3),
        "eval_count": eval_count,
        "eval_tok_s": round(tok_s, 2) if tok_s else None,
        "prompt_eval_count": prompt_eval_count,
        "prompt_tok_s": round(prompt_tok_s, 2) if prompt_tok_s else None,
    }


def bench_model(model):
    print(f"\n=== {model} ===")
    runs = []
    for prompt in PROMPTS:
        for i in range(RUNS_PER_PROMPT):
            try:
                res = run_once(model, prompt)
            except Exception as e:
                print(f"  ERRO: {e}")
                continue
            runs.append(res)
            print(f"  run {i+1}: {res['eval_tok_s']} tok/s "
                  f"({res['eval_count']} tokens, {res['wall_s']}s)")
    valid = [r["eval_tok_s"] for r in runs if r["eval_tok_s"]]
    avg = round(sum(valid) / len(valid), 2) if valid else None
    return {"model": model, "runs": runs, "avg_tok_s": avg}


def main():
    models = sys.argv[1:] or list_models()
    gpu = get_gpu_info()
    print(f"GPU: {gpu}")
    print(f"Modelos: {models}")

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "gpu": gpu,
        "prompts": PROMPTS,
        "runs_per_prompt": RUNS_PER_PROMPT,
        "models": [],
    }
    for model in models:
        results["models"].append(bench_model(model))

    RESULTS_DIR.mkdir(exist_ok=True)
    out_file = RESULTS_DIR / f"bench_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResultados salvos em {out_file}")

    print("\n=== RESUMO ===")
    for m in results["models"]:
        print(f"{m['model']:45s} {m['avg_tok_s']} tok/s (media)")


if __name__ == "__main__":
    main()
