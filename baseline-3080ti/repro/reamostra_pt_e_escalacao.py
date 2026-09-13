#!/usr/bin/env python3
"""Da taxa a dois achados n=1 da rodada de 2026-09-10 com os checks novos.

ACHADO 1 -- PT->EN no modelo PADRAO DE PRODUCAO. O qwen3:14b respondeu tres
perguntas em portugues inteiramente em ingles (howto_invoice_pt,
howto_schedule_c_pt, howto_import_csv_pt). Nao foi mistura parcial: a resposta
inteira no idioma errado. O item estava na lista de abertos como "padrao PT->EN
nao investigado" desde a Fase 0.

ACHADO 2 -- FALHA SILENCIOSA DE ESCALACAO no qwen3.5:9b, o SEGUNDO RESIDENTE.
Em escalate_double_charge_en ele escreveu "I'd like to forward your question to
our support team... I'll create a support ticket for you" e NAO emitiu
[ESCALATE_TO_SUPPORT]. Resposta completa, 672 chars, nao foi corte. O regex de
producao nao dispara: o cliente e informado de que um ticket sera criado e
nenhum ticket existe. No corpus historico e 1 em 64 escalacoes reais -- todas
as outras 63 de 11 modelos emitiram o token.

Os dois sao n=1 sobre temperature=0.7. Este script da taxa, variando a seed na
mesma progressao da Fase 7 (1000 + i*17), e persiste toda resposta.

Os dois modelos somam 19,66 GiB e cabem residentes juntos: nao expulsa producao
e nao precisa de janela combinada com o llm-exec.
"""
import importlib.util
import json
import time
from pathlib import Path

RAIZ = Path(__file__).parent.parent.parent
N = 5

# (modelo, casos, o que se quer medir)
PLANO = [
    ("qwen3:14b", ["howto_invoice_pt", "howto_schedule_c_pt", "howto_import_csv_pt",
                   "plaid_trap_pt", "payroll_trap_pt", "escalate_stripe_broken_pt",
                   "escalate_wrong_numbers_pt", "greet_pt", "pricing_pt"], "idioma"),
    ("qwen3.5:9b", ["escalate_double_charge_en", "escalate_stripe_broken_pt",
                    "escalate_feature_en", "escalate_wrong_numbers_pt"], "escalacao"),
]

# "promete escalar" -- o texto que o cliente le como "vou abrir um chamado".
# Sem token, isso e a falha silenciosa: promessa feita, nada disparado.
import re
PROMETE = re.compile(
    r"forward your question|support team so they can investigate|create a support ticket|"
    r"encaminhar (sua|a) (pergunta|questao|d[uú]vida)|equipe de suporte|abrir um chamado",
    re.I)


def main():
    spec = importlib.util.spec_from_file_location("rc", RAIZ / "run_chat.py")
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    rc.THINK = False  # convencao do laboratorio desde a Fase 0
    sysp = rc.load("prompts/system_prompt.txt")
    gs = {c["id"]: c for c in json.loads(rc.load("goldset_chat.json"))}

    registros = []
    for modelo, casos, foco in PLANO:
        print(f"=== {modelo}  ({foco}, n={N} por caso)")
        for cid in casos:
            caso = gs[cid]
            linha = []
            for i in range(N):
                rc.OPTIONS["seed"] = 1000 + i * 17
                try:
                    texto, metrica = rc.chat(modelo, sysp, caso["prompt"])
                    auto = rc.run_auto(texto, caso["auto"], caso["lang"])
                    erro = None
                except Exception as e:  # noqa: BLE001
                    texto, metrica, auto, erro = "", {}, {}, f"{type(e).__name__}: {e}"
                tem_token = "[ESCALATE_TO_SUPPORT]" in texto
                registros.append({
                    "modelo": modelo, "id": cid, "foco": foco,
                    "seed": rc.OPTIONS["seed"], "lang_esperado": caso["lang"],
                    "lang_detectado": auto.get("lang_detected"),
                    "lang_ok": auto.get("lang_ok"),
                    "escalation_ok": auto.get("escalation_ok"),
                    "deve_escalar": caso["auto"]["expect_escalation"],
                    "tem_token": tem_token,
                    "promete_escalar": bool(PROMETE.search(texto)),
                    # a falha silenciosa: promete ao cliente e nao dispara nada
                    "falha_silenciosa": (caso["auto"]["expect_escalation"]
                                         and not tem_token and bool(PROMETE.search(texto))),
                    "auto_score": auto.get("auto_score"), "erro": erro,
                    "chars": len(texto), "resposta": texto,
                })
                linha.append("." if erro is None and auto.get("auto_score") == 1.0
                             else ("E" if erro else "x"))
            print(f"    {cid:28s} {''.join(linha)}")
        print()

    out = RAIZ / "results" / f"reamostra_pt_escalacao_{int(time.time())}.json"
    out.write_text(json.dumps({
        "n_por_caso": N, "seeds": [1000 + i * 17 for i in range(N)],
        "options": rc.OPTIONS, "think": rc.THINK,
        "plano": [{"modelo": m, "casos": c, "foco": f} for m, c, f in PLANO],
        "registros": registros,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"artefato: {out}")


if __name__ == "__main__":
    main()
