# Metodologia e reprodução

**Português** | [English](en/methodology.md)

O [catálogo de experimentos](rtx5090/experimentos.md) descreve o desenho e as
ressalvas de cada medição. Esta página orienta a leitura e novas execuções;
a publicação do acervo não reexecutou inferência.

## Métricas que não devem ser confundidas

| Métrica | Definição e limite |
|---|---|
| Decode, tok/s | `eval_count / (eval_duration / 1e9)`; mede a geração, sem tempo de carga ou prefill. |
| Prefill, tok/s | `prompt_eval_count / (prompt_eval_duration / 1e9)`; prompts curtos e cache podem dominar essa medida. |
| Wall time | Tempo observado pelo cliente, inclui espera e demais custos. A/B de fila não equivale a A/B de decode. |
| Carga fria | Duração de carregar o modelo; separar de warmup e chamadas com modelo residente. |
| `auto_score` | Fração dos checks aplicáveis aprovados. Régua mudou em 10/09; não agregar versões diferentes. |
| Escalação | Presença do token comparada a `expect_escalation` em conjunto rotulado. LEAK e MISS têm impactos diferentes. |
| Contrato multirrodada | Inclui valor correto, protocolo, fontes e proveniência; acertar o valor sozinho não basta. |
| Idioma | Heurística por marcadores; `tie` aceito não demonstra idioma correto. Ver [PT→EN](achados/ACHADO-qwen3-14b-idioma-template-2026-09-12.md). |

A [baseline antiga](../baseline-3080ti/baseline-3080ti.md) divide tokens pelo
tempo total, que inclui prefill. Compará-la diretamente ao decode puro da 5090
produz uma razão enviesada. O throughput de uma GPU não é dedutível da
posição de um arquivo no diretório.

## Verificação offline

```bash
python3 tools/inventory.py check
```

O comando valida SHA-256, tamanho e lista de evidências; lê JSONs; confere links
relativos para arquivos da documentação nova. Não acessa Ollama nem importa
harness de inferência. O manifesto é um registro de integridade dos bytes,
não uma classificação de validade experimental.

Para incorporar novas evidências, primeiro inspecione os arquivos adicionados,
registre seu método e resultado, depois atualize o manifesto:

```bash
python3 tools/inventory.py update
python3 tools/inventory.py check
```

O `update` não deve ser usado para esconder alteração acidental em dado histórico.
As correções devem indicar quais conclusões substituem. Use o
[template de experimento](templates/experimento.md).

## Executar uma nova medição

Estas instruções fazem chamadas reais ao servidor. Em uma bancada compartilhada,
combine a janela e registre a configuração antes de iniciar; veja
[infraestrutura](infraestrutura.md). Os exemplos não reiniciam o servidor.

### Qualidade de atendimento

`run_chat.py` usa apenas a biblioteca padrão. Informe modelos explicitamente:
os defaults internos são herança da campanha antiga e não representam a
configuração de produção de setembro.

```bash
OLLAMA_URL=http://127.0.0.1:11434 \
MODELS_OVERRIDE=qwen3:14b THINK=false \
OUT_SUFFIX=.minha-medicao-001 python3 run_chat.py
```

Escolha um `OUT_SUFFIX` ainda não usado: o runner grava
`results/chat_raw<SUFIXO>.json` e `results/chat_table<SUFIXO>.md` e pode sobrescrever
uma execução com o mesmo sufixo. Registre hashes do prompt, goldset e runner
antes da chamada; seu estado atual não reconstrói automaticamente a régua antiga.

As opções atuais do runner são `temperature=0.7`, `num_ctx=8192`, `seed=42`.
Uma única execução dos 18 casos é triagem. Repetir seed não é sinônimo de
amostras independentes, e a mesma seed mudou de resultado entre sessões no
[experimento de reamostragem](../results/RESULTADO-reamostra-qwen3-14b-2026-09-08.md).

### Throughput de geração

`bench.py` depende de `requests`, declarado em [requirements.txt](../requirements.txt).
Seu endpoint está fixado em `http://localhost:11434`; a variável `OLLAMA_URL`
**não** muda esse runner. A captura de GPU tenta `powershell.exe` com `nvidia-smi`
e registra erro se não estiver disponível. Isso não comprova a GPU de um
endpoint remoto; registre o hardware do servidor separadamente.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python bench.py qwen3:14b
```

Sempre passe a lista pretendida: sem argumentos ele enumera todos os modelos
instalados, podendo trocar os residentes. O teste usa três prompts e duas
execuções por prompt, salva `results/bench_<timestamp>.json`, e não tem warmup
separado nem avaliação do conteúdo gerado.

### A/B de endpoints

```bash
ENDPOINT_A=http://127.0.0.1:11434 LABEL_A=controle \
ENDPOINT_B=http://127.0.0.1:11435 LABEL_B=candidato \
MODEL=qwen3:8b REPS=5 NUM_CTX=8192 python3 bench_engine_ab.py
```

É necessário preparar os endpoints antes. O runner alterna A/B em série,
descarta warmup e fixa opções. Dois servidores disputando a mesma GPU em
paralelo confundiriam o experimento. Versão de runtime e contexto precisam ser
registrados; a medição WSL/Windows preservada tinha versões distintas de Ollama.

### Harnesses das fases

Consulte o [catálogo](rtx5090/experimentos.md) para os scripts e raws específicos.
A localização `baseline-3080ti/repro/` foi preservada porque os scripts resolvem
caminhos relativos até a raiz. Alguns dependem de SSH, PowerShell ou do checkout
externo `llm-gateway`; o arquivo existir não garante reprodução autossuficiente.
O comparador offline de juízes histórico contém caminho absoluto e sobrescreve
seu artefato de saída. Para apenas ler o acervo, use o inventário acima.

## Regras para conclusões novas

1. Declare hipótese, carga, unidade de análise, versões, hashes e critérios de
   sucesso antes de medir. Diferencie amostras de perguntas, seeds e execuções.
2. Guarde resposta completa, erros, latência e contagens efetivas. Um preview
   cortado não sustenta ausência de token ou de evidência.
3. Relate denominadores e exclusões. Erros HTTP não viram respostas corretas;
   conjunto rotulado não reproduz o problema sem rótulo da produção.
4. Verifique residência e truncamento. Para modelos especulativos, `/api/ps`
   sozinho não valida toda a VRAM. Número coincidente não identifica causa.
5. Compare com controles e distribua o teste por pergunta. Nove perguntas
   gerando 196 pares não produzem 196 observações independentes.
6. Preserve resultado invalidado com sua correção identificada. Duas revisões
   com os mesmos revisores são uma amostra revisada duas vezes.

Esses cuidados derivam dos [achados desta bancada](rtx5090/achados.md), não são
uma alegação de que todos os experimentos históricos os cumpriram integralmente.
