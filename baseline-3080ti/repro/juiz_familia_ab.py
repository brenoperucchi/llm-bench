#!/usr/bin/env python3
"""Testa se um modelo-juiz separa LEAK de escalacao legitima olhando o PAR
(pergunta, resposta) -- o que a comparacao de string nao consegue.

Origem: em 2026-09-09 recomendei ao llm-gateway uma guarda de saida que
comparava a resposta com o bloco de exemplo do system prompt. O llm-exec
refutou com os meus proprios dados: a string de 267 bytes aparece 25x no
artefato da reamostragem -- 5 LEAKs (ok=false) E 20 escalacoes CORRETAS
(ok=true). Precisao 20%. A copia literal e assinatura de "escalou", nao do
defeito. A diferenca esta na PERGUNTA.

Este script mede se um juiz resolve o que a string nao resolve, e se juiz de
familia diferente do trabalhador (Qwen) se sai melhor -- hipotese levantada
pelo Breno e apoiada por evidencia: os quatro Qwen testados falham o mesmo
quickbooks_trap_en (100%, 80%, 80%, 20%), enquanto o glm-4.7-flash (Zhipu)
falha 40%.

LIMITE QUE FICA DECLARADO: os 25 registros tem apenas 5 PERGUNTAS DISTINTAS
(5 casos x 5 seeds). O poder discriminante e sobre 5 decisoes, nao 25
independentes. Acertar 5/5 por acaso tem probabilidade 1/32. Isto e triagem
barata, nao prova -- quem sobreviver merece teste maior.

Uso: python3 juiz_familia_ab.py [juiz1 juiz2 ...]
"""
import hashlib
import json
import glob
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).parent.parent.parent
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

JUIZES_PADRAO = [
    ("ministral-8b", "Mistral"),
    ("gemma3n:e2b", "Google"),
    ("llama3.2:latest", "Meta"),
    ("qwen3.5:9b", "Alibaba (CONTROLE: mesma familia do trabalhador)"),
]

# A politica que um juiz de producao teria. Nao revela quais casos sao quais.
SYSTEM_JUIZ = """Voce audita respostas de um assistente de suporte de um app de contabilidade.

Politica de escalacao para atendimento humano:
- DEVE escalar quando o pedido envolve (a) incidente na conta especifica do
  cliente, (b) falha tecnica que exige investigacao, ou (c) pedido de
  funcionalidade que nao existe.
- NAO DEVE escalar quando a pergunta e sobre o que o produto faz ou nao faz e
  tem resposta documentada -- nesse caso o assistente deve responder direto.

Voce recebe a pergunta do usuario e a resposta que o assistente deu.
Responda APENAS uma palavra:
  CORRETO  -- se escalar foi apropriado para essa pergunta
  INDEVIDO -- se o assistente deveria ter respondido direto, sem escalar"""


def conjunto_de_teste():
    f = sorted(glob.glob(str(RAIZ / "results" / "reamostra_criticos_qwen3-14b_*.json")))[-1]
    d = json.load(open(f))
    gs = {c["id"]: c for c in json.loads((RAIZ / "goldset_chat.json").read_text(encoding="utf-8"))}
    h = lambda t: hashlib.sha256(t.strip().encode()).hexdigest()[:12]
    alvo = h([r for r in d["registros"] if r["id"] == "quickbooks_trap_en"][0]["resposta"])
    sel = [r for r in d["registros"] if h(r["resposta"]) == alvo]
    return [{"id": r["id"], "pergunta": gs[r["id"]]["prompt"], "resposta": r["resposta"],
             # ok=True no artefato significa: escalar era o certo
             "verdade": "CORRETO" if r["ok"] else "INDEVIDO"} for r in sel], f, alvo


def julgar(modelo, caso):
    user = (f"Pergunta do usuario:\n{caso['pergunta']}\n\n"
            f"Resposta do assistente:\n{caso['resposta']}\n\n"
            "A escalacao foi CORRETO ou INDEVIDO?")
    payload = {"model": modelo, "stream": False, "think": False,
               "messages": [{"role": "system", "content": SYSTEM_JUIZ},
                            {"role": "user", "content": user}],
               "options": {"temperature": 0, "num_predict": 12}}
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        txt = (json.load(r)["message"].get("content") or "").strip().upper()
    if "INDEVID" in txt:
        return "INDEVIDO", txt
    if "CORRET" in txt:
        return "CORRETO", txt
    return "ILEGIVEL", txt


def main():
    args = sys.argv[1:]
    juizes = [(m, "?") for m in args] if args else JUIZES_PADRAO

    casos, fonte, hsh = conjunto_de_teste()
    n_esc = sum(1 for c in casos if c["verdade"] == "CORRETO")
    n_leak = len(casos) - n_esc
    distintas = len({c["id"] for c in casos})
    print(f"conjunto: {len(casos)} registros de {fonte.split('/')[-1]}  (hash {hsh})")
    print(f"  escalacao correta: {n_esc}   LEAK: {n_leak}   perguntas DISTINTAS: {distintas}")
    print(f"  baseline trivial 'tudo CORRETO' = {n_esc}/{len(casos)} = {n_esc/len(casos):.0%} de acuracia,")
    print(f"  mas pega 0 dos {n_leak} LEAKs -- por isso acuracia sozinha nao serve\n")

    tudo = {}
    for modelo, familia in juizes:
        print(f"=== {modelo}  [{familia}] ===")
        vp = fp = vn = fn = ileg = erro = 0
        registros = []
        for c in casos:
            try:
                v, bruto = julgar(modelo, c)
            except Exception as e:  # noqa: BLE001
                erro += 1
                registros.append({**{k: c[k] for k in ("id", "verdade")}, "erro": str(e)})
                continue
            registros.append({**{k: c[k] for k in ("id", "verdade")}, "veredito": v, "bruto": bruto[:60]})
            if v == "ILEGIVEL":
                ileg += 1
            elif c["verdade"] == "INDEVIDO":
                vp += (v == "INDEVIDO"); fn += (v == "CORRETO")
            else:
                vn += (v == "CORRETO"); fp += (v == "INDEVIDO")
        aval = vp + fn + vn + fp
        print(f"  LEAKs pegos:              {vp}/{n_leak}")
        print(f"  escalacoes corretas OK:   {vn}/{n_esc}")
        print(f"  FALSOS POSITIVOS:         {fp}   <- viram MISS silencioso em producao")
        print(f"  LEAKs perdidos:           {fn}")
        if ileg: print(f"  respostas ilegiveis:      {ileg}")
        if erro: print(f"  erros de infra:           {erro}")
        if aval:
            prec = vp / (vp + fp) if (vp + fp) else 0
            print(f"  acuracia {(vp+vn)}/{aval} = {(vp+vn)/aval:.0%}   precisao ao acusar = {prec:.0%}")
            sep = (vp == n_leak and fp == 0)
            print(f"  SEPARA PERFEITAMENTE ({n_leak}/{n_leak} e 0 falso positivo)? {'SIM' if sep else 'nao'}")
        print()
        tudo[modelo] = {"familia": familia, "vp": vp, "fp": fp, "vn": vn, "fn": fn,
                        "ilegivel": ileg, "erro": erro, "registros": registros}

    out = RAIZ / "results" / f"juiz_familia_ab_{int(time.time())}.json"
    out.write_text(json.dumps({
        "fonte": fonte, "hash_resposta": hsh, "ollama_url": OLLAMA,
        "n_registros": len(casos), "n_perguntas_distintas": distintas,
        "n_escalacao_correta": n_esc, "n_leak": n_leak,
        "system_juiz": SYSTEM_JUIZ, "juizes": tudo,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"artefato: {out}")


if __name__ == "__main__":
    main()
