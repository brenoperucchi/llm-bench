import json, urllib.request

TOOL = {"type":"function","function":{
    "name":"dre","description":"Consulta o DRE consolidado de um escopo e periodo",
    "parameters":{"type":"object","properties":{
        "escopo":{"type":"string"},"de":{"type":"string"},"ate":{"type":"string"}},
        "required":["escopo"]}}}

def call(n):
    body = {"project":"repro-toolcall","messages":[
        {"role":"user","content":"Qual foi o resultado do KCO em 2026? Use a ferramenta dre."}],
        "tools":[TOOL]}
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/local",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        b = json.load(r)
    m = b["message"]
    calls = m.get("tool_calls") or []
    content = (m.get("content") or "").strip()
    marca = "OK " if calls else "ANOMALA"
    print(f"  {n}. {marca} tool_calls={len(calls)} finish={b['finish_reason']:10} "
          f"{b['latency_ms']:7.0f}ms chars={len(content):4}")
    if not calls and content:
        print(f"       -> {content[:150]!r}")

for i in range(1, 7):
    call(i)
