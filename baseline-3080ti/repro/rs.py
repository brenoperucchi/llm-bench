import json, urllib.request, sys
sys.path.insert(0, "/home/brenoperucchi/Devs/llm-gateway/src")
from llm_gateway.profiles import LOCAL_CHAT

TOOL = {"type":"function","function":{"name":"dre","description":"Consulta o DRE consolidado",
    "parameters":{"type":"object","properties":{"escopo":{"type":"string"}},"required":["escopo"]}}}
PERGUNTA = {"role":"user","content":"Qual foi o resultado do KCO em 2025? Use a ferramenta."}

def run(rot, messages, n=5):
    anom = 0; amostras = []
    for _ in range(n):
        body = {"model":"qwen2.5:14b","messages":messages,"stream":False,"tools":[TOOL]}
        req = urllib.request.Request("http://100.88.95.78:11434/api/chat",
            data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            b = json.load(r)
        m = b.get("message",{})
        if not (m.get("tool_calls") or []):
            anom += 1
            amostras.append((m.get("content") or "").strip()[:55])
    print(f"  {rot:32} sem tool_call: {anom}/{n}")
    for a in amostras[:2]: print(f"       {a!r}")

run("SEM system_prompt", [PERGUNTA])
run("COM o system_prompt do perfil", [{"role":"system","content":LOCAL_CHAT.system_prompt}, PERGUNTA])
