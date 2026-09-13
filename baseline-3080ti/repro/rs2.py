import json, urllib.request, sys, time
sys.path.insert(0, "/home/brenoperucchi/Devs/llm-gateway/src")
from llm_gateway.profiles import BACKTEST_ANALYSIS as B

TEXTO = ("Comparacao de motores, 31 cestas, 1 noite.\n"
         "3tf_baseline: liquido -R$ 1.160.\nmn1_v2: liquido +R$ 30.\nlegacy: liquido -R$ 290.\n"
         "Mercado FECHADO na medicao. Delta pareado 3tf-mn1: -R$ 1.190 (desvio R$ 980, n=1).")

def roda(modelo, extra, n=8):
    ok = 0; conf_ok = 0; lat = []; erro = None
    for _ in range(n):
        body = {"model": modelo, "stream": False, "format": B.output_schema,
                "messages": [{"role":"system","content":B.system_prompt},
                             {"role":"user","content":TEXTO}],
                "options": {"num_predict": B.max_output_tokens}, **extra}
        req = urllib.request.Request("http://100.88.95.78:11434/api/chat",
            data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
        t = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=300) as r: b = json.load(r)
            lat.append((time.monotonic()-t)*1000)
            c = (b.get("message",{}).get("content") or "").strip()
            d = json.loads(c)
            ok += 1
            # mn1_v2 e o unico positivo: confidence deve ser baixa (n=1, desvio>delta)
            if d.get("confidence") == "baixa": conf_ok += 1
        except Exception as e:
            erro = str(e)[:60]
    lat.sort()
    med = lat[len(lat)//2] if lat else 0
    print(f"  {modelo:14} JSON valido {ok}/{n}   confidence correta {conf_ok}/{n}   mediana {med:.0f}ms"
          + (f"   erro: {erro}" if erro else ""))

roda("qwen2.5:14b", {})
roda("qwen3:14b", {"think": False})
