#!/usr/bin/env python3
"""Mesmo caso, mesmos seeds, DUAS instancias com config diferente.

Fecha a pergunta da regressao levantada em RESULTADO-reamostra-qwen3-14b:
na Fase 0 (04/09, config 1 = NUM_PARALLEL/MAX_LOADED = 1/1) o caso
quickbooks_trap_en passava com seed=42; hoje, em producao (config 4 +
NUM_PARALLEL=2), falha. Duas explicacoes concorrem: (a) a config mudou a
trajetoria numerica; (b) o modo de falha e de alta frequencia e engoliu esse
seed de qualquer jeito.

Grava PROVENIENCIA (achado llm-bench-8: os testes anteriores eram
irreconferiveis porque o artefato nao dizia contra qual servidor rodaram).

Uso: python3 seed_ab_instancia.py [seeds...]
"""
import importlib.util, json, os, re, sys, time, urllib.request
from pathlib import Path

RAIZ = Path(__file__).parent.parent.parent
CASO = "quickbooks_trap_en"
INSTANCIAS = {
    "producao (NP=2, MAX=2)": "http://127.0.0.1:11434",
    "isolada (NP=1, MAX=1)": "http://127.0.0.1:11437",
}

def harness():
    spec = importlib.util.spec_from_file_location("run_chat", RAIZ / "run_chat.py")
    rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)
    return rc

def get(url, path):
    with urllib.request.urlopen(f"{url}{path}", timeout=20) as r:
        return json.load(r)

def show(url, modelo):
    req = urllib.request.Request(f"{url}/api/show", data=json.dumps({"model": modelo}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def main():
    seeds = [int(x) for x in sys.argv[1:]] or [42, 7, 1, 999, 1017]
    rc = harness(); rc.THINK = False
    sp = rc.load("prompts/system_prompt.txt")
    caso = {c["id"]: c for c in json.loads(rc.load("goldset_chat.json"))}[CASO]

    proveniencia = {}
    for nome, url in INSTANCIAS.items():
        det = show(url, "qwen3:14b").get("details", {})
        proveniencia[nome] = {
            "ollama_url": url,
            "version": get(url, "/api/version").get("version"),
            "quantization": det.get("quantization_level"),
            "parameter_size": det.get("parameter_size"),
        }
        print(f"{nome:<24} {url}  ollama={proveniencia[nome]['version']}  "
              f"quant={proveniencia[nome]['quantization']}")
    print(f"\ncaso={CASO}  system_prompt sha256[:12]={__import__('hashlib').sha256(sp.encode()).hexdigest()[:12]}")
    print(f"seeds={seeds}\n")

    registros = []
    print(f"{'seed':>6}  " + "  ".join(f"{n:<24}" for n in INSTANCIAS))
    for seed in seeds:
        linha, cells = f"{seed:>6}  ", []
        for nome, url in INSTANCIAS.items():
            rc.OPTIONS["seed"] = seed
            os.environ["OLLAMA_URL"] = url
            rc.OLLAMA = url  # o modulo le a global em tempo de chamada
            try:
                texto, met = rc.chat("qwen3:14b", sp, caso["prompt"])
                a = rc.run_auto(texto, caso["auto"], caso["lang"])
                ok = a["auto_score"] == 1.0
                cells.append(f"{'PASSA' if ok else 'falha':<8} score={a['auto_score']:.2f}      ")
                registros.append({"seed": seed, "instancia": nome, "ollama_url": url,
                                  "ok": ok, "auto": a, "resposta": texto, "metrica": met})
            except Exception as e:  # noqa: BLE001
                cells.append(f"{'ERRO':<8} {type(e).__name__}   ")
                registros.append({"seed": seed, "instancia": nome, "ollama_url": url,
                                  "erro": f"{type(e).__name__}: {e}"})
        print(linha + "  ".join(cells))

    print()
    for nome in INSTANCIAS:
        rs = [r for r in registros if r["instancia"] == nome and "ok" in r]
        print(f"  {nome:<24} {sum(r['ok'] for r in rs)}/{len(rs)} passaram")

    out = RAIZ / "results" / f"seed_ab_instancia_{int(time.time())}.json"
    out.write_text(json.dumps({"caso": CASO, "seeds": seeds,
                               "proveniencia": proveniencia, "registros": registros},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nartefato (com proveniencia): {out}")

if __name__ == "__main__":
    main()
