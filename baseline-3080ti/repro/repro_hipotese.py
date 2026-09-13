import json, urllib.request

def tool(nome, desc):
    return {"type":"function","function":{"name":nome,"description":desc,
        "parameters":{"type":"object","properties":{"escopo":{"type":"string"}},"required":["escopo"]}}}

def call(t, pergunta, rot):
    body = {"project":"hip","messages":[{"role":"user","content":pergunta}],"tools":[t]}
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/local",
        data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        b = json.load(r)
    m = b["message"]; calls = m.get("tool_calls") or []
    nome = calls[0]["function"]["name"] if calls else "-"
    txt = (m.get("content") or "").strip()[:70]
    print(f"  {rot:34} tool_calls={len(calls)} name={nome!r:12} {'' if calls else repr(txt)}")

P = "Qual foi o resultado do KCO em 2025? Use a ferramenta."
print("A) descrição começa com verbo (como no caso original):")
for i in range(3): call(tool("dre","Consulta o DRE consolidado"), P, f"desc='Consulta o DRE...' #{i+1}")
print("B) MESMA ferramenta, descrição reescrita sem verbo inicial:")
for i in range(3): call(tool("dre","Demonstrativo de resultado por escopo"), P, f"desc='Demonstrativo...' #{i+1}")
print("C) sem descrição nenhuma:")
for i in range(3): call(tool("dre",""), P, f"sem descrição #{i+1}")
