#!/usr/bin/env python3
"""Reamostragem dos casos criticos do goldset, n>=5, com seed variando.

Por que existe: a Fase 4 reamostrou os 9 casos criticos do `qwen3.5:9b`
(n=5 cada) e achou defeito em 3 deles. O `qwen3:14b`, default de producao,
NUNCA passou pelo mesmo teste -- so tem a passada unica da Fase 0. Duas
rodadas de revisao cega (llm-bench-6 e 7) apontaram, independentemente, que
comparar "taxa mais baixa" entre os dois compara um numero medido com um
desconhecido. Este script fecha essa lacuna.

Diferente do ad hoc da Fase 4, aqui TUDO fica persistido em results/: cada
resposta, cada seed, cada auto-check. O achado de revisao llm-bench-7 foi
que a Fase 4 e a unica fase decisoria sem artefato reconferivel.

Uso: python3 reamostra_criticos.py <modelo> [n] [rotulo]
"""
import importlib.util
import json
import re
import statistics
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent.parent
RESULTS = RAIZ / "results"

# Os mesmos 9 casos que a Fase 4 reamostrou no qwen3.5:9b -- 4 de escalacao
# real + 5 traps de anti-alucinacao. Mudar esta lista quebra a comparabilidade.
CRITICOS = [
    "plaid_trap_pt", "autosync_en", "quickbooks_trap_en", "payroll_trap_pt",
    "mobile_trap_en", "escalate_double_charge_en", "escalate_stripe_broken_pt",
    "escalate_feature_en", "escalate_wrong_numbers_pt",
]


def carregar_harness():
    spec = importlib.util.spec_from_file_location("run_chat", RAIZ / "run_chat.py")
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    return rc


def main():
    modelo = sys.argv[1] if len(sys.argv) > 1 else "qwen3:14b"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    rotulo = sys.argv[3] if len(sys.argv) > 3 else modelo

    rc = carregar_harness()
    rc.THINK = False  # convencao do laboratorio desde a Fase 0

    system_prompt = rc.load("prompts/system_prompt.txt")
    goldset = {c["id"]: c for c in json.loads(rc.load("goldset_chat.json"))}

    faltando = [c for c in CRITICOS if c not in goldset]
    if faltando:
        raise SystemExit(f"casos ausentes do goldset: {faltando}")

    print(f"modelo={modelo}  n={n} por caso  casos={len(CRITICOS)}  "
          f"total={len(CRITICOS) * n} chamadas")
    print("seed varia por repeticao; THINK=false\n")

    registros, por_caso, erros = [], {}, 0

    for cid in CRITICOS:
        caso = goldset[cid]
        acertos, falhas_infra = 0, 0
        for i in range(1, n + 1):
            rc.OPTIONS["seed"] = 1000 + i * 17  # mesma progressao da Fase 7
            try:
                texto, metrica = rc.chat(modelo, system_prompt, caso["prompt"])
                auto = rc.run_auto(texto, caso["auto"], caso["lang"])
                erro = None
            except Exception as e:  # noqa: BLE001 - infra vira dado, nao crash
                texto, metrica, auto, erro = "", {}, {}, f"{type(e).__name__}: {e}"
                erros += 1
                falhas_infra += 1
            ok = bool(auto) and auto.get("auto_score", 0) == 1.0
            acertos += ok
            registros.append({
                "id": cid, "categoria": caso["category"], "rep": i,
                "seed": rc.OPTIONS["seed"], "ok": ok, "erro": erro,
                "auto": auto, "resposta": texto, "metrica": metrica,
            })
        validas = n - falhas_infra
        por_caso[cid] = {"acertos": acertos, "validas": validas,
                         "categoria": caso["category"]}
        marca = "" if acertos == validas else "   <-- DEFEITO"
        print(f"  {cid:<28} {acertos}/{validas}{marca}")

    print()
    com_defeito = [c for c, v in por_caso.items() if v["acertos"] < v["validas"]]
    tot_ok = sum(v["acertos"] for v in por_caso.values())
    tot_val = sum(v["validas"] for v in por_caso.values())
    print(f"--- {modelo} ---")
    print(f"  agregado:            {tot_ok}/{tot_val} "
          f"({tot_ok / tot_val * 100:.1f}%)" if tot_val else "  sem amostra valida")
    print(f"  casos com defeito:   {len(com_defeito)}/{len(CRITICOS)}")
    if com_defeito:
        for c in com_defeito:
            v = por_caso[c]
            taxa = (v["validas"] - v["acertos"]) / v["validas"] * 100
            print(f"      {c:<28} {v['acertos']}/{v['validas']} "
                  f"({taxa:.0f}% de falha, {v['categoria']})")
    if erros:
        print(f"  erros de infra:      {erros} (fora do denominador)")

    seguro = re.sub(r"[^A-Za-z0-9_-]", "_", rotulo)
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f"reamostra_criticos_{seguro}_{int(time.time())}.json"
    out.write_text(json.dumps({
        "modelo": modelo, "n": n, "casos": CRITICOS,
        "agregado_ok": tot_ok, "agregado_total": tot_val,
        "casos_com_defeito": com_defeito, "por_caso": por_caso,
        "erros_infra": erros, "registros": registros,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nartefato: {out}")


if __name__ == "__main__":
    main()
