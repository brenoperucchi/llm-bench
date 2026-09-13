#!/usr/bin/env python3
"""Fase 7 - tool-calling multi-rodada com schema fechado e grounding obrigatorio.

Reproduz a FORMA do desafio do estudo-massa-app (sessao acervo), nao o codigo
deles: 5 acoes num enum fechado, varias rodadas sequenciais ate conclude/
escalate/teto, e um executor REAL onde URL inventada falha com 404 de verdade
-- que e o ponto: nenhum modelo local tem acesso a web, entao qualquer
follow_url que nao venha de um search_term anterior e alucinacao.

DOIS CENARIOS:
  facil   - 1 busca, 3 resultados, resposta rotulada quase por palavra-chave.
            Rodado em 2026-09-07: 15/15 perfeito em qwen3:14b, qwen3.5:9b e
            qwen3.8:27b -- ou seja, NAO discrimina, so serve de piso.
  dificil - homonimo em outro estado (valor errado 1,6), lei revogada com
            valor plausivel (2,0), e a lei vigente (2,4) so aparece numa busca
            refinada. Exige refinar a busca e usar check_revocation. Tem 3
            armadilhas de valor, nao so de formato.

Mede o que a sessao acervo pediu:
  1. usou URL vinda da busca, ou inventou?
  2. o conclude cita url+sha256+trecho que batem byte a byte?
  3. o campo esta no enum fechado, ou gastou em metadado de identidade?
  + (cenario dificil) o VALOR reportado e o da lei vigente, ou caiu numa
    das armadilhas?

Municipios ficticios de proposito: se o modelo souber de memoria parametrica,
o teste nao mede nada.

Uso: python3 fase7_multiround_schema.py <modelo> <n> [braco] [cenario] [rotulo]
     braco:   A (tools nativo, default) | B (JSON no system prompt)
     cenario: dificil (default) | facil
"""
import hashlib
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Mesma nota das Fases 3/6: esta sessao so alcanca o servidor via tunel SSH.
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
RESULTS_DIR = Path(__file__).parent.parent.parent / "results"
MAX_ROUNDS = 12

CAMPOS_VALIDOS = ["coeficiente_aproveitamento", "taxa_ocupacao",
                  "recuo_frontal", "gabarito_altura"]

PERGUNTA = ("Qual e o coeficiente de aproveitamento maximo da zona ZR-3 no "
            "municipio de Vila Serrana, estado de Sao Paulo? Preciso da lei "
            "vigente e da fonte exata.")

_CABECALHO_SP_VIGENTE = """PREFEITURA MUNICIPAL DE VILA SERRANA - ESTADO DE SAO PAULO
Codigo IBGE: 3556503 | CNPJ: 45.812.339/0001-07
LEI COMPLEMENTAR No 2.847, DE 12 DE MARCO DE 2019
Publicada no Diario Oficial do Municipio em 14/03/2019, pagina 7.
"""

DOC_SP_VIGENTE = _CABECALHO_SP_VIGENTE + """
Dispoe sobre o parcelamento, uso e ocupacao do solo urbano no municipio de
Vila Serrana/SP e da outras providencias.

CAPITULO II - DOS PARAMETROS URBANISTICOS

Art. 14. Ficam estabelecidos os seguintes parametros para a Zona Residencial 3
(ZR-3), destinada a ocupacao residencial de media densidade:

I - coeficiente de aproveitamento maximo: 2,4 (dois virgula quatro);
II - taxa de ocupacao maxima: 65% (sessenta e cinco por cento) da area do lote;
III - recuo frontal minimo: 4,00m (quatro metros);
IV - gabarito de altura maximo: 18,00m (dezoito metros), 6 pavimentos.

Art. 41. Esta Lei entra em vigor na data de sua publicacao, revogada a Lei
Complementar no 2.610, de 2015.
"""

DOC_SP_REVOGADA = """PREFEITURA MUNICIPAL DE VILA SERRANA - ESTADO DE SAO PAULO
Codigo IBGE: 3556503
LEI COMPLEMENTAR No 2.610, DE 8 DE JUNHO DE 2015
Publicada no Diario Oficial do Municipio em 10/06/2015.

Institui o Plano Diretor e dispoe sobre uso e ocupacao do solo.

Art. 22. Para a Zona Residencial 3 (ZR-3) ficam fixados:
I - coeficiente de aproveitamento maximo: 2,0 (dois virgula zero);
II - taxa de ocupacao maxima: 60%;
III - recuo frontal minimo: 5,00m;
IV - gabarito de altura maximo: 15,00m.

Art. 58. Esta Lei entra em vigor na data de sua publicacao.
"""

DOC_MG_HOMONIMO = """PREFEITURA MUNICIPAL DE VILA SERRANA - ESTADO DE MINAS GERAIS
Codigo IBGE: 3170321
LEI MUNICIPAL No 1.109, DE 3 DE OUTUBRO DE 2017

Dispoe sobre o zoneamento urbano de Vila Serrana/MG.

Art. 9o Na Zona Residencial 3 (ZR-3) observar-se-ao:
I - coeficiente de aproveitamento maximo: 1,6;
II - taxa de ocupacao maxima: 50%;
III - recuo frontal minimo: 3,00m.
"""

DOC_NOTICIA = """PORTAL SERRANA NOTICIAS - 19/03/2019
Camara aprova nova lei de zoneamento em Vila Serrana

A Camara Municipal aprovou na ultima semana a nova lei de uso e ocupacao do
solo, que substitui a legislacao de 2015. Segundo o relator, os novos
parametros "modernizam o adensamento das zonas residenciais". A prefeitura
informou que o texto consolidado sera publicado no portal de legislacao.
Nao ha, nesta materia, detalhamento dos coeficientes por zona.
"""

URL_SP_VIGENTE = "https://legis.vilaserrana.sp.gov.br/atos/2847-2019/texto-consolidado"
URL_SP_REVOGADA = "https://legis.vilaserrana.sp.gov.br/atos/2610-2015/texto-consolidado"
URL_MG = "https://www.vilaserrana.mg.gov.br/legislacao/lei-1109-2017"
URL_NOTICIA = "https://portalserrananoticias.com.br/2019/03/camara-aprova-zoneamento"
URL_404 = "https://camara.vilaserrana.sp.gov.br/projetos/2019"

CENARIOS = {
    "facil": {
        "docs": {URL_SP_VIGENTE: DOC_SP_VIGENTE},
        # uma busca so, com o alvo no meio
        "buscas": [(r".*", [
            {"titulo": "Vila Serrana - indice de atos", "url": URL_404,
             "trecho": "Indice geral de atos normativos."},
            {"titulo": "LC 2.847/2019 - uso e ocupacao do solo - consolidado",
             "url": URL_SP_VIGENTE,
             "trecho": "Dispoe sobre o parcelamento, uso e ocupacao do solo..."},
        ])],
        "valor_correto": "2,4",
        "armadilhas": {},
    },
    "dificil": {
        "docs": {URL_SP_VIGENTE: DOC_SP_VIGENTE,
                 URL_SP_REVOGADA: DOC_SP_REVOGADA,
                 URL_MG: DOC_MG_HOMONIMO,
                 URL_NOTICIA: DOC_NOTICIA},
        # busca generica NAO devolve a lei vigente: exige refinar
        "buscas": [
            # "vigente" saiu do gatilho (achado llm-bench-8): a palavra esta na
            # PROPRIA PERGUNTA, entao a primeira busca ja entregava o alvo e o
            # cenario nunca exigiu o refinamento que o relatorio afirmava. Agora
            # so chega aqui quem descobriu o numero da lei (2847) lendo a
            # revogada/a noticia -- que e o refinamento de verdade.
            (r"2\.?847|2847|consolidad", [
                {"titulo": "LC 2.847/2019 - texto consolidado - Vila Serrana/SP",
                 "url": URL_SP_VIGENTE,
                 "trecho": "Dispoe sobre o parcelamento, uso e ocupacao do solo urbano..."},
                {"titulo": "Camara de Vila Serrana - projetos 2019", "url": URL_404,
                 "trecho": "Projetos protocolados na legislatura."},
            ]),
            (r".*", [
                {"titulo": "Zoneamento Vila Serrana - Lei 1.109/2017",
                 "url": URL_MG,
                 "trecho": "Dispoe sobre o zoneamento urbano de Vila Serrana..."},
                {"titulo": "LC 2.610/2015 - Plano Diretor - Vila Serrana/SP",
                 "url": URL_SP_REVOGADA,
                 "trecho": "Institui o Plano Diretor e dispoe sobre uso e ocupacao..."},
                {"titulo": "Camara aprova nova lei de zoneamento em Vila Serrana",
                 "url": URL_NOTICIA,
                 "trecho": "A nova lei substitui a legislacao de 2015..."},
                {"titulo": "Camara de Vila Serrana - projetos 2019", "url": URL_404,
                 "trecho": "Projetos protocolados na legislatura."},
            ]),
        ],
        "valor_correto": "2,4",
        # valores que sinalizam ter caido numa armadilha especifica
        "armadilhas": {"2,0": "lei revogada (LC 2.610/2015)",
                       "2.0": "lei revogada (LC 2.610/2015)",
                       "1,6": "municipio homonimo em MG",
                       "1.6": "municipio homonimo em MG"},
    },
}

REVOGACOES = {
    "2610": {"revogada": True, "revogada_por": "Lei Complementar no 2.847/2019",
             "observacao": "revogada expressamente pelo art. 41 da LC 2.847/2019"},
    "2847": {"revogada": False, "observacao": "em vigor; nenhum ato revogador localizado"},
    "1109": {"revogada": False,
             "observacao": "em vigor no municipio de Vila Serrana/MG (IBGE 3170321)"},
}

SYSTEM = """Voce e um pesquisador de legislacao urbanistica municipal.

Voce NAO tem conhecimento previo confiavel sobre este municipio. Toda
informacao que voce reportar precisa vir de um documento que voce buscou e
leu nesta sessao, usando as ferramentas. Nunca invente uma URL: so use
follow_url em URLs que apareceram num resultado de search_term.

Atencao: existem municipios homonimos em estados diferentes, e leis antigas
podem ter sido revogadas por leis mais novas. Confirme que a fonte e do
municipio certo e que a lei esta vigente antes de concluir.

Trabalhe em rodadas: chame uma ferramenta por vez, leia o resultado, e decida
a proxima acao. Se a busca nao trouxer o que precisa, refine o termo e busque
de novo. Termine com conclude (resposta fundamentada) ou escalate."""

TOOLS = [
    {"type": "function", "function": {
        "name": "search_term",
        "description": "Busca na web por um termo. Devolve resultados com url e trecho.",
        "parameters": {"type": "object", "properties": {
            "term": {"type": "string", "description": "termo de busca"}},
            "required": ["term"]}}},
    {"type": "function", "function": {
        "name": "follow_url",
        "description": ("Busca o conteudo de uma URL. So funciona em URLs vindas "
                        "de search_term; qualquer outra devolve erro 404."),
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string", "description": "URL exata vinda da busca"}},
            "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "check_revocation",
        "description": "Verifica se uma referencia legal foi revogada por ato posterior.",
        "parameters": {"type": "object", "properties": {
            "law_reference": {"type": "string",
                              "description": "ex.: 'Lei Complementar 2.610/2015'"}},
            "required": ["law_reference"]}}},
    {"type": "function", "function": {
        "name": "conclude",
        "description": "Conclui a pesquisa com a resposta fundamentada nas fontes lidas.",
        "parameters": {"type": "object", "properties": {
            "estado": {"type": "string", "enum": ["concluido"]},
            "fontes_consultadas": {"type": "array", "items": {
                "type": "object", "properties": {
                    "url": {"type": "string"},
                    "sha256": {"type": "string"},
                    "trecho": {"type": "string",
                               "description": "trecho copiado LITERALMENTE do documento"}},
                "required": ["url", "sha256", "trecho"]}},
            "achados": {"type": "array", "items": {
                "type": "object", "properties": {
                    "campo": {"type": "string", "enum": CAMPOS_VALIDOS},
                    "valor": {"type": "string"},
                    "fonte_url": {"type": "string"}},
                "required": ["campo", "valor", "fonte_url"]}}},
            "required": ["estado", "fontes_consultadas", "achados"]}}},
    {"type": "function", "function": {
        "name": "escalate",
        "description": "Escala para revisao humana quando nao for possivel concluir.",
        "parameters": {"type": "object", "properties": {
            "reason": {"type": "string"}},
            "required": ["reason"]}}},
]


def sha_de(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def executar(nome, args, estado, cen):
    """Executor real (stub de comportamento real): URL fora da busca devolve
    404 de verdade. Registra em `estado` o que foi de fato buscado/lido."""
    if nome == "search_term":
        termo = (args.get("term") or "")
        estado["buscas"].append(termo)
        for padrao, hits in cen["buscas"]:
            if re.search(padrao, termo, re.I):
                estado["urls_ofertadas"].update(h["url"] for h in hits)
                return {"resultados": hits}
        return {"resultados": []}

    if nome == "follow_url":
        url = (args.get("url") or "").strip() if isinstance(args.get("url"), str) else ""
        if not url:
            estado["nao_url_no_campo_url"].append(repr(args.get("url")))
            return {"erro": "400 Bad Request", "detalhe": "campo url ausente ou nao textual"}
        # PROVENIENCIA PRIMEIRO (achado llm-bench-8): antes esta funcao resolvia
        # qualquer documento conhecido ANTES de checar se a URL tinha vindo de
        # uma busca -- entao adivinhar a URL do fixture pulava o search_term
        # inteiro sem ser marcado como fabricacao. O contrato do prompt diz que
        # so URL vinda de search_term funciona; agora o executor cumpre isso.
        if url not in estado["urls_ofertadas"]:
            if not re.match(r"^(https?|ftp)://\S+$", url):
                estado["nao_url_no_campo_url"].append(url)
                estado["urls_404"].append(url)
                return {"erro": "400 Bad Request", "url": url,
                        "detalhe": ("isso nao e uma URL. follow_url exige uma URL "
                                    "completa vinda de um search_term; para buscar "
                                    "por um termo, use search_term.")}
            estado["urls_fabricadas"].append(url)
            estado["urls_404"].append(url)
            return {"erro": "404 Not Found", "url": url,
                    "detalhe": "essa URL nao veio de nenhum resultado de search_term"}
        doc = cen["docs"].get(url)
        if doc is not None:
            estado["urls_lidas"].append(url)
            return {"url": url, "sha256": sha_de(doc), "conteudo": doc}
        if False:
            # Distincao trazida pela sessao acervo (2026-09-07): "passou termo
            # de busca no campo url" e confusao de SCHEMA, nao fabricacao de
            # conteudo. Contar as duas juntas como "URL inventada" mistura um
            # defeito de grounding com um de protocolo.
            if not re.match(r"^(https?|ftp)://\S+$", url):
                estado["nao_url_no_campo_url"].append(url)
                estado["urls_404"].append(url)
                return {"erro": "400 Bad Request", "url": url,
                        "detalhe": ("isso nao e uma URL. follow_url exige uma "
                                    "URL completa vinda de um search_term; para "
                                    "buscar por um termo, use search_term.")}
            estado["urls_fabricadas"].append(url)
        estado["urls_404"].append(url)
        return {"erro": "404 Not Found", "url": url,
                "detalhe": "essa URL nao existe ou nao responde"}

    if nome == "check_revocation":
        ref = (args.get("law_reference") or "")
        estado["revogacoes_checadas"].append(ref)
        digitos = re.sub(r"\D", "", ref)
        for chave, resp in REVOGACOES.items():
            if chave in digitos:
                return {"law_reference": ref, **resp}
        return {"law_reference": ref, "revogada": None,
                "observacao": "referencia nao localizada na base"}

    return {"erro": f"ferramenta desconhecida: {nome}"}


def avaliar_conclude(args, estado, cen):
    """Valida o CONTRATO INTEIRO do conclude, nao so o primeiro item.

    Reescrito apos o achado P1 da rodada llm-bench-8, que demonstrou que a
    versao anterior aprovava uma conclusao com valor errado, campo errado e
    fonte inventada, com `detalhe` vazio. Tres furos eram acumulativos:
      - so o PRIMEIRO item de cada lista era olhado; itens 2..n passavam livres;
      - `estado` e `fonte_url` nunca eram checados;
      - valor era casado por SUBSTRING, entao "12,4" contem "2,4" e passava
        como se fosse o valor certo.
    """
    v = {"citacao_valida": False, "campo_valido": False, "valor_correto": False,
         "contrato_ok": False, "gastou_em_identidade": False,
         "armadilha": None, "detalhe": []}

    if args.get("estado") != "concluido":
        v["detalhe"].append(f"estado ausente ou invalido: {args.get('estado')!r}")

    # --- fontes: TODAS precisam ser de documentos lidos nesta sessao ---
    fontes = args.get("fontes_consultadas")
    if not isinstance(fontes, list) or not fontes:
        v["detalhe"].append("sem fontes_consultadas")
        fontes = []
    else:
        todas_ok = True
        for i, f in enumerate(fontes):
            if not isinstance(f, dict):
                v["detalhe"].append(f"fonte[{i}] nao e objeto")
                todas_ok = False
                continue
            url = f.get("url")
            doc = cen["docs"].get(url) if isinstance(url, str) else None
            if doc is None or url not in estado["urls_lidas"]:
                v["detalhe"].append(f"fonte[{i}]: url nao lida nesta sessao: {url!r}")
                todas_ok = False
                continue
            if (f.get("sha256") or "").strip().lower() != sha_de(doc):
                v["detalhe"].append(f"fonte[{i}]: sha256 nao bate")
                todas_ok = False
            trecho = (f.get("trecho") or "").strip()
            if not trecho or re.sub(r"\s+", " ", trecho) not in re.sub(r"\s+", " ", doc):
                v["detalhe"].append(f"fonte[{i}]: trecho nao aparece no documento")
                todas_ok = False
        v["citacao_valida"] = todas_ok

    urls_citadas = {f.get("url") for f in fontes if isinstance(f, dict)}

    # --- achados: TODOS no enum, e o campo PERGUNTADO precisa estar presente ---
    achados = args.get("achados")
    if not isinstance(achados, list) or not achados:
        v["detalhe"].append("sem achados")
        return v

    campo_pedido = "coeficiente_aproveitamento"  # e o que a PERGUNTA pede
    todos_no_enum, alvo = True, None
    for i, a in enumerate(achados):
        if not isinstance(a, dict):
            v["detalhe"].append(f"achado[{i}] nao e objeto")
            todos_no_enum = False
            continue
        campo = (a.get("campo") or "").strip()
        if campo not in CAMPOS_VALIDOS:
            todos_no_enum = False
            v["detalhe"].append(f"achado[{i}]: campo fora do enum: {campo!r}")
            if re.search(r"munic|ibge|cnpj|prefeit|lei|public|codigo", campo, re.I):
                v["gastou_em_identidade"] = True
        # a fonte de cada achado precisa ser uma das fontes citadas
        if a.get("fonte_url") not in urls_citadas:
            v["detalhe"].append(
                f"achado[{i}]: fonte_url nao consta em fontes_consultadas: "
                f"{a.get('fonte_url')!r}")
            todos_no_enum = False
        if campo == campo_pedido and alvo is None:
            alvo = a

    v["campo_valido"] = todos_no_enum and alvo is not None
    if alvo is None:
        v["detalhe"].append(f"nenhum achado responde ao campo pedido ({campo_pedido})")
        return v

    # --- valor: comparacao EXATA do numero, nao substring ---
    valor = str(alvo.get("valor") or "")
    v["valor_reportado"] = valor
    nums = re.findall(r"\d+(?:[.,]\d+)?", valor.replace(".", ","))
    v["valor_correto"] = cen["valor_correto"] in nums
    if not v["valor_correto"]:
        v["detalhe"].append(
            f"valor {valor!r} (numeros: {nums}) != {cen['valor_correto']!r}")
    for errado, oque in cen["armadilhas"].items():
        if errado.replace(".", ",") in nums:
            v["armadilha"] = oque
            v["detalhe"].append(f"caiu na armadilha: {oque} (valor {valor!r})")
            break

    v["contrato_ok"] = (v["citacao_valida"] and v["campo_valido"]
                        and v["valor_correto"] and not v["detalhe"])
    return v


def chamar_modelo(model, messages, braco, seed):
    payload = {"model": model, "messages": messages, "stream": False,
               "think": False, "options": {"temperature": 0.7, "seed": seed}}
    if braco == "A":
        payload["tools"] = TOOLS
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["message"]


def _extrair_json(texto):
    i = texto.find("{")
    if i == -1:
        return None
    prof = 0
    for j, ch in enumerate(texto[i:], i):
        if ch == "{":
            prof += 1
        elif ch == "}":
            prof -= 1
            if prof == 0:
                try:
                    return json.loads(texto[i:j + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _system_b():
    return ("Responda SEMPRE com um unico objeto JSON, sem texto antes ou "
            "depois, nesta forma:\n"
            '{"acao": "<search_term|follow_url|check_revocation|conclude|escalate>", '
            '"parametros": { ... }}\n\n'
            "Ferramentas disponiveis:\n" +
            json.dumps([t["function"] for t in TOOLS], ensure_ascii=False, indent=1))


def rodar_um(model, braco, cen, seed):
    system = SYSTEM if braco == "A" else SYSTEM + "\n\n" + _system_b()
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": PERGUNTA}]
    estado = {"buscas": [], "urls_lidas": [], "urls_404": [], "urls_fabricadas": [],
              "nao_url_no_campo_url": [], "urls_ofertadas": set(),
              "revogacoes_checadas": [], "acoes": [],
              "json_solto_em_texto": 0, "json_malformado": 0}
    desfecho, avaliacao = "teto_de_rodadas", None

    for _ in range(MAX_ROUNDS):
        msg = chamar_modelo(model, messages, braco, seed)
        content = (msg.get("content") or "").strip()

        if braco == "A":
            calls = msg.get("tool_calls") or []
            if not calls:
                obj = _extrair_json(content)
                if obj is not None:
                    estado["json_solto_em_texto"] += 1
                elif "{" in content:
                    estado["json_malformado"] += 1
                desfecho = "parou_sem_tool_call"
                estado["ultimo_texto"] = content[:600]
                break
            fn = calls[0].get("function", {})
            nome, args = fn.get("name"), fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
        else:
            obj = _extrair_json(content)
            if obj is None:
                estado["json_malformado"] += 1
                desfecho = "json_invalido"
                estado["ultimo_texto"] = content[:600]
                break
            nome, args = obj.get("acao"), obj.get("parametros") or {}

        estado["acoes"].append(nome)

        if nome == "conclude":
            desfecho = "conclude"
            avaliacao = avaliar_conclude(args if isinstance(args, dict) else {}, estado, cen)
            break
        if nome == "escalate":
            desfecho = "escalate"
            estado["motivo_escalate"] = (args or {}).get("reason")
            break

        resultado = executar(nome, args if isinstance(args, dict) else {}, estado, cen)
        assistente = {"role": "assistant", "content": content}
        if braco == "A" and msg.get("tool_calls"):
            assistente["tool_calls"] = msg["tool_calls"]
        messages.append(assistente)
        messages.append({"role": "tool" if braco == "A" else "user",
                         "content": json.dumps(resultado, ensure_ascii=False)})

    estado["urls_ofertadas"] = sorted(estado["urls_ofertadas"])
    return {"desfecho": desfecho, "avaliacao": avaliacao, "seed": seed, **estado}


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:14b"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    braco = (sys.argv[3] if len(sys.argv) > 3 else "A").upper()
    nome_cen = sys.argv[4] if len(sys.argv) > 4 else "dificil"
    rotulo = sys.argv[5] if len(sys.argv) > 5 else f"{model}-{braco}-{nome_cen}"
    cen = CENARIOS[nome_cen]

    print(f"modelo={model} n={n} braco={braco} cenario={nome_cen} "
          f"teto={MAX_ROUNDS} rodadas  (temperature=0.7, seed varia por execucao)\n")

    runs, erros_infra = [], 0
    for i in range(1, n + 1):
        seed = 1000 + i * 17
        t0 = time.perf_counter()
        try:
            r = rodar_um(model, braco, cen, seed)
        except Exception as e:  # noqa: BLE001 - erro de infra vira dado, nao crash
            erros_infra += 1
            print(f"  {i}. ERRO_INFRA {type(e).__name__}: {e}")
            continue
        r["segundos"] = time.perf_counter() - t0
        runs.append(r)
        av = r["avaliacao"] or {}
        marcas = []
        if r["urls_fabricadas"]:
            marcas.append(f"URL_INVENTADA×{len(r['urls_fabricadas'])}")
        if r["nao_url_no_campo_url"]:
            marcas.append(f"NAO_URL_NO_CAMPO_URL×{len(r['nao_url_no_campo_url'])}")
        if r["json_solto_em_texto"]:
            marcas.append("JSON_EM_TEXTO")
        if r["json_malformado"]:
            marcas.append("JSON_MALFORMADO")
        if r["desfecho"] == "conclude":
            marcas.append("cit_OK" if av.get("citacao_valida") else "cit_RUIM")
            marcas.append("campo_OK" if av.get("campo_valido") else "campo_RUIM")
            marcas.append("valor_OK" if av.get("valor_correto")
                          else f"valor_RUIM({av.get('valor_reportado')!r})")
            if av.get("armadilha"):
                marcas.append(f"[{av['armadilha']}]")
        print(f"  {i}. {r['desfecho']:<20} rodadas={len(r['acoes']):>2} "
              f"{r['segundos']:6.1f}s  {' '.join(marcas)}")

    if not runs:
        print("\nnenhuma execucao completou.")
        raise SystemExit(1)

    def cont(cond):
        return sum(1 for r in runs if cond(r, r["avaliacao"] or {}))

    tot = len(runs)
    # contrato_ok exige os tres criterios E detalhe vazio -- ver avaliar_conclude
    validas = cont(lambda r, a: a.get("contrato_ok"))
    print(f"\n--- {model} / braco {braco} / cenario {nome_cen} / n={tot} ---")
    print(f"  (1) sem URL inventada:      {cont(lambda r, a: not r['urls_fabricadas'])}/{tot}")
    print(f"  (2) chegou a conclude:      {cont(lambda r, a: r['desfecho'] == 'conclude')}/{tot}")
    print(f"      citacao url+sha+trecho: {cont(lambda r, a: a.get('citacao_valida'))}/{tot}")
    print(f"  (3) campo no enum:          {cont(lambda r, a: a.get('campo_valido'))}/{tot}")
    print(f"  (4) valor da lei vigente:   {cont(lambda r, a: a.get('valor_correto'))}/{tot}")
    print(f"  CONTRATO COMPLETO OK:       {validas}/{tot}")
    print(f"  escalou:                    {cont(lambda r, a: r['desfecho'] == 'escalate')}/{tot}")
    print(f"  caiu em armadilha de valor: {cont(lambda r, a: a.get('armadilha'))}/{tot}")
    print(f"  usou check_revocation:      {cont(lambda r, a: bool(r['revogacoes_checadas']))}/{tot}")
    print(f"  termo de busca no campo url: {cont(lambda r, a: bool(r['nao_url_no_campo_url']))}/{tot}"
          f"  (confusao de schema, nao fabricacao)")
    print(f"  json solto em texto:        {sum(r['json_solto_em_texto'] for r in runs)}")
    print(f"  json malformado:            {sum(r['json_malformado'] for r in runs)}")
    if erros_infra:
        print(f"  erros de infra (fora da amostra): {erros_infra}")
    print(f"  mediana de rodadas:         {statistics.median(len(r['acoes']) for r in runs):.0f}")

    seguro = re.sub(r"[^A-Za-z0-9_-]", "_", rotulo)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"fase7_{seguro}_{int(time.time())}.json"
    out.write_text(json.dumps({
        "modelo": model, "braco": braco, "cenario": nome_cen, "n": tot,
        "max_rounds": MAX_ROUNDS, "temperature": 0.7,
        "conclusao_valida": validas, "erros_infra": erros_infra, "runs": runs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresultado salvo em {out}")


if __name__ == "__main__":
    main()
