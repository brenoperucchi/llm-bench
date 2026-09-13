import json, urllib.request, sys
sys.path.insert(0, "/home/brenoperucchi/Devs/llm-gateway/src")
from llm_gateway.profiles import LOCAL_CHAT

TOOL = {"type":"function","function":{"name":"dre","description":"Consulta o DRE consolidado",
    "parameters":{"type":"object","properties":{"escopo":{"type":"string"}},"required":["escopo"]}}}
MSGS = [{"role":"system","content":LOCAL_CHAT.system_prompt},
        {"role":"user","content":"Qual foi o resultado do KCO em 2025? Use a ferramenta."}]

for modelo, extra in [("qwen2.5:14b", {}), ("qwen3:14b", {"think": False}), ("llama3.2:latest", {})]:
    ok = 0; n = 6; amostra = None
    for _ in range(n):
        body = {"model":modelo,"messages":MSGS,"stream":False,"tools":[TOOL], **extra}
        req = urllib.request.Request("http://100.88.95.78:11434/api/chat",
            data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                b = json.load(r)
            m = b.get("message",{})
            if (m.get("tool_calls") or []): ok += 1
            elif amostra is None: amostra = (m.get("content") or "").strip()[:60]
        except Exception as e:
            if amostra is None: amostra = f"ERRO {e}"
    print(f"  {modelo:18} chamou a ferramenta: {ok}/{n}" + (f"   falha: {amostra!r}" if ok < n else ""))
