import json, urllib.request

GW = "http://127.0.0.1:8080/v1/chat/local"
TOOL = {"type": "function", "function": {
    "name": "dre", "description": "Retorna o DRE consolidado do periodo",
    "parameters": {"type": "object", "properties": {"escopo": {"type": "string"}}, "required": ["escopo"]}}}

# dict com ~20 chaves numericas, como ele descreveu
PAYLOAD = {
    "receita_bruta": 61300000.00, "deducoes": -8200000.00, "receita_liquida": 53100000.00,
    "cmv": -31400000.00, "lucro_bruto": 21700000.00, "despesas_comerciais": -9800000.00,
    "despesas_administrativas": -7300000.00, "despesas_pessoal": -4100000.00,
    "alugueis": -820000.00, "energia": -410000.00, "manutencao": -290000.00,
    "marketing": -1200000.00, "viagens": -180000.00, "consultorias": -540000.00,
    "seguros": -95000.00, "telefonia": -62000.00, "licencas_softwares": -324.00,
    "depreciacao": -880000.00, "resultado_financeiro": -1200000.00,
    "impostos": -340000.00, "resultado_liquido": -971553.41,
}

def call(messages, tools=None):
    body = {"project": "repro-concisao", "messages": messages}
    if tools: body["tools"] = tools
    req = urllib.request.Request(GW, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)

msgs = [{"role": "user", "content": "Use a ferramenta dre com escopo grupo:KSH. Qual foi o resultado?"}]
r1 = call(msgs, [TOOL])
msgs.append(r1["message"])
calls = r1["message"].get("tool_calls") or []
if not calls:
    print("modelo nao chamou a ferramenta:", r1["message"].get("content", "")[:200]); raise SystemExit
msgs.append({"role": "tool", "tool_call_id": calls[0]["id"], "content": json.dumps(PAYLOAD)})
r2 = call(msgs, [TOOL])
texto = r2["message"].get("content") or ""
print("=" * 70)
print(texto)
print("=" * 70)
print(f"caracteres: {len(texto)} | linhas: {len(texto.splitlines())} | tokens_saida: {r2['output_tokens']}")
