# Índice de sessões — o histórico de chat por trás deste diretório

Levantado em **2026-09-04** com `/search-sessions`. Serve para recuperar o
raciocínio que não virou arquivo: por que uma decisão foi tomada, o que foi
medido e descartado, quem eram os interlocutores.

## Retenção — leia antes de procurar

O histórico local do Claude Code (`~/.claude/projects/`) **só retém desde
2026-06-30**. Duas coisas importantes ficaram de fora:

- as sessões de **maio/2026** que produziram o harness `run_chat.py`, o gold set
  e o `RELATORIO_CONSOLIDADO.md` — sobraram só os arquivos, em
  `~/Devs/contabil-ollama/llm-bench/`;
- o benchmark de tok/s **3080 Ti × MacBook Pro M5 Pro de 25/03/2026**, que nunca
  foi salvo em arquivo.

É a razão de este diretório existir: resultado versionado em `results/`, não em
scrollback.

## Sessões vivas

| Sessão | cwd | O que tem |
|---|---|---|
| `43f68058-337d-4e8a-9da0-44ad61102744` | `~` | **A principal.** 01–02/09: Ryzen9 vira o único servidor Ollama, `OLLAMA_HOST` de loopback para `0.0.0.0`, acesso por Tailscale, Open WebUI, e os A/B de tool-calling e saída anômala congelados em `baseline-3080ti/` |
| `1e802568-fdff-40fa-983a-8720b314f76e` | `~` | 08/08: auditoria das três máquinas e plano de migração — origem de `~/Projects/HomeLab/specs.md` e `migration-master-plan.md` |
| `36ed92b7-7332-4d95-90e9-4db426957b70` | `~/Devs/llm-gateway` | Providers, perfis e governança do gateway |
| `b5f69d18-1f77-42f2-8787-0ce8671c700e` | `~/Devs/Khronos/DRE` | Consumidor DRE: tool-calling, dado financeiro não sai da rede |
| `45bdf118-0eab-42aa-864c-69f2e712d84a` | `~/Devs/miqueias/MFC` | Consumidor MFC: timeout de 180 s e o custo de recarga do `MAX_LOADED_MODELS=1` |
| `d4fd9b7f-dd5e-4f59-a23b-25989d2de04b` | `~/Devs/acervo` | Consumidor acervo: `OllamaReasoner`, e o achado do Grok fora da governança |
| `7e01f566-4e6a-4375-beb5-422b608cc700` | `~` | 19/08: papéis das máquinas do lab, migração de trading Ryzen7 → Ryzen9 |
| `8777e648-2fe2-4def-8dcf-1b2dda98d8da` | `~` | 04/09: o levantamento que produziu este índice |

Retomar qualquer uma:

```bash
cd <cwd> && claude -r <uuid>
```

Buscar dentro do histórico sem abrir sessão:

```bash
search-sessions "<termo>" --deep
```

## Onde está cada coisa

| Pergunta | Arquivo |
|---|---|
| O que roda aqui e como | [`README.md`](README.md) |
| Modelos para 30 GiB, parametrização da Blackwell, plano de medição | [`rtx5090-modelos-parametrizacao.md`](rtx5090-modelos-parametrizacao.md) |
| Por que o servidor saiu do WSL2 | [`MIGRACAO-windows-nativo-2026-09-04.md`](MIGRACAO-windows-nativo-2026-09-04.md) |
| Tudo da placa anterior, congelado | [`baseline-3080ti/`](baseline-3080ti/) |
| Qualidade em CPU (i7, maio/2026) | `~/Devs/contabil-ollama/llm-bench/results/RELATORIO_CONSOLIDADO.md` |
