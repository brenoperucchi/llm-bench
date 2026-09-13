#!/usr/bin/env python3
"""A/B de tempo de carga de modelo entre dois stores em discos diferentes.

Motivacao: o store saiu de C: (SSD antigo) para E: (SSD novo, 2026-09-07) e a
primeira comparacao disponivel era n=1 de cada lado, com condicoes de cache
diferentes -- exatamente o tipo de par de numeros que este laboratorio ja foi
enganado tres vezes por acreditar.

Metodo: alternancia por repeticao, o mesmo padrao do bench_engine_ab.py deste
repo ("ordem alternada por repeticao: dilui deriva termica e de clock"). Cada
ciclo carrega o mesmo modelo nos dois discos, um logo apos o outro, e descarrega
entre as cargas (keep_alive=0). O primeiro ciclo e descartado como warmup.

RESSALVA que fica no proprio script: isto NAO mede leitura de disco a frio. O
cache de filesystem do Windows nao esta sob controle, e a maquina tem 64 GiB de
RAM contra modelos de 6-19 GB. O que o desenho garante e SIMETRIA: os dois
discos passam pelas mesmas condicoes, na mesma ordem, no mesmo intervalo. A
comparacao vale; o numero absoluto nao e "tempo de disco puro".

Uso: python3 disco_ab_load.py <n_ciclos> [modelo1 modelo2 ...]
"""
import json
import statistics
import sys
import time
import urllib.error
import urllib.request

DISCOS = {"E: (novo)": "http://127.0.0.1:11434",
          "C: (antigo)": "http://127.0.0.1:11436"}

MODELOS_PADRAO = ["qwen3.5:9b", "qwen3:14b", "gpt-oss:20b", "qwen3.8:27b"]


def _post(url, payload, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def descarregar(base, modelo):
    try:
        _post(f"{base}/api/generate", {"model": modelo, "keep_alive": 0}, timeout=120)
    except Exception:  # noqa: BLE001 - descarga best-effort
        pass


def carregar(base, modelo):
    """Devolve load_duration em segundos, reportado pelo proprio servidor."""
    b = _post(f"{base}/api/generate", {
        "model": modelo, "prompt": "oi", "stream": False, "think": False,
        "options": {"num_predict": 1, "temperature": 0}})
    return b.get("load_duration", 0) / 1e9


def main():
    n_ciclos = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    modelos = sys.argv[2:] or MODELOS_PADRAO

    print(f"ciclos={n_ciclos} (1o descartado como warmup)  modelos={len(modelos)}")
    print("alternancia por repeticao; descarrega entre cargas\n")

    dados = {d: {m: [] for m in modelos} for d in DISCOS}
    falhas = 0

    for ciclo in range(n_ciclos + 1):
        tag = "warmup" if ciclo == 0 else f"ciclo{ciclo}"
        for modelo in modelos:
            linha = [f"  {tag:<7} {modelo:<14}"]
            for disco, base in DISCOS.items():
                descarregar(base, modelo)
                time.sleep(1)
                try:
                    s = carregar(base, modelo)
                except Exception as e:  # noqa: BLE001 - erro vira dado, nao crash
                    falhas += 1
                    linha.append(f"{disco}=ERRO({type(e).__name__})")
                    continue
                if ciclo > 0:
                    dados[disco][modelo].append(s)
                linha.append(f"{disco}={s:6.2f}s")
                descarregar(base, modelo)
                time.sleep(1)
            print("  ".join(linha))

    print(f"\n{'modelo':<14} {'C: (antigo)':>13} {'E: (novo)':>13} {'diferenca':>12}")
    print("-" * 56)
    deltas = []
    for modelo in modelos:
        c = dados["C: (antigo)"][modelo]
        e = dados["E: (novo)"][modelo]
        if not c or not e:
            print(f"{modelo:<14} {'sem dado':>13}")
            continue
        mc, me = statistics.median(c), statistics.median(e)
        pct = (me - mc) / mc * 100
        deltas.append(pct)
        print(f"{modelo:<14} {mc:12.2f}s {me:12.2f}s {pct:+11.1f}%")

    if deltas:
        print("-" * 56)
        print(f"{'mediana':<14} {'':>13} {'':>13} {statistics.median(deltas):+11.1f}%")
        print("\n(negativo = E: mais rapido; positivo = E: mais lento)")
    if falhas:
        print(f"\nfalhas descartadas: {falhas}")
    print("\nRessalva: cache de filesystem nao controlado. O desenho garante")
    print("simetria entre os discos, nao leitura a frio de disco puro.")


if __name__ == "__main__":
    main()
