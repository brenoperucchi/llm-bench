#!/usr/bin/env python3
"""Compara o check deterministico do goldset com o melhor juiz LLM medido.

Motivo: em 2026-09-10 recomendei o gemma4:26b como auto-check offline do
goldset. A recomendacao estava errada e este script mede por que. O goldset e
um conjunto ROTULADO -- cada caso traz expect_escalation -- entao
run_auto()["escalation_ok"] nao precisa inferir nada, so comparar. O juiz
existe para o caso em que nao ha rotulo, que e producao, nao goldset.
"""
import json, importlib.util
from pathlib import Path

RAIZ = Path("/home/brenoperucchi/Devs/llm-bench")
spec = importlib.util.spec_from_file_location("rc", RAIZ / "run_chat.py")
rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)

pares = json.loads((RAIZ / "results/juiz_pares_2026-09-10.json").read_text(encoding="utf-8"))
gs = {c["id"]: c for c in json.loads(rc.load("goldset_chat.json"))}
J = json.loads((RAIZ / "results/juiz_grande_1789065587.json").read_text(encoding="utf-8"))["juizes"]

det = {"vp": 0, "fp": 0, "vn": 0, "fn": 0, "divergencias": []}
for i, p in enumerate(pares):
    caso = gs[p["id"]]
    acusou = not rc.run_auto(p["resposta"], caso["auto"], caso["lang"])["escalation_ok"]
    defeito = p["verdade"] == "INCORRETO"
    if defeito and acusou: det["vp"] += 1
    elif defeito: det["fn"] += 1; det["divergencias"].append({"i": i, "tipo": "perdeu", **{k: p[k] for k in ("id","modelo","quadrante")}})
    elif acusou: det["fp"] += 1; det["divergencias"].append({"i": i, "tipo": "falso positivo", **{k: p[k] for k in ("id","modelo","quadrante")}})
    else: det["vn"] += 1

n_def = sum(1 for p in pares if p["verdade"] == "INCORRETO")
linhas = [("run_auto (deterministico, sem GPU)", det["vp"], det["fp"], 0.0, 0.0)]
for m in ("gemma4:26b", "qwen3.5:9b", "qwen3:14b"):
    v = J[m]
    linhas.append((m, v["vp"], v["fp"], v["minutos"], {"gemma4:26b": 17.5, "qwen3.5:9b": 5.73, "qwen3:14b": 13.93}[m]))

print(f"{'corretor':38s} {'pegou':>8s} {'FP':>4s} {'precisao':>9s} {'min':>6s} {'GiB':>6s}")
for nome, vp, fp, mins, gib in linhas:
    prec = vp / (vp + fp) if vp + fp else 0
    print(f"{nome:38s} {vp:3d}/{n_def:<4d} {fp:4d} {prec:8.0%} {mins:6.1f} {gib:6.2f}")
print(f"\ndivergencias do check deterministico: {len(det['divergencias'])}")
for d in det["divergencias"]:
    print("  ", d)

saida = {
    "pergunta": "o gemma4:26b serve como auto-check offline do goldset?",
    "resposta": "nao -- o check deterministico ja acerta 12/12 com 0 falso positivo",
    "por_que": ("o goldset e um conjunto ROTULADO: cada caso traz expect_escalation, entao "
                "run_auto so compara e nao precisa inferir. O juiz resolve o caso SEM rotulo, "
                "que e producao. A conclusao 'so a pergunta distingue' vale la, nao aqui."),
    "conjunto": "results/juiz_pares_2026-09-10.json",
    "n_pares": len(pares), "n_defeitos": n_def,
    "deterministico": {k: det[k] for k in ("vp", "fp", "vn", "fn")},
    "juizes": {m: {"vp": J[m]["vp"], "fp": J[m]["fp"], "minutos": J[m]["minutos"]}
               for m in ("gemma4:26b", "qwen3.5:9b", "qwen3:14b")},
}
out = RAIZ / "results/comparacao-check-vs-juiz-2026-09-10.json"
out.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nartefato: {out}")
