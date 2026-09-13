#!/usr/bin/env python3
"""Fase 6 - mede latencia sob concorrencia real (nao alternancia) no mesmo
modelo, comparando OLLAMA_NUM_PARALLEL=1 vs 2. 5 lotes, descarta o primeiro
como warmup - mesmo padrao do A/B de infra deste lab.

Revisado (rodada llm-bench-4, 2026-09-05): checa /api/ps antes e depois de
cada run pra confirmar que o modelo ficou 100% em GPU (size_vram == size) --
sem isso um spill pra CPU sob NUM_PARALLEL=2 pareceria "NUM_PARALLEL=2 e mais
lento", quando a causa real seria "nao coube" (a mesma classe de erro que ja
gerou um falso bug de q8_0 na Fase 1, ver RESULTADO-fase1-*.md); guarda
eval_count/eval_duration/prompt_eval_count de cada resposta em vez de
descartar o corpo; uma falha isolada de rede nao aborta mais o lote inteiro;
MODEL deixou de ser global e virou parametro; resultado agora e persistido em
JSON (rotulado via 4o argumento) alem de impresso.

Remediado (2026-09-05): o prompt padrao abaixo (~12 tokens) mede decode sob
concorrencia, nao prefill -- nao representa o perfil de producao medido em
baseline-3080ti/baseline-3080ti.md (prompt medio ~2086-2183 tokens). Para
medir prefill sob concorrencia real, passe um arquivo de prompt longo como 5o
argumento -- ver baseline-3080ti/repro/fase6_prompt_longo.txt (908 palavras
de texto real do repo, calibrado para prompt_eval_count=2108, dentro da
faixa de producao observada).

Revisado de novo (rodada llm-bench-5, 2026-09-05): a checagem de residencia
era fail-open -- falha de rede ao consultar /api/ps e "modelo nao carregado"
caiam no mesmo estado neutro, sem alerta, mesmo depois do warmup (quando o
modelo deveria estar carregado). Agora sao 4 estados ('ok','spill','ausente',
'desconhecido'), size/size_vram brutos sao persistidos no JSON (antes so o
estado era salvo), lotes com falha de requisicao sao excluidos das
estatisticas de tempo (antes entravam e enviesavam o resultado pra parecer
mais rapido), o rotulo e sanitizado antes de virar nome de arquivo, o JSON
de resultado passou a ir pra results/ (nao mais junto dos scripts), num_ctx
passou a ser pinado, e o processo sai com exit 1 se `spill_detectado`.

Uso: python3 fase6_concurrency.py <modelo> <n_threads> <n_lotes> [rotulo] [arquivo_prompt]
"""
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Default aponta pro localhost porque esta sessao so alcanca o servidor via
# tunel SSH (100.88.95.78:11434 direto parou de responder em 2026-09-05,
# causa do lado do cliente, nao identificada -- ver
# MIGRACAO-windows-nativo-2026-09-04.md). Passe OLLAMA_URL se sua sessao
# alcancar o tailnet/LAN direto, sem precisar de tunel.
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
PROMPT_CURTO = "Explique em duas frases o que e uma nota fiscal."
SEED = 42
NUM_CTX = 32768  # pinado pra nao depender do default por-VRAM do servidor mudar entre runs
RESULTS_DIR = Path(__file__).parent.parent.parent / "results"


def get_ps(model):
    """Consulta /api/ps e devolve a entrada do modelo alvo, ou None se nao
    aparece (nao residente)."""
    req = urllib.request.Request(f"{OLLAMA}/api/ps", method="GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.load(r)
    for m in data.get("models", []):
        if m.get("name") == model or m.get("model") == model:
            return m
    return None


def check_full_gpu_residency(model, when):
    """Retorna {'estado', 'size', 'size_vram'}. Estados: 'ok' (100% GPU),
    'spill' (carregado, parcialmente em CPU), 'ausente' (nao aparece em
    /api/ps -- neutro so ANTES do 1o load; suspeito depois), 'desconhecido'
    (falha ao consultar /api/ps -- nao confundir com 'ausente': aqui a
    pergunta nao foi respondida, nao foi respondida com 'nao'). Nao aborta
    sozinho -- quem chama decide o que fazer com cada estado."""
    try:
        ps = get_ps(model)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"  [aviso] {when}: falha ao consultar /api/ps ({type(e).__name__}: {e})")
        return {"estado": "desconhecido", "size": None, "size_vram": None}
    if ps is None:
        print(f"  [info] {when}: {model!r} nao aparece em /api/ps (ainda nao carregado)")
        return {"estado": "ausente", "size": None, "size_vram": None}
    size, size_vram = ps.get("size", 0), ps.get("size_vram", 0)
    # TODO (2026-09-10): este check e CEGO para modelos de decodificacao
    # especulativa. O gemma4:26b carrega um alvo de 25,23B (31/31 camadas) mais
    # um rascunho gemma4-assistant de 419,71M (5/5 camadas), e o /api/ps reporta
    # size == size_vram == 1,38 GiB -- so o rascunho. Os ~16 GiB do alvo somem, e
    # a igualdade abaixo devolve "ok" sem nunca ter visto o modelo principal.
    # Diagnostico completo em results/RESULTADO-juiz-familia-2026-09-10.md.
    # Conserto sugerido pela revisao llm-bench-9, sem precisar ler o log:
    # comparar size_vram com general.parameter_count x bytes/param do /api/show
    # (Q4_K_M ~ 0,56 B/param da ~13 GiB de piso para o gemma4) e marcar
    # "desconhecido" se o ps reportar menos da metade disso.
    # NAO CONSERTADO. Nenhum modelo especulativo entrou na Fase 6 ate hoje.
    estado = "ok" if size_vram == size else "spill"
    marca = "OK" if estado == "ok" else "SPILL"
    print(f"  [{marca}] {when}: size={size} size_vram={size_vram}")
    return {"estado": estado, "size": size, "size_vram": size_vram}


def call_one(model, prompt):
    payload = {
        "model": model, "prompt": prompt, "stream": False,
        "think": False, "options": {"temperature": 0, "num_predict": 64, "seed": SEED, "num_ctx": NUM_CTX},
    }
    req = urllib.request.Request(f"{OLLAMA}/api/generate", data=json.dumps(payload).encode(),
                                  headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as r:
        body = json.load(r)
    elapsed = time.perf_counter() - t0
    return {
        "elapsed": elapsed,
        "eval_count": body.get("eval_count"),
        "eval_duration_ns": body.get("eval_duration"),
        "prompt_eval_count": body.get("prompt_eval_count"),
        "prompt_eval_duration_ns": body.get("prompt_eval_duration"),
    }


def run_batch(model, prompt, n_threads):
    t_batch0 = time.perf_counter()
    per_req, falhas = [], 0
    with ThreadPoolExecutor(max_workers=n_threads) as ex:
        futs = [ex.submit(call_one, model, prompt) for _ in range(n_threads)]
        for f in as_completed(futs):
            try:
                per_req.append(f.result())
            except Exception as e:  # noqa: BLE001 - qualquer falha de request vira dado, nao crash
                falhas += 1
                print(f"    [erro_infra] {type(e).__name__}: {e}")
    batch_wall = time.perf_counter() - t_batch0
    return batch_wall, per_req, falhas


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:14b"
    n_threads = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    n_lotes = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    label = sys.argv[4] if len(sys.argv) > 4 else "sem-rotulo"
    prompt_file = sys.argv[5] if len(sys.argv) > 5 else None
    if n_threads <= 0 or n_lotes <= 0:
        raise SystemExit(f"n_threads e n_lotes devem ser > 0 (recebido {n_threads}, {n_lotes})")

    if prompt_file:
        prompt = Path(prompt_file).read_text(encoding="utf-8")
        perfil = f"longo (arquivo={prompt_file})"
    else:
        prompt = PROMPT_CURTO
        perfil = "curto (default, nao representativo de producao)"

    print(f"modelo={model} threads={n_threads} lotes={n_lotes} rotulo={label!r} "
          f"seed={SEED} prompt={perfil} (1o lote descartado como warmup)\n")

    check_full_gpu_residency(model, "antes do warmup (esperado: ausente, num cold start)")

    batch_walls, all_per_req, falhas_totais, lotes_descartados = [], [], 0, 0
    residente_pos_warmup = None
    for lote in range(n_lotes + 1):
        wall, per_req, falhas = run_batch(model, prompt, n_threads)
        falhas_totais += falhas
        tag = "warmup" if lote == 0 else f"lote{lote}"
        tempos = [f"{r['elapsed']:.2f}" for r in per_req]
        sufixo = f"  [{falhas} falha(s) -- lote descartado das estatisticas]" if falhas else ""
        print(f"  {tag:<8} wall_lote={wall:6.2f}s  por_req={tempos}{sufixo}")
        if lote == 0:
            residente_pos_warmup = check_full_gpu_residency(model, "logo apos o warmup (inicio da janela medida)")
        if lote > 0:
            if falhas:
                lotes_descartados += 1
            else:
                batch_walls.append(wall)
                all_per_req.extend(per_req)

    residente_depois = check_full_gpu_residency(model, "depois do ultimo lote (fim da janela medida)")

    print()
    estados_suspeitos = {"spill", "ausente", "desconhecido"}
    spill_detectado = (residente_pos_warmup["estado"] in estados_suspeitos
                        or residente_depois["estado"] in estados_suspeitos)
    if spill_detectado:
        print("  [ATENCAO] residencia em GPU nao confirmada como 100% na janela "
              f"medida (pos-warmup={residente_pos_warmup['estado']!r}, "
              f"final={residente_depois['estado']!r}) -- resultado abaixo pode "
              "refletir spill p/ CPU ou verificacao falha, nao o efeito de "
              "NUM_PARALLEL. Nao usar esta run para decisao sem investigar "
              "(ver 'ollama ps' manualmente).\n")
    if lotes_descartados:
        print(f"  [aviso] {lotes_descartados} lote(s) com falha de requisicao "
              "excluido(s) das estatisticas de tempo (viés seria na direcao de "
              "parecer mais rapido do que e).\n")

    tempos_totais = [r["elapsed"] for r in all_per_req]
    prompt_evals = [r["prompt_eval_count"] for r in all_per_req if r.get("prompt_eval_count")]
    toks_s = [r["eval_count"] / (r["eval_duration_ns"] / 1e9)
              for r in all_per_req if r.get("eval_count") and r.get("eval_duration_ns")]
    resultado = {
        "modelo": model, "rotulo": label, "threads": n_threads, "lotes": n_lotes,
        "seed": SEED, "prompt_perfil": perfil,
        "residente_pos_warmup": residente_pos_warmup, "residente_depois": residente_depois,
        "spill_detectado": spill_detectado,
        "falhas_infra": falhas_totais, "lotes_descartados_por_falha": lotes_descartados,
        "wall_lote_mediana_s": statistics.median(batch_walls) if batch_walls else None,
        "wall_lote_min_s": min(batch_walls) if batch_walls else None,
        "wall_lote_max_s": max(batch_walls) if batch_walls else None,
        "por_req_mediana_s": statistics.median(tempos_totais) if tempos_totais else None,
        "por_req_min_s": min(tempos_totais) if tempos_totais else None,
        "por_req_max_s": max(tempos_totais) if tempos_totais else None,
        "prompt_eval_count_mediana": statistics.median(prompt_evals) if prompt_evals else None,
        "gen_tok_s_mediana": statistics.median(toks_s) if toks_s else None,
        "n_amostras": len(tempos_totais),
        "por_req_detalhe": all_per_req,
    }

    if batch_walls:
        print(f"wall do lote (concorrente): mediana={resultado['wall_lote_mediana_s']:.2f}s  "
              f"min={resultado['wall_lote_min_s']:.2f}s  max={resultado['wall_lote_max_s']:.2f}s")
    if tempos_totais:
        print(f"tempo por requisicao:       mediana={resultado['por_req_mediana_s']:.2f}s  "
              f"min={resultado['por_req_min_s']:.2f}s  max={resultado['por_req_max_s']:.2f}s  "
              f"n={resultado['n_amostras']}")
    if prompt_evals:
        print(f"prompt_eval_count (prefill): mediana={resultado['prompt_eval_count_mediana']:.0f} tokens")
    if toks_s:
        print(f"geracao pura (decode):       mediana={resultado['gen_tok_s_mediana']:.1f} tok/s "
              f"(eval_count/eval_duration, exclui espera de fila e prefill)")
    if falhas_totais:
        print(f"falhas de infra descartadas: {falhas_totais}")

    rotulo_seguro = re.sub(r"[^A-Za-z0-9_-]", "_", label) or "sem-rotulo"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"fase6_resultado_{rotulo_seguro}_{int(time.time())}.json"
    out_path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nresultado salvo em {out_path}")

    if spill_detectado:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
