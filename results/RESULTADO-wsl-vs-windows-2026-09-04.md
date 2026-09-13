# WSL2 vs Windows nativo, e cuda_v12 vs cuda_v13 — RTX 5090, 2026-09-04

Dois A/B na mesma placa, mesmo modelo (`qwen3:8b`, digest `500a1f067a9f` idêntico
nos dois stores), mesmo `num_ctx=8192`, `num_predict=256`, `temperature=0`,
`seed=42`, 5 repetições alternadas, warmup descartado. Harness:
[`../bench_engine_ab.py`](../bench_engine_ab.py).

O serviço de produção (`content-insights-ollama.service`, porta 11434) **não foi
tocado**: as instâncias de teste subiram no Windows nas portas 11435 e 11436, e
foram derrubadas ao fim. Verificado antes e depois — mesmo pid, unit `active`.

## Run 1 — WSL2 vs Windows nativo

`engine_ab_20260904_145228.{json,md}`

| | A | B |
|---|---|---|
| onde | WSL2 Debian 13 (produção) | Windows 11 nativo |
| Ollama | 0.33.2 | 0.33.3 |
| runner | cuda_v12 (forçado por env var) | cuda_v13 (auto) |

| prompt | métrica | wsl | windows | delta |
|---|---|---|---|---|
| curto (~5 tok) | **decode tok/s** | 201,40 | 232,45 | **+15,4%** |
| médio (~616 tok) | **decode tok/s** | 199,71 | 225,78 | **+13,1%** |
| longo (~1191 tok) | **decode tok/s** | 195,02 | 223,74 | **+14,7%** |
| médio | prefill tok/s | 40.644 | 42.016 | +3,4% |
| longo | prefill tok/s | 26.950 | 26.049 | −3,3% |
| longo | TTFT s | 0,05 | 0,05 | +2,2% |

**Decode difere ~14% de forma consistente nos três tamanhos; prefill e TTFT
empatam dentro do ruído.** É exatamente a assinatura prevista: o custo da
paravirtualização está em latência de *kernel launch*, e o decode é um laço de
muitos launches pequenos, enquanto o prefill são poucos launches grandes.

Descartado que fosse cache de prompt: `prompt_eval_count` ficou constante
(616 e 1191) em todas as repetições dos dois lados — o prompt foi reprocessado
toda vez.

## Run 2 — o mesmo teste isolando o runner CUDA

`engine_ab_20260904_145334.{json,md}`

Duas instâncias **ambas no Windows nativo**, mesma versão 0.33.3, mesmo store,
diferindo só no runner (confirmado nos logs: `libdirs=ollama,cuda_v13` contra
`libdirs=ollama,cuda_v12`).

| prompt | métrica | win-cuda12 | win-cuda13 | delta |
|---|---|---|---|---|
| curto | decode tok/s | 233,74 | 233,09 | −0,3% |
| médio | decode tok/s | 223,78 | 224,51 | +0,3% |
| longo | decode tok/s | 222,13 | 218,58 | −1,6% |
| longo | prefill tok/s | 26.607 | 26.449 | −0,6% |

**Empate.** O runner CUDA não explica nada.

> O resumo automático acusa −47,2% no prefill do prompt `medio`. É artefato: a
> instância `cuda13` foi bimodal ali (48.439 na primeira repetição, depois
> ~24.000 nas quatro seguintes), enquanto no prompt `longo` as duas ficam coladas
> (26.607 vs 26.449). Leia a linha `longo`.

## Conclusões

**1. Os ~14% são do WSL2, não do runner.** O Run 2 elimina o runner CUDA como
explicação. Sobra um confusor: 0.33.2 vs 0.33.3. É um patch release — muito
improvável valer 14% de decode, mas não foi isolado. Isolar exigiria instalar o
0.33.2 no Windows ou atualizar o WSL (que é produção).

**2. `OLLAMA_LLM_LIBRARY=cuda_v12` pode sair da unit, mas não por performance.**
O empate do Run 2 responde essa pergunta **sem reiniciar o serviço de produção** —
a bancada do Windows serviu de laboratório para uma decisão do WSL. Remova por
higiene (a var mascara o auto-detect e é resíduo de um workaround já resolvido),
sem esperar ganho.

**3. Migrar para Windows nativo não é a próxima ação.** Os 14% são reais e
permanentes, mas o gargalo medido do parque é **fila**, não throughput de pico:
a baseline da 3080 Ti mostra p5 de ~24 tok/s contra mediana de 64, e o
`acervo/task-97` registrou a GPU a 1–4% de utilização durante chamadas lentas.
Nenhum dos dois melhora com +14% de decode; ambos melhoram com
`MAX_LOADED_MODELS` e contexto explícito.

Contra a migração pesam ainda: perder a unit systemd com `Restart=always` e o
`journalctl` (foi o journal que revelou o salto de `-c 4096` para `-c 32768`, o
breakdown de 5,0 GiB de KV e o histórico da placa antiga), mover 40 GB de
modelos, e refazer a exposição de rede — que hoje **já está resolvida** pelo
`networkingMode=mirrored`: o WSL enxerga direto o IP da LAN e o da tailnet, sem
NAT nem portproxy, e o loopback funciona nos dois sentidos.

Reavaliar quando o parque estabilizar. Se um modelo virar executor principal, a
opção mais interessante não é migrar tudo — é a mesma ideia do llama-server com
MTP: **Ollama no WSL como parque, Windows nativo como hot path.**

## Achado colateral: um risco que já existia

`OLLAMA_HOST=0.0.0.0:11434` está definido no escopo **Machine** do Windows
(variável de sistema). Com mirrored networking, WSL e Windows compartilham o
espaço de portas. Se o Ollama do Windows for iniciado sem sobrescrever — e ele
**está instalado** desde 03/09, em
`C:\Users\Breno Perucchi\AppData\Local\Programs\Ollama\ollama.exe` — ele tenta
bindar exatamente a porta do serviço de produção. Quem faz bind primeiro ganha.

Num boot em que o Windows suba antes do WSL, o `content-insights-ollama.service`
falha e os quatro consumidores ficam sem Ollama. Vale corrigir independentemente
de qualquer decisão de migração: apagar a variável Machine, ou apontá-la para
uma porta que não colida.

## Limpeza

Instâncias 11435 e 11436 encerradas; nada escutando no Windows. Restam **4,9 GB**
em `C:\Users\Breno Perucchi\.ollama-bench` (o store do `qwen3:8b` do teste).
Remover com:

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.ollama-bench"
```

Manter só se for repetir o A/B — evita rebaixar 5,2 GB.

---

## Epílogo: a migração foi feita

A recomendação acima era **não migrar agora**. O dono do lab decidiu migrar, com
os números à vista, e a migração foi executada no mesmo dia — ver
[`../MIGRACAO-windows-nativo-2026-09-04.md`](../MIGRACAO-windows-nativo-2026-09-04.md).

O ganho previsto se confirmou em produção: **225,9 tok/s** medidos no servidor já
migrado (qwen3:8b, 256 tokens), contra os 225,8 do lado `windows` deste A/B e os
199,7 do WSL.

Duas ressalvas deste documento seguem de pé e viraram pendências: a
observabilidade regrediu (não há mais `journalctl`), e o gargalo de **fila**
continua sem tratamento — `MAX_LOADED_MODELS` e contexto explícito ainda não
foram ajustados.
