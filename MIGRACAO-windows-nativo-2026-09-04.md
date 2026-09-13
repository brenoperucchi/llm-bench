# Migração do Ollama: WSL2 → Windows nativo — 2026-09-04

O servidor Ollama do Ryzen9 saiu do WSL2 e passou a rodar no **Windows nativo,
como tarefa agendada do SYSTEM que sobe no boot**. O endereço não mudou —
`192.168.0.125:11434` (LAN) e `100.88.95.78:11434` (tailnet) seguem valendo, e
nenhum cliente precisou ser reconfigurado.

Motivo: o [A/B de hoje](results/RESULTADO-wsl-vs-windows-2026-09-04.md) mediu
**~14% a mais de decode** no Windows nativo (225,8 contra 199,7 tok/s no
qwen3:8b), com prefill e TTFT empatando. Medido depois no servidor migrado, em
produção: **225,9 tok/s** — o ganho se confirmou.

## Antes e depois

| | Antes (WSL2) | Depois (Windows nativo) |
|---|---|---|
| processo | `ollama serve` sob systemd de usuário | `ollama.exe serve` sob tarefa agendada |
| unit / tarefa | `content-insights-ollama.service` | Tarefa `OllamaServer` |
| usuário | `brenoperucchi` (WSL) | `NT AUTHORITY\SYSTEM` |
| sobe quando | a distro WSL inicia | **no boot**, sem depender de login |
| versão | 0.33.2 | 0.33.3 |
| runner | `cuda_v12` (forçado) | `cuda_v13` (auto-detect) |
| store | `~/.ollama/models` (ext4, 40 GB) | `C:\Users\Breno Perucchi\.ollama\models` (78 GB) |
| logs | `journalctl --user -u …` | `C:\ProgramData\ollama-server\ollama.log` |
| modelos | 8 | **14** |

O parque cresceu porque o Windows já tinha um store antigo que o WSL não tinha.
Os dois foram fundidos (`rsync`, dedupe por sha256 — 42,6 GB em 5m29):

- **veio do WSL:** `qwen3:14b`, `qwen3.5:9b`, `qwen3:8b`, `gemma3n:e2b`,
  `ministral-8b:latest` e o GGUF do HF;
- **já estava no Windows:** `qwen3:30b-a3b` (MoE), `llama3.2-vision:11b` (a régua
  do Track B de OCR), `contabil:latest` (custom), `qwen2.5-coder:14b`,
  `dolphin-llama3:8b`, `nomic-embed-text`.

> `ministral-8b:latest` e `contabil:latest` são **aliases locais** — não existem
> no registry público. Foram copiados, não rebaixados; um `ollama pull` os teria
> perdido.

## Como operar agora

```powershell
# estado
Get-ScheduledTask -TaskName OllamaServer | Select-Object State      # deve ser Running
Get-NetTCPConnection -LocalPort 11434 -State Listen

# parar / iniciar — NUNCA só Stop-ScheduledTask, ver aviso abaixo
Stop-ScheduledTask -TaskName OllamaServer
Get-Process -Name 'ollama','llama-server' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3
Start-ScheduledTask -TaskName OllamaServer

# logs
Get-Content C:\ProgramData\ollama-server\ollama.log -Tail 50
Get-Content C:\ProgramData\ollama-server\supervisor.log -Tail 20
```

> ⚠️ **`Stop-ScheduledTask` sozinho não mata `llama-server.exe`.** Descoberto
> na Fase 1 de parametrização (2026-09-04): `Stop-ScheduledTask` mata o
> `cmd.exe`/`ollama.exe` da tarefa, mas o worker de inferência real
> (`llama-server.exe`, quem carrega os pesos e segura o contexto CUDA) fica
> **órfão, segurando a VRAM indefinidamente**. Cinco reinícios seguidos sem
> matar `llama-server` acumularam **7 processos zumbis** e derrubaram a VRAM
> livre de 31,8 GiB para 252 MiB — sem aparecer em
> `nvidia-smi --query-compute-apps` (os zumbis não contam como "compute app"
> mas continuam presos à memória). Isso chegou a ser confundido com um crash
> de CUDA em outro teste, porque a memória presa faz cargas legítimas
> falharem por "falta" de VRAM que na verdade está disponível, só que vazada.
> **Sempre mate `ollama` e `llama-server` juntos antes de reiniciar** — o
> comando acima já faz isso. Script pronto:
> [`ollama-restart.ps1`](ollama-restart.ps1).

Do WSL ou de qualquer máquina da tailnet, o servidor continua acessível como antes:

```bash
curl http://100.88.95.78:11434/api/version
```

### Configuração

Variáveis no escopo **Machine** (SYSTEM tem outro `%USERPROFILE%`, por isso o
store vai com caminho absoluto):

```
OLLAMA_HOST              = 0.0.0.0:11434
OLLAMA_MODELS            = C:\Users\Breno Perucchi\.ollama\models
OLLAMA_KEEP_ALIVE        = 5m
OLLAMA_NUM_PARALLEL      = 1
OLLAMA_MAX_LOADED_MODELS = 1
```

Paridade deliberada com a unit que saiu: o cutover mudou **uma** variável (o SO),
não cinco. Os ajustes pendentes — contexto explícito e `MAX_LOADED_MODELS=2` —
entram depois, medidos um a um, senão não dá para atribuir regressão.

`OLLAMA_LLM_LIBRARY` ficou **de fora de propósito**: o A/B mediu empate entre
`cuda_v12` e `cuda_v13`, então forçar o runner só mascara o auto-detect. A unit
antiga está preservada em
[`baseline-3080ti/content-insights-ollama.service.txt`](baseline-3080ti/content-insights-ollama.service.txt).

## Três coisas que só apareceram executando

**1. O app de bandeja rouba a porta.** O instalador do Windows deixa um
`Ollama.lnk` na pasta Startup; ele sobe `ollama app.exe`, que por sua vez sobe um
`ollama.exe serve` — e esse ganhou a corrida pela 11434, fazendo a tarefa do
SYSTEM falhar com `bind: Only one usage of each socket address`. Durante um bom
tempo o servidor no ar era o **do usuário logado**, não a tarefa de boot — o que
derrotaria o objetivo inteiro. O atalho foi removido.

**2. `-RestartCount` do Task Scheduler não cobre processo morto por fora.**
Matando o `ollama.exe`, a tarefa foi para `Ready` com `LastTaskResult=-1` e o
serviço ficou fora do ar — não reiniciou. A supervisão real está num loop dentro
do `run-ollama.cmd`: se o Ollama sair por qualquer motivo, sobe de novo em 5 s e
a tarefa segue `Running`. **Validado**: processo morto às 12:25:11, de volta às
12:25:16 com pid novo.

**3. CUDA funciona em session 0.** Era o risco que poderia inviabilizar o boot
sem login — GeForce sob WDDM nem sempre é visível para serviços. Testado numa
porta isolada antes do cutover: `library=CUDA compute=12.0 … RTX 5090 …
available="30.3 GiB"`. Funcionou.

## Por que tarefa agendada e não um Windows Service

Decidido em 2026-09-04, depois de pesquisar as alternativas: **fica a tarefa
`OllamaServer`**.

O `ollama.exe` **não implementa a interface do Service Control Manager**, então
não existe "Ollama service" nativo — o SCM não consegue iniciá-lo nem monitorá-lo,
e é por isso que ele nunca aparece em `services.msc`. A issue
[ollama#4658](https://github.com/ollama/ollama/issues/4658) pedindo suporte
nativo está aberta desde maio/2024; a
[#10713](https://github.com/ollama/ollama/issues/10713) relata a mesma ausência.
Qualquer serviço de verdade passa por um wrapper de terceiro:

| Wrapper | Estado | Nota |
|---|---|---|
| NSSM 2.24 | **abandonado** (último release em 2014) | é o que a [doc oficial](https://docs.ollama.com/windows) recomenda, mas a issue [#11962](https://github.com/ollama/ollama/issues/11962) relata falha com Ollama > 0.10.0 (registro apontando para o `nssm.exe`) |
| [WinSW](https://github.com/winsw/winsw) | mantido | XML + rotação de log; v3 ainda em alpha |
| [Shawl](https://github.com/mtkennerly/shawl) | mantido | binário Rust único, restart nativo — a melhor das três se um dia for preciso |

A tarefa agendada entrega o que importa (boot sem login, SYSTEM, GPU, restart do
Ollama em 5 s) sem instalar dependência nova. O que um serviço acrescentaria é
ergonomia — aparecer em `services.msc`, `Restart-Service`, dependências
declaradas — e não capacidade.

**Fraqueza aceita conscientemente:** o loop protege contra o `ollama.exe` morrer,
mas não contra o **próprio wrapper** (`cmd.exe`) morrer; nesse caso o serviço fica
fora do ar até o próximo boot. Se isso acontecer na prática, há duas saídas, em
ordem de custo: adicionar um gatilho recorrente à tarefa (`MultipleInstances` já
está em `IgnoreNew`, então uma instância extra é descartada quando já está
rodando), ou migrar para Shawl.

## Validação do cutover

- `/api/version` e `/api/tags` pela **tailnet** e pela **LAN**: OK, 14 modelos
- inferência real em `qwen3:14b` e `qwen3.5:9b` pela tailnet: OK
- `ollama ps`: modelo 100% em VRAM (`size_vram == size`), sem spill
- throughput: **225,9 tok/s** no qwen3:8b, batendo o A/B
- `llm-gateway` no omarchy: `{"status":"ok"}`, listando modelos
- supervisão: processo morto voltou sozinho em 5 s
- WSL: unit parada, desabilitada e removida; store e binário apagados
  (**42 GB liberados**, 81G → 39G)

## Pendências

1. ~~Reboot ainda não testado.~~ **Validado em 2026-09-04 15:03.** A máquina
   reiniciou e o servidor subiu sozinho, sem login:

   | | |
   |---|---|
   | 15:03:37 | boot do Windows |
   | 15:03:47 | tarefa `OllamaServer` dispara (+10 s) |
   | 15:03:48 | `supervisor.log`: "iniciando ollama serve" |
   | 15:04:15 | GPU detectada: `RTX 5090 … cuda_v13 … available="30.3 GiB"` |

   Cadeia de processos conforme o desenho —
   `cmd.exe /c run-ollama.cmd` → `ollama.exe` (pid 10656), como
   `NT AUTHORITY\SYSTEM`. Wrapper e supervisão ativos após o boot; CUDA
   funcionando em session 0 no cenário real, não só no teste isolado.
2. **Observabilidade regrediu.** Não há mais `journalctl`: o equivalente é
   `C:\ProgramData\ollama-server\*.log`, sem rotação, sem índice por unidade e
   sem histórico de boots. Se crescer demais, vai precisar de rotação.
3. **`OLLAMA_HOST=0.0.0.0:11434` no escopo Machine deixou de ser risco e virou
   requisito** — é o que faz a tarefa expor o servidor na rede. Antes era uma
   armadilha (colidia com o WSL); agora é a configuração correta.
4. Os ajustes de tuning ainda não aplicados: contexto explícito (hoje o default
   por VRAM dá 32k) e `MAX_LOADED_MODELS=2`.
5. **Incidente de conectividade — 2026-09-05, causa não identificada, provável
   lado do cliente.** Em algum momento desta sessão, a porta 11434 parou de
   responder a partir da sessão do Claude Code que operava este projeto — nem
   pelo IP da tailnet (`100.88.95.78`) nem pelo da LAN (`192.168.0.125`).
   Diagnóstico descartou o servidor (saudável via `127.0.0.1` na própria
   máquina, inclusive testado com `Test-NetConnection` da própria máquina para
   seu próprio IP de LAN — sucesso) e descartou o Windows Firewall (regra
   `Ollama API` intacta, `Enabled=True`, `Profile=Any`). SSH (porta 22)
   continuou funcionando o tempo todo, dos dois lados. Contorno adotado:
   túnel SSH local (`ssh -L 11434:127.0.0.1:11434 ...`) — os scripts de
   reprodução deste repo (`fase3_ab_template.py`, `fase6_concurrency.py`)
   passaram a apontar pro túnel por padrão. **Fica sem explicação root-cause**;
   se a porta voltar a responder direto numa sessão futura, os scripts aceitam
   `OLLAMA_URL` pra usar o caminho direto de novo.
6. **Store movido para o SSD novo em E: — 2026-09-07.** `OLLAMA_MODELS` saiu de
   `C:\Users\Breno Perucchi\.ollama\models` para **`E:\ollama\models`**, e o
   store avulso em `D:\ollama-overflow\models` (criado em 05/09 quando o
   `deepseek-r1:32b` não coubera em C:) foi **consolidado no mesmo destino** —
   blobs são endereçados por hash, então os dois stores se fundiram sem
   colisão: 93 + 6 = 99 arquivos, 160,48 + 18,49 = 178,97 GB, conferido dos
   dois lados. Com isso a **instância secundária na porta 11435 deixou de ser
   necessária**: o `deepseek-r1:32b` voltou a ser um modelo comum do servidor
   principal.

   Método, para repetir: cópia **a quente** com o servidor no ar (robocopy
   `/E /COPY:DAT /MT:16`), depois parada curta para re-sync delta + troca da
   variável + restart. **Downtime real: 7,1 s.** A ordem de kill é a mesma do
   `ollama-restart.ps1` (supervisor antes dos filhos). Log em
   `C:\ProgramData\ollama-server\move-to-e.log`.

   **As cópias antigas em C: e D: foram deixadas intactas como rollback** —
   apagar só depois de decidir que não são mais necessárias.

   **Ganho medido do disco novo: leitura sequencial 1,27× (2.895 → 3.670 MB/s,
   +26,8%)**, medido com leitura sem buffer (`FILE_FLAG_NO_BUFFERING`) do mesmo
   blob de 18,88 GB nos dois discos, alternando por repetição e variando o
   offset para não reaproveitar cache do SSD; n=4, mediana. O C: mede
   notavelmente estável (±0,5%) e o E: varia bastante (3.158–4.024 MB/s), causa
   não investigada. **Isso não se traduz em 27% de carga de modelo mais
   rápida** — carga inclui transferência pra VRAM, alocação de KV e trabalho de
   CPU, que não mudaram; a fração disco/resto não foi medida. Uma primeira
   comparação por `load_duration` foi feita e **descartada por inválida**
   (unload silencioso que não ocorria, configs diferentes entre as instâncias e
   variância de 9× — ver `baseline-3080ti/repro/disco_ab_load.py`, mantido só
   como registro do que não fazer).
