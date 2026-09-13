import json, urllib.request, sys, time
sys.path.insert(0, "/home/brenoperucchi/Devs/llm-gateway/src")
from llm_gateway.profiles import LOCAL_CHAT

TOOL = {"type":"function","function":{"name":"dre","description":"Consulta o DRE consolidado",
    "parameters":{"type":"object","properties":{"escopo":{"type":"string"}},"required":["escopo"]}}}
PERGUNTAS = [
    "Qual foi o resultado do KCO em 2025? Use a ferramenta.",
    "Me diga a receita líquida do grupo KSH.",
    "Qual o resultado consolidado? Consulte.",
]

for modelo, extra in [("qwen2.5:14b", {}), ("qwen3:14b", {"think": False})]:
    ok = 0; n = 0; lat = []
    for p in PERGUNTAS:
        for _ in range(4):
            msgs = [{"role":"system","content":LOCAL_CHAT.system_prompt},{"role":"user","content":p}]
            body = {"model":modelo,"messages":msgs,"stream":False,"tools":[TOOL], **extra}
            req = urllib.request.Request("http://100.88.95.78:11434/api/chat",
                data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
            t=time.monotonic()
            with urllib.request.urlopen(req, timeout=300) as r: b = json.load(r)
            lat.append((time.monotonic()-t)*1000); n += 1
            if (b.get("message",{}).get("tool_calls") or []): ok += 1
    lat.sort()
    print(f"  {modelo:14} {ok}/{n} chamadas com ferramenta ({100*ok//n}%)  mediana {lat[len(lat)//2]:.0f}ms")
