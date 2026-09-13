#Requires -RunAsAdministrator
param(
  [ValidatePattern('^\d*$')]
  [string]$CtxLength,   # "" ou vazio = nao definida (auto); senao numero
  [ValidatePattern('^\d*$')]
  [string]$MaxLoaded,   # "1","2","3"
  [ValidateSet('', 'q8_0', 'q4_0')]
  [string]$KvCache,     # "" = nao definida (f16); ou "q8_0"
  [ValidatePattern('^\d*$')]
  [string]$NumParallel,  # "" = nao definida (default do Ollama); "1","2",...
  [ValidateSet('', '0', '1')]
  [string]$FlashAttention  # "" = nao definida (default); "1" = ligado; "0" = desligado
)
$ErrorActionPreference = 'Stop'

function Set-OrClear($name, $value) {
  if ([string]::IsNullOrEmpty($value)) {
    [Environment]::SetEnvironmentVariable($name, $null, 'Machine')
  } else {
    [Environment]::SetEnvironmentVariable($name, $value, 'Machine')
  }
}

Set-OrClear 'OLLAMA_CONTEXT_LENGTH'    $CtxLength
Set-OrClear 'OLLAMA_MAX_LOADED_MODELS' $MaxLoaded
Set-OrClear 'OLLAMA_KV_CACHE_TYPE'     $KvCache
Set-OrClear 'OLLAMA_NUM_PARALLEL'      $NumParallel
Set-OrClear 'OLLAMA_FLASH_ATTENTION'   $FlashAttention

Write-Output "=== aplicado ==="
foreach ($v in 'OLLAMA_CONTEXT_LENGTH','OLLAMA_MAX_LOADED_MODELS','OLLAMA_KV_CACHE_TYPE','OLLAMA_NUM_PARALLEL','OLLAMA_FLASH_ATTENTION') {
  Write-Output ("  $v = " + [Environment]::GetEnvironmentVariable($v,'Machine'))
}

Write-Output "=== reiniciando (stop mata o processo inteiro; supervisor.cmd nao herda env novo se so o ollama.exe cair) ==="
Stop-ScheduledTask -TaskName 'OllamaServer'

# CRITICO, ordem importa: mata o supervisor (cmd.exe do run-ollama.cmd) ANTES
# de 'ollama'/'llama-server'. Ele tem um loop de 5s que resobe o ollama.exe se
# ele morrer primeiro -- com o AMBIENTE ANTIGO, podendo vencer a corrida
# contra o Start-ScheduledTask abaixo e segurar a porta 11434 com a config
# errada (o health check no fim so prova que ALGUEM responde em 11434, nao
# que e a instancia nova -- achado de revisao, rodada llm-bench-4).
$supervisores = Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" |
  Where-Object { $_.CommandLine -like '*run-ollama.cmd*' }
$supervisores | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# mata tambem 'ollama' e 'llama-server' -- o worker de inferencia real. Matar
# so 'ollama' deixa o llama-server orfao segurando a VRAM -- confirmado em
# 2026-09-04: 7 zumbis acumulados, GPU caiu para 252 MiB livres de 32 GiB.
# ATENCAO: isto mata por NOME em toda a maquina, nao so a arvore da tarefa --
# se houver uma instancia de bancada rodando em paralelo (ex.: portas 11435/
# 11436, ver results/RESULTADO-wsl-vs-windows-2026-09-04.md), ela morre junto.
$alvos = @(Get-Process -Name 'ollama','llama-server' -ErrorAction SilentlyContinue)
if ($alvos.Count -gt 0) {
  Write-Output ("  matando " + $alvos.Count + " processo(s) chamado(s) 'ollama'/'llama-server' " +
                "em toda a maquina (nao filtrado por tarefa) -- PIDs: " + ($alvos.Id -join ', '))
  $alvos | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
}

# espera de verdade os processos sumirem (ate 15s), em vez de um sleep fixo
# as cegas -- fecha parte da janela de corrida do achado acima
$deadlineKill = (Get-Date).AddSeconds(15)
do {
  Start-Sleep -Milliseconds 500
  $restantes = @(Get-Process -Name 'ollama','llama-server' -ErrorAction SilentlyContinue)
} while ($restantes.Count -gt 0 -and (Get-Date) -lt $deadlineKill)
if ($restantes.Count -gt 0) {
  Write-Output "  [aviso] processo(s) ainda de pe apos 15s de espera -- seguindo mesmo assim"
}

Start-ScheduledTask -TaskName 'OllamaServer'
Start-Sleep -Seconds 8

$deadline = (Get-Date).AddSeconds(30)
$ok = $false
do {
  try {
    Invoke-WebRequest "http://127.0.0.1:11434/api/version" -UseBasicParsing -TimeoutSec 3 | Out-Null
    $ok = $true
  } catch { Start-Sleep -Seconds 2 }
} while (-not $ok -and (Get-Date) -lt $deadline)

Write-Output "=== confirmacao no log ==="
Get-Content "C:\ProgramData\ollama-server\ollama.log" -Tail 60 |
  Select-String -Pattern 'server config|vram-based default context' |
  Select-Object -Last 2 | ForEach-Object { $_.Line }

if (-not $ok) {
  Write-Output "AINDA FORA DO AR apos 30s"
  exit 1
}

$taskState = (Get-ScheduledTask -TaskName 'OllamaServer').State
if ($taskState -ne 'Running') {
  Write-Output ("servidor respondeu em /api/version, mas a tarefa 'OllamaServer' " +
                "nao esta 'Running' (estado: $taskState) -- pode ser outra instancia " +
                "respondendo na porta, com a config antiga")
  exit 1
}

Write-Output "servidor no ar (tarefa 'OllamaServer': $taskState)"
