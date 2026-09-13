# RTX 5090 no Ryzen9 — modelos, parametrização e plano de medição

**Data:** 2026-09-04
**Máquina:** Ryzen9WSL (Ryzen 9 5950X, 64 GiB / 31,3 GiB no WSL2 Debian 13, Win11 Pro)
**Servidor:** Ollama 0.33.2, unit **de usuário** `content-insights-ollama.service`
(`~/.config/systemd/user/`), binário próprio em `~/ollama-dist-content-insights/`
**Consumidores em produção:** content-insights-collector (direto), Khronos/DRE,
miqueias/MFC e acervo (via llm-gateway)

> **DESATUALIZADO EM 2026-09-04 (mesmo dia).** Este relatório descreve o Ollama
> rodando sob WSL2, com a unit `content-insights-ollama.service` e
> `OLLAMA_LLM_LIBRARY=cuda_v12`. **Nada disso existe mais**: o servidor foi
> migrado para o Windows nativo, como tarefa do SYSTEM que sobe no boot. Ver
> [`MIGRACAO-windows-nativo-2026-09-04.md`](MIGRACAO-windows-nativo-2026-09-04.md).
>
> O que permanece válido: a análise de modelos para 30 GiB (§1), toda a seção de
> parametrização (§2) e o plano de medição (§3) — exceto o item do runner CUDA,
> já respondido por medição (empate), e o do power limit, descartado.


---

## 0. A premissa mudou: a 5090 já está na máquina

O prompt desta investigação diz "vou trocar a 3080 Ti". A troca já aconteceu.
Medido por SSH em 2026-09-04 04:22, sem alterar nada:

```
$ /usr/lib/wsl/lib/nvidia-smi
NVIDIA-SMI 615.65.07   KMD Version: 616.64   CUDA UMD Version: 13.4
GPU 0: NVIDIA GeForce RTX 5090   32607 MiB total   600 W cap   PCIe gen4 x16
compute_cap = 12.0   (sm_120)
```

Primeira aparição da placa no journal do serviço: **2026-09-04T02:36:44-03:00**.
A última linha com "RTX 3080 Ti" é do mesmo boot anterior. O Ollama já a detectou
e está servindo com ela:

```
msg="inference compute" library=CUDA compute=12.0 name=CUDA0
  description="NVIDIA GeForce RTX 5090" libdirs=ollama,cuda_v12 driver=13.4
  total="31.8 GiB" available="30.2 GiB"
```

**Orçamento real de VRAM: 30,2 GiB utilizáveis** (31,8 GiB visíveis; ~0,4 GiB
reservados pelo WDDM + o que o desktop Windows consome).

### Três coisas mudaram sozinhas com a troca

Comparando a linha de comando que o Ollama monta para o `llama-server`
**antes** (29/08, 3080 Ti) e **agora** (04/09, 5090) — mesma unit, mesmo binário,
nenhuma variável de ambiente alterada:

| | 29/08 (3080 Ti) | 04/09 (5090) |
|---|---|---|
| contexto | `-c 4096` | **`-c 32768`** |
| batch | `-b 512 -ub 512` | **`-b 1024 -ub 1024`** |
| flash attention | `--flash-attn auto` | `--flash-attn auto` |

Isso não é acaso: o Ollama escolhe o contexto default pela VRAM disponível —
`< 24 GiB → 4k`, `24–48 GiB → 32k`, `≥ 48 GiB → 256k`
([docs](https://docs.ollama.com/context-length)). Ao cruzar os 24 GiB, o default
saltou 8×.

Custo medido disso, do `common_memory_breakdown_print` do próprio log
(qwen2.5:14b, `-c 32768`, KV em f16):

```
modelo 8423 MiB + contexto 5120 MiB + compute 328 MiB = 13871 MiB
```

**5,0 GiB de KV cache** para um modelo de 8,2 GiB. Em `-c 4096` seriam ~640 MiB.
Sobra VRAM para isso hoje, mas é 4,4 GiB comprados sem ninguém pedir — e é o
primeiro item a decidir explicitamente, não herdar.

### Duas afirmações do prompt que os dados corrigem

1. **`OLLAMA_LLM_LIBRARY=cuda_v12` continua forçado.** A unit tem o comentário
   `"Do not silently fall back to CPU. Re-enable only after the WSL GPU bridge
   exposes the RTX and this CUDA backend passes the device smoke test."` — era
   workaround da migração WSL. O dist tem **os dois** runners:
   `cuda_v12` (cuBLAS 12.8.5.5) e `cuda_v13` (cuBLAS 13.1.1.3), e o driver expõe
   CUDA 13.4. Hoje a 5090 roda pelo runner CUDA 12.8. Funciona (12.8 é a primeira
   versão com sm_120), mas é uma escolha por inércia, não por medição.

2. **"Nenhum modelo do Ryzen9 tem visão" está desatualizado.** A API responde:

   ```
   qwen3.5:9b   6.59 GB  9.7B  Q4_K_M  ctx=262144  caps=vision,completion,tools,thinking
   ```

   O `qwen3.5:9b` — justamente o que o acervo usa — já é multimodal.

---

## 1. Modelos que passam a valer a pena em 30 GiB

Todos os candidatos abaixo estão no registry do Ollama hoje e cabem com folga
para KV cache. Tamanhos são os do registry (Q4_K_M salvo indicação).

### Aptos a substituir o `qwen3:14b` como default do gateway

| Modelo | Arq. | Q4_K_M | Ativos/token | ctx | Capacidades | Por que interessa |
|---|---|---|---|---|---|---|
| **qwen3.8:27b** | denso | 18 GB | 27B | 256K | vision, tools, thinking | Geração mais recente da Qwen; benchmarks de agentic/computer-use publicados (OSWorld 84,3 / AndroidWorld 81,9). Denso → qualidade previsível, tok/s menor |
| **qwen3.6:27b** | denso | 17 GB | 27B | 256K | vision, tools, thinking | Um passo atrás do 3.8, mais rodado pela comunidade. Tem variante `-mtp` (ver §2g) |
| **qwen3.6:35b-a3b** | **MoE** | 24 GB | ~3B | 256K | vision, tools, thinking | O ponto ótimo velocidade×qualidade: peso de 35B, custo de banda de 3B |
| **gemma4:26b** (`26b-a4b`) | **MoE** | 18 GB (QAT 16 GB) | 3,8B de 25,2B | 256K | vision, tools, thinking, audio | **Continuidade direta**: é o vencedor do seu bench de CPU (99% auto_score, 0 leaks, 4/4 escalação). Único da lista com áudio |
| **gemma4:31b** | denso | 20 GB (QAT 19 GB) | 31B | 256K | vision, tools, thinking | Irmão denso do 26b; teto de qualidade da família |
| **nemotron3:33b** | — | 28 GB | — | 128K | vision, tools, thinking | "Omni": vídeo, áudio, imagem e texto. Cabe, mas quase não sobra para KV |

Referência de arquitetura do gemma4:26b-a4b: 25,2B totais, 3,8B ativos, 128
experts com 8 ativos + 1 compartilhado, sliding window de 1024
([model card](https://huggingface.co/google/gemma-4-26B-A4B),
[technical report](https://arxiv.org/pdf/2607.02770)).

### O que a mudança de classe realmente compra

- **O `gemma4:26b` deixa de ser teórico.** Ele venceu seu benchmark de CPU com
  99% e escalação limpa nas duas direções, e foi descartado para GPU porque
  17 GB não cabiam em 12. Agora cabe com 12 GiB sobrando. É o candidato com
  menor risco de regressão: você já tem o `Modelfile.lana` apontando para ele.
- **Visão sem trocar de modelo.** Hoje o parque é `completion,tools`; qualquer
  um dos candidatos acima resolve o pedido de visão sem um modelo dedicado.
- **O fim do rodízio de 25 s** (§2e) — provavelmente o maior ganho de latência
  percebida, e não é sobre tok/s.

### O que continua não cabendo

Modelos de fronteira abertos (`mistral-medium-3.5:128b`, `qwen3.5:122b`,
`ornith-1.5:397b`, e todos os `-cloud`) seguem fora. A classe 32 GB é a classe
"27–35B em Q4/QAT", não a classe "modelo grande".

### Expectativa de velocidade (números de terceiros, a confirmar na sua máquina)

Ordem de grandeza medida por terceiros em 5090, **não** na sua:

| Modelo | tok/s reportado | Fonte |
|---|---|---|
| Qwen3.5-35B-A3B Q4_K_XL, FA + KV q8_0 | 194 tg / ~6.500 pp | [llama.cpp #19890](https://github.com/ggml-org/llama.cpp/discussions/19890) |
| Qwen3.6-27B Q4_K_M | 60–90 | blogs de benchmark |
| Gemma 4 27B Q4_K_M | 38–44 | blogs de benchmark |
| Llama-2 7B Q4_0 (referência de teto) | 248 tg / 16.041 pp (FA on) | [llama.cpp #15013](https://github.com/ggml-org/llama.cpp/discussions/15013) |

A linha do 35B-A3B é a mais confiável (llama-bench com flags publicadas) e ilustra
o mesmo achado do seu relatório de CPU: **o MoE fura o teto de banda**. A diferença
é a escala — em CPU o teto denso era ~14 tok/s; aqui a GDDR7 dá 1,79 TB/s.

---

## 2. Parametrização: o que muda o número e o que é folclore

Cada item marcado como **MEDIDO** (número publicado com metodologia),
**PLAUSÍVEL** (mecanismo correto, número não verificado) ou **FOLCLORE**
(repetido sem evidência, ou verdadeiro para outra coisa).

### a) Flash attention — **MEDIDO, ganho modesto**

Já está ligada: a linha de comando mostra `--flash-attn auto`. O Ollama liga FA
por padrão desde a v0.11.8 onde o backend suporta.

Medição na própria 5090 (llama-bench, Llama-2-7B Q4_0, build 9c35706,
[scoreboard CUDA](https://github.com/ggml-org/llama.cpp/discussions/15013)):

| | sem FA | com FA | Δ |
|---|---|---|---|
| pp512 (prefill) | 14.752 tok/s | 16.042 tok/s | **+8,7%** |
| tg128 (decode) | 239,6 tok/s | 248,6 tok/s | **+3,7%** |

O ganho de velocidade é pequeno. O valor real da FA é **habilitar KV quantizado**
e derrubar a memória de atenção em contexto longo. Quem promete "2× com flash
attention" está vendendo folclore.

### b) Quantização de KV cache — **MEDIDO, e depende da família**

`OLLAMA_KV_CACHE_TYPE` aceita `f16` (default), `q8_0` (~½ da memória) e `q4_0`
(~¼) ([FAQ](https://docs.ollama.com/faq)). O consenso de fórum — "q8_0 é
praticamente lossless" — **é family-dependent, e a família que te interessa é a
pior**.

Benchmark de divergência KL sobre 250 mil tokens em 6 categorias de tarefa
([localbench](https://localbench.substack.com/p/kv-cache-quantization-benchmark)):

| Modelo | q8_0 | q4_0 |
|---|---|---|
| Qwen3.6-27B (denso) | 0,039 | 0,087 |
| Qwen3.6-35B-A3B (MoE) | 0,024 | 0,117 |
| Gemma 4 31B (denso) | 0,108 | 0,275 |
| **Gemma 4 26B-A4B (MoE)** | **0,377** | **1,088** |

O `gemma4:26b` — seu vencedor de CPU — é 3,5× mais sensível a q8_0 que o irmão
denso, e q4_0 o destrói. Nas Qwen, q8_0 é ruído e até q4_0 é usável.

**Consequência prática:** com 30 GiB você não *precisa* quantizar o KV. Se
quantizar por hábito, e o modelo escolhido for gemma4, você paga qualidade sem
precisar. Trate isso como decisão por modelo, medida no seu goldset — os traps
anti-alucinação e a escalação por token exato são exatamente o tipo de coisa que
degrada primeiro.

### c) `num_ctx` — **a alavanca de maior impacto, e a que mudou sozinha**

Já coberto em §0: o default saltou de 4k para 32k só por cruzar 24 GiB de VRAM,
custando 5,0 GiB de KV por modelo carregado.

- O `run_chat.py` já fixa `num_ctx: 8192` nas options — as runs do benchmark
  não são afetadas.
- Os **clientes de produção** provavelmente não fixam. Se não fixam, herdaram 32k.
- Contexto maior não deixa o modelo mais rápido; deixa a carga mais lenta e come
  VRAM que você poderia gastar em manter dois modelos residentes (§2e).

**Ação:** decidir `OLLAMA_CONTEXT_LENGTH` explicitamente na unit em vez de
herdar do heurístico. Para o perfil atual (system prompt de ~5 KB + turnos
curtos) 8k–16k cobre com folga.

### d) `num_batch` / `-ub` — **FOLCLORE na parte que interessa**

Blogs prometem "+50–80% de throughput com num_batch=1024". O mecanismo real:
`-b` é o batch lógico (quantos tokens de prompt o servidor bufferiza) e `-ub` é
o batch físico (o que a GPU vê por dispatch). Em **stream único**, `-b` só importa
enquanto `-b >= -ub`; nada além disso ajuda
([llama.cpp #6328](https://github.com/ggml-org/llama.cpp/discussions/6328)).

E o que ambos governam é **prefill**, não decode. O tok/s de geração é limitado
por banda de memória — o batch não entra na conta.

Onde isso importa para você: o system prompt da Lana tem ~5 KB, então o prefill
não é desprezível no TTFT. O Ollama já dobrou para `-b 1024 -ub 1024` sozinho
com a placa nova. Mensurável, mas em *tempo até o primeiro token*, não em tok/s.

### e) `num_parallel` e `max_loaded_models` — **onde está o ganho arquitetural**

`OLLAMA_NUM_PARALLEL` não acelera nada: permite requisições concorrentes,
dividindo o mesmo KV e a mesma GPU. Cada slot adicional multiplica a memória de
contexto (a memória escala com `NUM_PARALLEL × CONTEXT_LENGTH`).

O gargalo real do seu setup não é esse. É `OLLAMA_MAX_LOADED_MODELS=1` com
**três modelos em rodízio** e ~25 s de recarga a cada alternância entre clientes.
Com 12 GB isso era imposição do hardware. Com 30,2 GiB, não é mais:

```
qwen3:14b   9,3 GB  +  qwen3.5:9b  6,6 GB  =  15,9 GB de pesos
```

Dois modelos residentes cabem com folga mesmo com KV generoso. Trocar
`MAX_LOADED_MODELS=1` por 2 provavelmente elimina mais latência percebida (25 s
por troca) do que qualquer ajuste de tok/s desta seção inteira.

**Ressalva:** isso muda o comportamento de um serviço que atende 4 projetos em
produção. Merece uma janela e uma medição, não um `sed` na unit.

### f) `num_gpu` (camadas offloaded) — **irrelevante agora**

Com 30,2 GiB e modelos de 17–24 GB, tudo cabe. `num_gpu` é a alavanca de quando
*não* cabe. O que continua valendo é **verificar**: `ollama ps` mostrando
`size_vram == size` e o log dizendo `runner.vram == runner.size`. Qualquer
fração em CPU derruba o tok/s em ordem de grandeza.

### g) Escolha de engine — **o maior ganho disponível está fora do Ollama**

| Engine | Estado na 5090 (sm_120) | Veredito para este lab |
|---|---|---|
| **Ollama 0.33.2** (atual) | Funciona; usa `llama-server` internamente (llamarunner) | TTFT baixo, operação simples, 4 clientes já integrados. **Não tem speculative decoding em CUDA** |
| **llama.cpp direto** | MTP (multi-token prediction) merged em **b9180**, 16/05/2026 | **1,73× no Qwen3.6-27B denso**, 1,17× no 35B-A3B, sem perda de acurácia. É o maior ganho single-stream conhecido hoje |
| **vLLM** | sm_120 suportado a partir da v0.17.0, com GEMM FP8 dedicado. NVFP4 ainda cai em Marlin W4A16 em alguns checkpoints ([#47749](https://github.com/vllm-project/vllm/issues/47749)) | Ganho vem de batching contínuo → só compensa sob concorrência. Em single-user o TTFT é *pior* (~82 ms vs ~45 ms do Ollama em L3.1-8B) |
| **TensorRT-LLM** | FP4 nativo desde 0.17; ~135 tok/s em MoE 30B NVFP4, TTFT ~15 ms | Melhor throughput absoluto, pior custo operacional: engine compilada por modelo × config. Incompatível com um parque que troca de modelo |

Sobre MTP no Ollama: o suporte que existe é para gemma4 **no runner MLX (macOS)**
— PR [#15980](https://github.com/ollama/ollama/pull/15980), merged 05/05/2026 na
v0.23.2, explicitamente não estendido a CUDA/llama.cpp. O registry até publica
tags `qwen3.6:27b-mtp-q4_K_M`, mas a cabeça MTP não é usada pelo caminho CUDA.

**Leitura:** se depois de medir o `qwen3.6:27b` no Ollama o tok/s incomodar, a
alavanca com melhor relação ganho/risco não é vLLM nem TensorRT — é rodar
`llama-server` direto com MTP para *esse um modelo*, mantendo o Ollama para o
resto. 1,73× é maior que qualquer coisa em §2a–2d somadas.

### h) FP8 / FP4 / NVFP4 do Blackwell — **MEDIDO, e o ganho não está onde o hype diz**

NVFP4 é formato nativo do Blackwell (requer compute capability ≥ 10.0; a 5090 é
12.0). Kernels CUDA entraram no llama.cpp em
[PR #20644](https://github.com/ggml-org/llama.cpp/pull/20644) (26/03/2026, dp4a)
e [PR #21074](https://github.com/ggml-org/llama.cpp/pull/21074) (01/04/2026, MMQ
genérico).

O ganho medido, contra Q4_K_M de tamanho equivalente:

| Fase | Δ NVFP4 vs Q4_K_M |
|---|---|
| **prefill** (pp512) | **+32 a +42%** (5.415 vs 3.826 tok/s) |
| **decode** (tg) | **+9%** (84 vs 77 tok/s) |

O motivo é o mesmo de §2d: decode é limitado por banda, então segue o *footprint*
do modelo, não o empacotamento dos pesos. O hype de "1,6× com FP4" vem de cargas
de servidor com batch alto, onde o compute domina — não do seu perfil.

E no Ollama especificamente: as tags `-nvfp4` do registry são **MLX (Apple)**. O
suporte NVFP4 do Ollama estava restrito ao macOS ainda em abril/2026
([fórum NVIDIA](https://forums.developer.nvidia.com/t/ollama-with-nvfp4-support/365286)).
Não é caminho pronto no Linux/CUDA.

**Veredito:** não é a alavanca desta rodada. Vira interessante se o perfil mudar
para prompts longos ou visão (onde o prefill domina).

### i) Power limit — **MEDIDO, e é dinheiro na mesa**

Do mesmo scoreboard, na 5090, mesmo modelo e build:

| | 600 W | 400 W | Δ |
|---|---|---|---|
| pp512 | 14.752 | 12.706 | −13,9% |
| tg128 | 239,6 | 236,7 | **−1,2%** |

Cortar 200 W custa ~1% do decode. Numa máquina que também é desktop Windows, com
um serviço que fica residente, isso é térmica e ruído de graça. Não é
parametrização de modelo, mas é o melhor ganho/custo da lista.

### j) WSL2 vs Linux nativo — **PLAUSÍVEL, alta variância, meça você mesmo**

As medições públicas divergem demais para servirem de base:

- ~1,7% de penalidade em token generation, negligível em prompt processing;
- ~15% (68 → 58 tok/s numa 4070 Ti, 7B Q4_K_M);
- "90–100% do nativo" em guias de blog.

O mecanismo é conhecido e aponta para o lado baixo: o overhead do WSL2 está em
latência de *kernel launch* e na travessia PCIe, e inferência é dominada por
kernels grandes e sustentados. O trabalho do Puget Systems que costuma ser citado
para isso **não tem benchmark de GPU** — mede HPL/HPCG/NAMD em CPU.

Dois pontos específicos deste host que valem mais que a média da internet:

1. **A VM WSL2 tem 31,3 GiB de RAM** de 64 GiB físicos. Irrelevante enquanto tudo
   couber na VRAM; crítico se houver qualquer spill.
2. A 5090 está em **PCIe gen4 x16** (limite da plataforma AM4/X570 do 5950X, não
   da placa, que é gen5). Sem impacto em inferência single-GPU com o modelo
   residente; importa só no carregamento.

**Não vale migrar para Linux nativo com base em folclore.** Vale medir: uma run
do goldset em WSL2 é o número que você tem; se a diferença justificar, ela
aparecerá contra os números publicados de llama-bench na mesma placa.

### k) O suspeito nº 1 das suas anomalias não é o modelo — é o template

Você mediu, na 3080 Ti: `qwen2.5:14b` chamou a ferramenta em 4/12 (33%) contra
12/12 do `qwen3:14b`, mais saída anômala em 7 de 18 chamadas (39%) com
`tool_calls=0` e resposta ocasional em tailandês. Você descartou o gateway
(6/6 falharam direto no Ollama) e o system prompt, e concluiu "é o modelo".

Há uma terceira hipótese que os dois testes não separam: **o template de
tool-calling do registry do Ollama**. Três issues abertas descrevem exatamente
esses sintomas:

- [#14601](https://github.com/ollama/ollama/issues/14601) — as definições de
  ferramenta são renderizadas com o formato de struct do Go em vez de JSON:
  o modelo recebe `{get_weather Get the current...}`. Além disso, tool calls do
  assistente são removidas do histórico antes do template. Aberta em 03/03/2026,
  Ollama 0.17.5.
- [#14493](https://github.com/ollama/ollama/issues/14493) — Qwen3.5 mapeado para
  o pipeline errado (`Qwen3` Hermes-style JSON quando o modelo foi treinado no
  XML do Qwen3-Coder), e `</think>` não fechado corrompendo o histórico multi-turn.
- [#15783](https://github.com/ollama/ollama/issues/15783) — o sampler Go
  (`ollamarunner`) aceita e **descarta silenciosamente** `repeat_penalty`,
  `frequency_penalty` e `presence_penalty`; só `temperature`, `top_k`, `top_p` e
  `min_p` funcionam. O model card da Qwen3.8 recomenda `presence_penalty=1.5`
  no modo instruct justamente contra loops de repetição.

Duas observações que estreitam isso no seu caso:

- **Os seus modelos rodam no `llamarunner`, não no `ollamarunner`.** O log mostra
  todos subindo via `llama-server`, então o bug #15783 (penalties descartados)
  **não** é a explicação para as suas anomalias hoje. Mas passa a ser risco se
  você migrar para gemma4, que roda no engine Go.
- O Ollama sobe o `llama-server` com **`--no-jinja --chat-template chatml`**: o
  template do GGUF é ignorado e o prompt é renderizado do lado Go, pelo template
  do registry. Ou seja, o comportamento de tool-calling que você mediu é o do
  template do registry — que é o que as issues acima dizem estar quebrado para
  Qwen.

**Antes de trocar de modelo por causa disso, vale um teste barato:**
`ollama show --template qwen2.5:14b` e comparar com o template oficial da Qwen;
e repetir o A/B de tool-calling contra o mesmo modelo com as ferramentas
embutidas no system prompt como JSON (o workaround de #14601) em vez do parâmetro
`tools`. Se a taxa subir, o veredito "é o modelo" precisa ser revisado.

---

## 3. Plano de medição reaproveitando o `run_chat.py`

Objetivo: números de GPU **comparáveis lado a lado** com os de CPU que já existem
em `RELATORIO_CONSOLIDADO.md`. Não é um benchmark novo — é o mesmo harness, o
mesmo goldset de 18 casos, o mesmo `system_prompt.txt` (sha256 `11f95bf9…`).

### Regras de comparabilidade

1. **Uma variável por run.** `OUT_SUFFIX` descreve a variável, não o modelo.
2. **Manter `THINK=false`** — como em todas as runs de CPU.
3. **`NUM_PARALLEL=1`** durante a medição, como no relatório de CPU.
4. **Registrar o estado do servidor** junto do resultado: versão do Ollama, env
   vars efetivas, e a linha `cmd=` do `llama-server` no journal. Sem isso, uma
   run de daqui a três semanas não é comparável.
5. **Janela dedicada.** O serviço atende 4 projetos. Medição concorrente com
   tráfego real invalida o tok/s e prejudica os clientes.

### Dois ajustes mínimos no harness

O `run_chat.py` hoje grava só a fase de geração:

```python
eval_count = body.get("eval_count", 0)
eval_dur_ns = body.get("eval_duration", 0) or 0
tok_s = (eval_count / (eval_dur_ns / 1e9)) if eval_dur_ns else 0.0
```

**(a) Capturar o prefill.** Metade das alavancas desta pesquisa (`-ub`, NVFP4,
flash attention, num_ctx) atua no prompt processing, que o harness não mede hoje.
O `/api/chat` já devolve os campos:

```python
prompt_eval_count = body.get("prompt_eval_count", 0)
prompt_eval_dur_ns = body.get("prompt_eval_duration", 0) or 0
prefill_tok_s = (prompt_eval_count / (prompt_eval_dur_ns / 1e9)) if prompt_eval_dur_ns else 0.0
ttft_s = (prompt_eval_dur_ns + (body.get("load_duration", 0) or 0)) / 1e9
```

**(b) Carimbar a configuração.** No topo do `chat_raw*.json`, gravar um bloco com
`OLLAMA/api/version`, as options enviadas, e as env vars relevantes lidas do
ambiente. Custo: ~15 linhas. Sem isso, a procedência dos números se perde como
se perdeu a da Ryzen 3800X no relatório anterior.

### Matriz de runs

**Fase 0 — linha de base congelada (antes de mexer em qualquer coisa)**

Roda a configuração *como está agora*, para ter o "antes" honesto:

```bash
MODELS_OVERRIDE="qwen3:14b,qwen3.5:9b,qwen2.5:14b" THINK=false \
  OUT_SUFFIX=".gpu5090-baseline" \
  OLLAMA_URL=http://100.88.95.78:11434 python3 run_chat.py
```

Isto sozinho já responde a pergunta central do upgrade: **quanto a GPU muda o
tok/s dos modelos que você já roda**, contra os 7,2 tok/s do qwen2.5:14b na i7.

**Fase 1 — configuração do servidor** (uma variável por vez, requer restart da unit)

| # | Variável | Runs | O que responde |
|---|---|---|---|
| 1 | runner CUDA | `cuda_v12` (atual) vs sem `OLLAMA_LLM_LIBRARY` (auto → cuda_v13) | A var forçada custa performance? Vale removê-la? |
| 2 | `OLLAMA_CONTEXT_LENGTH` | 32768 (herdado) vs 8192 | Quanto o contexto default custa em VRAM e em tempo de carga |
| 3 | `OLLAMA_KV_CACHE_TYPE` | `f16` vs `q8_0` | O auto_score cai? (esperado: não em Qwen) |
| 4 | `OLLAMA_MAX_LOADED_MODELS` | 1 vs 2 | Elimina os 25 s de recarga sem regressão? |
| 5 | power limit | 600 W vs 400 W | Confirma o −1,2% em decode na sua placa |

**Fase 2 — modelos novos** (config vencedora da Fase 1 congelada)

```bash
MODELS_OVERRIDE="gemma4:26b,qwen3.6:27b,qwen3.6:35b-a3b,qwen3.8:27b" \
  THINK=false OUT_SUFFIX=".gpu5090-novos" python3 run_chat.py
```

O fine-check de escalação do §8 do relatório anterior (token exato caractere a
caractere nos 4 casos que devem escalar e nos 5 traps) continua sendo o critério
que elimina modelo — o `auto_score` médio esconde MISS e LEAK.

**Fase 3 — tool-calling** (fora do `run_chat.py`)

O goldset da Lana não testa tool-calling; os seus A/B de setembro testam. Vale
um harness irmão, com o mesmo formato de saída, cobrindo:

- os 12 casos de tool-calling e os 8 de structured output que você já rodou;
- **e o controle de §2k**: mesmos casos com as ferramentas no system prompt como
  JSON em vez do parâmetro `tools`, para separar modelo de template.

### Ordem sugerida das ações

1. **Fase 0** — congela o "antes". Nada muda na infra.
2. **Decidir `OLLAMA_CONTEXT_LENGTH`** explicitamente (hoje herdado, 32k).
3. **Medir `cuda_v12` vs auto/`cuda_v13`** e remover a var se o auto ganhar ou
   empatar — ela é resíduo de um workaround já resolvido.
4. **`MAX_LOADED_MODELS=2`** — provável maior ganho de latência percebida.
5. **Fase 2**, com `gemma4:26b` como primeiro candidato (menor risco: já
   validado no seu goldset, `Modelfile.lana` pronto).
6. **Fase 3 / §2k** antes de qualquer decisão de trocar modelo por tool-calling.

---

## 4. Fontes

**Primárias / com metodologia publicada**
- llama.cpp — scoreboard CUDA (5090, FA on/off, power limit): https://github.com/ggml-org/llama.cpp/discussions/15013
- llama.cpp — 5090 vs R9700, Qwen3.5-35B-A3B, flags publicadas: https://github.com/ggml-org/llama.cpp/discussions/19890
- llama.cpp — batch vs ubatch: https://github.com/ggml-org/llama.cpp/discussions/6328
- llama.cpp — kernels NVFP4: PR [#20644](https://github.com/ggml-org/llama.cpp/pull/20644), [#21074](https://github.com/ggml-org/llama.cpp/pull/21074)
- Ollama — context length por VRAM: https://docs.ollama.com/context-length
- Ollama — FAQ (KV cache types, num_parallel, keep_alive): https://docs.ollama.com/faq
- Ollama — MTP só no runner MLX: https://github.com/ollama/ollama/pull/15980
- Ollama — issues de tool-calling/sampler: [#14601](https://github.com/ollama/ollama/issues/14601), [#14493](https://github.com/ollama/ollama/issues/14493), [#15783](https://github.com/ollama/ollama/issues/15783)
- vLLM — NVFP4 em sm_120: https://github.com/vllm-project/vllm/issues/47749
- Gemma 4 26B-A4B — model card e technical report: https://huggingface.co/google/gemma-4-26B-A4B · https://arxiv.org/pdf/2607.02770
- Qwen3.8-27B — arquitetura e sampling recomendado: https://huggingface.co/Qwen/Qwen3.8-27B-FP8
- KV cache quantization, KL divergence: https://localbench.substack.com/p/kv-cache-quantization-benchmark
- NVFP4 no Ollama restrito a macOS: https://forums.developer.nvidia.com/t/ollama-with-nvfp4-support/365286
- Puget Systems, WSL2 vs Linux (CPU only — citado para dizer que **não** cobre GPU): https://www.pugetsystems.com/labs/hpc/wsl2-vs-linux-hpl-hpcg-namd-2354/

**Primárias desta máquina** (coletadas por SSH, read-only, 2026-09-04)
- `nvidia-smi` via `/usr/lib/wsl/lib/`
- `journalctl --user -u content-insights-ollama.service`
- `systemctl --user cat content-insights-ollama.service`
- `GET /api/tags`, `/api/ps`, `/api/version` em `100.88.95.78:11434`
