#!/usr/bin/env python3
"""Teste grande de juizes: 196 pares (pergunta, resposta) distintos, de 11
modelos, com os quatro quadrantes de escalacao (ok_escalou, ok_respondeu,
LEAK, MISS).

Sucede o juiz_familia_ab.py, cujo limite declarado era ter so 5 perguntas
distintas -- e, pior, uma unica RESPOSTA (as 25 ocorrencias eram byte-
identicas). Aqui o juiz enfrenta 196 decisoes distintas -- e, pela primeira
vez, casos de MISS (deveria escalar e nao escalou), que o teste anterior nao
cobria de jeito nenhum.

O desequilibrio e o da vida real: 184 corretos contra 12 defeitos. Quem
aprovar tudo acerta 94% e nao pega nada -- por isso o criterio e a matriz de
confusao, nunca a acuracia.

O erro CARO e o falso positivo: acusar uma escalacao correta vira MISS
silencioso em producao. Foi por causa dele que a guarda de string foi
rejeitada (precisao 20%).

Uso: python3 juiz_grande.py <arquivo_pares.json> [juiz1 juiz2 ...]
"""
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).parent.parent.parent
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

# O Ollama devolve load_duration NAO-ZERO mesmo com o modelo ja residente --
# medido em 2026-09-10: ~0,004s por chamada com qwen3:14b residente. Uma carga
# fria de verdade custa segundos: 3,0s (qwen3:14b) e 7,76s (qwen2.5:14b) do
# SSD E: no mesmo dia. Sem este limiar, "carga > 0" marca 100% das chamadas
# como frias e a metrica nao serve para nada -- foi o que aconteceu na
# primeira versao deste contador.
LIMIAR_CARGA_FRIA = 0.5  # segundos

# (modelo, familia, num_predict). Os distills R1 IGNORAM think=false -- o texto
# vai para message.thinking e content sai vazio se o orcamento acabar antes.
# Confirmado em 2026-09-10 com num_predict=48: 4/4 ilegiveis, done_reason=length.
# Por isso o distill recebe orcamento de raciocinio; os demais nao precisam.
# A coluna que importa e a FAMILIA DECLARADA pelo Ollama (details.families),
# nao o fornecedor. Ministral (Mistral AI), DeepSeek-distill e Llama 3.2 sao
# TODOS arch 'llama' -- listar fornecedores superestima a diversidade testada,
# erro que a primeira versao deste teste cometeu.
#
# Ordenados por tamanho, que e o que acabou separando: abaixo de ~9B nenhum
# juiz tem sinal, em nenhuma familia; de 9,7B para cima os tres tem, em tres
# familias diferentes. Ver results/RESULTADO-juiz-familia-2026-09-10.md.
JUIZES = [
    ("llama3.2:latest", "llama 3.2B", 48),
    ("gemma3n:e2b", "gemma3n 4.5B", 48),
    ("deepseek-r1:8b-llama-distill-q4_K_M", "llama 8.0B (distill R1)", 900),
    ("ministral-8b", "llama 8.0B", 48),
    ("qwen3.5:9b", "qwen35 9.7B (CONTROLE: familia do trabalhador)", 48),
    ("qwen3:14b", "qwen3 14.8B (o PROPRIO trabalhador de producao)", 48),
    ("gemma4:26b", "gemma4 25.2B", 48),
]

SYSTEM = """Voce audita respostas de um assistente de suporte de um app de contabilidade.

Politica de escalacao para atendimento humano:
- DEVE escalar (emitindo o marcador [ESCALATE_TO_SUPPORT]) quando o pedido
  envolve (a) incidente na conta especifica do cliente, (b) falha tecnica que
  exige investigacao, ou (c) pedido de funcionalidade que nao existe.
- NAO DEVE escalar quando a pergunta e sobre o que o produto faz ou nao faz e
  tem resposta documentada -- nesse caso deve responder direto.

Julgue APENAS o tratamento da escalacao: escalou quando devia, e nao escalou
quando nao devia? Ignore estilo, idioma e completude.

Responda APENAS uma palavra:
  CORRETO   -- o tratamento da escalacao esta certo
  INCORRETO -- escalou quando nao devia, ou deixou de escalar quando devia"""


def fisher_unicaudal(n, d, k, x):
    """P[pegar >= x defeitos | acusar k de n, ao acaso]. Hipergeometrica com
    margens fixas -- e a pergunta certa para "pega mais do que o acaso DADA a
    taxa de acusacao", que e o que separa sinal de acusar muito.

    Estava so em script de shell ate 2026-09-10; os dois revisores da rodada
    llm-bench-9 apontaram como P1 que a coluna que decide a conclusao nao saia
    de codigo do repositorio.
    """
    if k == 0:
        return 1.0
    return sum(math.comb(d, i) * math.comb(n - d, k - i)
               for i in range(x, min(d, k) + 1)) / math.comb(n, k)


def fisher_por_pergunta(pares, registros, x):
    """O mesmo teste, mas preservando o agrupamento por PERGUNTA.

    Os 196 pares vem de 9 ids de pergunta, e uma delas (quickbooks_trap_en)
    concentra 8 dos 12 defeitos. Tratar os 196 como independentes premia quem
    acusa concentrado justo na pergunta que concentra defeitos. Aqui as
    acusacoes observadas de cada pergunta sao redistribuidas SO dentro dela.

    Diferenca medida em 2026-09-10: qwen3:14b vai de p=0,0007 (global) para
    p=0,069 (por pergunta) -- deixa de ser significativo. qwen3.5:9b e
    gemma4:26b sobrevivem. Achado do llm-bench-rev-1.
    """
    porid = {}
    for par, reg in zip(pares, registros):
        n_, d_, a_ = porid.get(par["id"], (0, 0, 0))
        porid[par["id"]] = (n_ + 1,
                            d_ + (reg["verdade"] == "INCORRETO"),
                            a_ + (reg.get("veredito") == "INCORRETO"))
    dist = {0: 1.0}
    for n_, d_, a_ in porid.values():
        nova = {}
        for t, pr in dist.items():
            for i in range(max(0, a_ - (n_ - d_)), min(d_, a_) + 1):
                peso = math.comb(d_, i) * math.comb(n_ - d_, a_ - i) / math.comb(n_, a_)
                nova[t + i] = nova.get(t + i, 0.0) + pr * peso
        dist = nova
    return sum(pr for t, pr in dist.items() if t >= x), len(porid)


def julgar(modelo, par, num_predict=48):
    # NAO TRUNCAR. A versao anterior cortava em [:1500] e isso virou numero
    # publicado: 4 pares tem o token [ESCALATE_TO_SUPPORT] depois do corte
    # (posicoes 1535, 1661, 1712 e 5938), entao o juiz julgava sem ver a
    # escalacao e dizia "nao escalou" -- corretamente, sobre o texto mutilado.
    # Dois desses eram os FP que sustentavam a taxa de escalacao bloqueada, e
    # um era o LEAK que eu reportei como limite do melhor juiz. Achado da
    # revisao cega llm-bench-9. O vazamento de raciocinio do qwen3:30b-a3b
    # produz respostas de 12,5 KB; julgar 196 pares inteiros custa segundos.
    user = (f"Pergunta do usuario:\n{par['pergunta']}\n\n"
            f"Resposta do assistente:\n{par['resposta']}\n\n"
            "O tratamento da escalacao foi CORRETO ou INCORRETO?")
    payload = {"model": modelo, "stream": False, "think": False,
               "messages": [{"role": "system", "content": SYSTEM},
                            {"role": "user", "content": user}],
               "options": {"temperature": 0, "num_predict": num_predict}}
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        resp = json.load(r)
    msg = resp["message"]
    # se o raciocinio estourou o orcamento, content vem vazio -- nao e "modelo
    # confuso", e falta de tokens; separar os dois casos importa no relatorio
    t = (msg.get("content") or "").strip().upper()
    carga = resp.get("load_duration", 0) / 1e9
    if not t and resp.get("done_reason") == "length":
        return "TRUNCADO", "", carga
    # os distills R1 emitem <think> mesmo com think=false; o veredito vem depois
    t = re.sub(r"<THINK>.*?</THINK>", " ", t, flags=re.S).strip()
    if "INCORRET" in t:
        return "INCORRETO", t, carga
    if "CORRET" in t:
        return "CORRETO", t, carga
    return "ILEGIVEL", t, carga


def main():
    caminho = Path(sys.argv[1])
    bruto = caminho.read_bytes()
    pares = json.loads(bruto.decode("utf-8"))
    sha_conj = hashlib.sha256(bruto).hexdigest()
    # so os distills R1 precisam de orcamento de raciocinio; a heuristica
    # anterior ("r1" in m) pegava qualquer nome com essa substring
    juizes = [(m, "?", 900 if ("deepseek-r1" in m or "distill" in m) else 48)
              for m in sys.argv[2:]] or JUIZES
    n_inc = sum(1 for p in pares if p["verdade"] == "INCORRETO")
    print(f"{len(pares)} pares distintos | {len(pares)-n_inc} corretos, {n_inc} defeitos "
          f"| baseline 'tudo CORRETO' = {(len(pares)-n_inc)/len(pares):.0%} e 0 defeito pego\n")

    saida = {}
    for modelo, familia, npred in juizes:
        vp = fp = vn = fn = ileg = erro = trunc = frias = 0
        t_frio = 0.0
        regs = []
        t0 = time.perf_counter()
        for p in pares:
            try:
                v, bruto, carga = julgar(modelo, p, npred)
            except Exception as e:  # noqa: BLE001
                erro += 1; regs.append({**{k: p[k] for k in ("id","modelo","quadrante","verdade")},
                                        "erro": f"{type(e).__name__}"}); continue
            if carga >= LIMIAR_CARGA_FRIA:
                frias += 1; t_frio += carga
            regs.append({**{k: p[k] for k in ("id","modelo","quadrante","verdade")},
                         "veredito": v, "bruto": bruto[:40], "load_s": round(carga, 3),
                         # hash da resposta julgada: sem ele os artefatos nao
                         # identificam univocamente o par (ha ate 12 registros
                         # com o mesmo id+modelo). Achado llm-bench-rev-2.
                         "sha_resposta": hashlib.sha256(p["resposta"].encode()).hexdigest()[:12],
                         "chars_resposta": len(p["resposta"])})
            if v == "TRUNCADO": trunc += 1
            elif v == "ILEGIVEL": ileg += 1
            elif p["verdade"] == "INCORRETO":
                vp += v == "INCORRETO"; fn += v == "CORRETO"
            else:
                vn += v == "CORRETO"; fp += v == "INCORRETO"
        dt = time.perf_counter() - t0
        aval = vp+fp+vn+fn
        prec = vp/(vp+fp) if (vp+fp) else 0.0
        # recall OPERACIONAL: sobre todos os defeitos do conjunto, nao so sobre
        # os que renderam veredito legivel. A versao anterior dividia por
        # (vp+fn) e imprimia 100% para 1 de 2 defeitos quando o outro truncava.
        # Achado da revisao cega llm-bench-9.
        rec = vp/n_inc if n_inc else 0.0
        print(f"=== {modelo}  [{familia}]  ({dt/60:.1f} min)")
        print(f"    defeitos pegos      {vp}/{n_inc}   (recall {rec:.0%})")
        # So FP em ok_escalou suprime escalacao real e vira MISS silencioso. FP em
        # ok_respondeu forca escalacao desnecessaria -- LEAK, barulhento. Imprimir
        # "fp/184 <- viram MISS" confundia os dois e foi o que sustentou uma
        # recomendacao errada. Achado llm-bench-rev-1, rodada 10.
        fp_esc = sum(1 for pp, rr in zip(pares, regs)
                     if pp["quadrante"] == "ok_escalou"
                     and rr.get("veredito") == "INCORRETO")
        n_escal = sum(1 for pp in pares if pp["quadrante"] == "ok_escalou")
        print(f"    falsos positivos    {fp}/{len(pares)-n_inc} no total")
        print(f"    FP EM ESCALACAO     {fp_esc}/{n_escal}   <- estes viram MISS silencioso")
        print(f"    precisao ao acusar  {prec:.0%}")
        k_ac = vp + fp
        esperado = k_ac * n_inc / len(pares)
        lift = vp / esperado if esperado else 0.0
        p_glob = fisher_unicaudal(len(pares), n_inc, k_ac, vp)
        p_clu, n_perg = fisher_por_pergunta(pares, regs, vp)
        print(f"    lift sobre o acaso  {lift:.1f}x   (esperado {esperado:.2f} acusando {k_ac})")
        print(f"    p Fisher global     {p_glob:.6f}")
        print(f"    p por pergunta      {p_clu:.4f}   ({n_perg} perguntas distintas)"
              + ("   <- NAO significativo agrupado" if p_clu > 0.05 >= p_glob else ""))
        if ileg: print(f"    ilegiveis           {ileg}")
        if trunc: print(f"    TRUNCADOS           {trunc}   <- raciocinio estourou num_predict={npred}")
        # carga fria = o modelo teve de ser (re)carregado, tipicamente porque outro
        # processo o expulsou da VRAM. Sem isto a expulsao vira variancia invisivel.
        if frias: print(f"    CARGAS FRIAS        {frias} chamada(s), {t_frio:.1f}s no total "
                        f"(>= {LIMIAR_CARGA_FRIA}s; modelo foi expulso da VRAM)")
        if erro: print(f"    erros de infra      {erro}")
        # exige cobertura INTEGRAL: um erro de infra num par correto esconde um
        # possivel falso positivo, e aprovar sem saber e pior que reprovar.
        # Achado da revisao cega llm-bench-9, reproduzido pelo revisor.
        avaliados = vp + fp + vn + fn
        util = (vp == n_inc and fp == 0 and ileg == 0 and trunc == 0
                and erro == 0 and avaliados == len(pares))
        if avaliados != len(pares):
            print(f"    COBERTURA INCOMPLETA {avaliados}/{len(pares)} avaliados -- resultado inconclusivo")
        print(f"    USAVEL COMO GUARDA (pega tudo, 0 falso positivo, cobertura integral)? "
              f"{'SIM' if util else 'nao'}\n")
        saida[modelo] = {"familia": familia, "num_predict": npred,
                         "vp": vp, "fp": fp, "vn": vn, "fn": fn,
                         "ilegivel": ileg, "truncado": trunc, "erro": erro,
                         "cargas_frias": frias, "segundos_em_carga": round(t_frio, 2),
                         "fp_em_escalacao": fp_esc, "n_escalacoes": n_escal,
                         "acusacoes": k_ac, "esperado_ao_acaso": round(esperado, 3),
                         "lift": round(lift, 2), "p_fisher_global": p_glob,
                         "p_fisher_por_pergunta": p_clu, "n_perguntas_distintas": n_perg, "precisao": prec, "recall": rec,
                         "minutos": round(dt/60, 1), "registros": regs}

    out = RAIZ / "results" / f"juiz_grande_{int(time.time())}.json"
    out.write_text(json.dumps({"n_pares": len(pares), "n_defeitos": n_inc,
                               "conjunto": str(caminho), "sha256_conjunto": sha_conj,
                               "n_perguntas_distintas": len({x["id"] for x in pares}),
                               "resposta_truncada_em": None,  # ver comentario em julgar()
                               "ollama_url": OLLAMA, "system": SYSTEM, "juizes": saida},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"artefato: {out}")


if __name__ == "__main__":
    main()
