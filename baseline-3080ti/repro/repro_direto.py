import json, urllib.request

TOOL = {"type":"function","function":{"name":"dre","description":"Consulta o DRE consolidado",
    "parameters":{"type":"object","properties":{"escopo":{"type":"string"}},"required":["escopo"]}}}
MSG = [{"role":"user","content":"Qual foi o resultado do KCO em 2025? Use a ferramenta."}]

def direto(rot, extra=None):
    body = {"model":"qwen2.5:14b","messages":MSG,"stream":False,"tools":[TOOL]}
    if extra: body.update(extra)
    req = urllib.request.Request("http://100.88.95.78:11434/api/chat",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        b = json.load(r)
    m = b.get("message",{}); calls = m.get("tool_calls") or []
    txt = (m.get("content") or "").strip()[:60]
    print(f"  {rot:26} tool_calls={len(calls)} {'' if calls else repr(txt)}")

print("DIRETO NO OLLAMA (sem gateway), 6x:")
for i in range(6): direto(f"direto #{i+1}")
print("DIRETO com keep_alive=0 (descarrega entre chamadas), 4x:")
for i in range(4): direto(f"keep_alive=0 #{i+1}", {"keep_alive": 0})
