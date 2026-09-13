# Relatos originais dos 4 agentes (fonte da revisão publicada)

Coletados em 2026-09-02 com a mesma pergunta em 4 blocos: problemas enfrentados,
resolvidos, pendente/contornado, onde está registrado.

ATENÇÃO REVISOR: os relatos de `acervo-exec`, `content-insights-collector-exec` e
`mfc-exec` abaixo foram lidos da tela dos panes (`herdr agent read`), que é
lossy e pode ter truncado partes. O de `dre-exec` chegou completo. Se um ponto do
artifact não tiver respaldo aqui, isso pode ser truncamento da minha leitura —
mas também pode ser afirmação minha sem fonte. Assinale como suspeita.

---

## dre-exec (relato completo)

PROBLEMAS: (a) tool-calling quebrado no perfil local, 400 "Value looks like
object" — causa no gateway, arguments normalizado para string na saída e não
aceito de volta. (b) modelo erra recorte de período: pergunta mar/26, consultou
mar/25, R$ 161,7M em vez de R$ 34,1M, com qwen3:14b e llama3.2 — causa no lado
dele, delegava ao modelo decisão que o código sabia tomar. (c) alucinação sem
consulta: qwen2.5:14b não chamou ferramenta e inventou R$ 12.345.678. (d)
estrutura duplicada: respondeu receita bruta quando perguntaram líquida, porque
"(=) Receita Líquida" é totalizador calculado que não existe na base — erro de
desenho dele. (e) despejo do payload da ferramenta: pergunta de UM número,
resposta com 24 bullets; causa dupla — bug do system_prompt não repassado (meu) +
tamanho do retorno de ferramenta dele (34 linhas, ~750 tokens). (f) RESPOSTA EM
TAILANDÊS: qwen2.5:14b, perfil local, primeira chamada depois de um restart do
gateway; sem tool call, cifra inventada (R$ -6.546.567, certo era -971.553,41), e
2,3s de latência quando o normal dele é 11-15s. NÃO INVESTIGOU. Reapareceu no A/B
dele: 1 de 8 respostas fora do alfabeto latino. Duas ocorrências, zero
investigação. É o item que ele mais queria que eu olhasse — a latência de 2,3s é
o que o incomoda, "não parece geração normal". (g) erros próprios achados pelos
revisores dele: except KeyError envolvia a chamada da ferramenta e virava
"ferramenta desconhecida"; cliente podia substituir o system prompt inteiro;
histórico crescia sem teto; auditor só verificava se a trilha existia.

RESOLVIDOS: (a) gateway commit c62313e, contorno removido do lado dele, ficou
teste de integração que reenvia arguments como string. (b) periodo.py extrai o
período e trata como parâmetro; RECUSA quando o modelo diverge do que o usuário
escreveu; os três modelos passaram a acertar. (c) MITIGADO, não resolvido: toda
cifra >= 1.000 tem de aparecer em resultado de ferramenta. (d) estrutura.py
compartilhada. (e) PARCIAL. (g) resolvidos do lado dele ontem.

PENDENTE: VERBOSIDADE NÃO RESOLVIDA — minha regra levou meu caso sintético de 543
para 31 tokens, mas no caso dele mediu 3 execuções: 1.130, 1.754, 1.811
caracteres. Reduziu o payload de 34 para 12 linhas e remediu: 784, 1.041, 1.826.
Melhorou, não resolveu. ACEITOU SEM ENTENDER por que minha regra funcionou no meu
teste e não no dele; hipótese não isolada (payload grande + prompt de domínio de
~1.260 tokens vindo DEPOIS do meu no encadeamento). A/B INCONCLUSIVO: n=8,
mediana 938 ch com a linha, 759 sem, mas p25 150 e p75 1.657 — variância engole a
diferença; decidiu por divisão conceitual, NÃO por medição. CONTORNO QUE PREFERIA
NÃO TER: _aplicar_recorte recusa a chamada do modelo e devolve instrução de
correção como se fosse resultado de ferramenta — canal fora de banda que ele
inventou. REGISTRADO E NÃO FEITO: o `limite` da ferramenta composicao vem do
modelo sem teto. NUNCA MEDIU: quantas vezes max_voltas=8 é atingido; e o custo é
sempre 0.0 no perfil local, então não tem sinal de orçamento. DUAS LIMITAÇÕES QUE
ELE DIZ SEREM MINHAS: (1) sem streaming incremental — chat fica 15s com spinner e
zero saída parcial, "para um gestor esperando um número, 15s de nada é a
diferença entre usar e não usar"; (2) não tem como saber se um modelo melhor
resolve a verbosidade, porque seguiu a regra de não mandar dado real pelo perfil
chat — está otimizando às cegas contra um 14B sem linha de base.

REGISTRADO: chat/README.md, memória dre-khronos-chat-llm.md, commits a6bbfda e
5857f78, .herdr/review/dre-2/*/verdict.md, docstring de _dre. EM LUGAR NENHUM: a
resposta em tailandês e a latência 2,3s; o A/B inconclusivo; as duas limitações.

---

## content-insights-collector-exec (lido da tela, pode estar truncado)

PROBLEMAS: categoria inválida do Ollama (saas.micro_saaaS) em smoke real com
qwen2.5:14b em 22/08 — prompt não restringia por enum; validador pós-resposta
pegou e o post foi dead-lettered sem publicar dado ruim. CONCORRÊNCIA entre
worker de triagem e investigador batendo no mesmo Ollama — não documentado como
incidente com data, mas llm_gate.py diz por que existe: "makes failures harder to
attribute and can overload an older runner"; alguém viu doer o suficiente para
construir file-lock cross-process. Injeção de prompt via conteúdo capturado do X
— não sabe se foi incidente real ou ameaça antecipada. Superinferência de
categoria sem evidência. Erros de transporte (429, 5xx, timeout, JSON malformado)
— todos tratados, mas NÃO SABE quais dispararam de verdade em produção. Staging
interrompido em 23/08 (banco preservado à parte) — viu acontecer, causa raiz
nunca investigada. Achados de auditoria desta sessão:
MAX_CODEX_LENS_CALLS_PER_DAY lido direto de os.environ fora do Settings;
RETENTION_DAYS não declarada no local.env bloqueia fail-closed a primeira chamada
ao Sonnet hospedado; margem de quota global em zero folga (ΣC_k = G - A
exatamente).

SOBRE O GATEWAY: não encontrou NENHUMA referência a llm-gateway no repositório —
nem código, nem env var, nem doc. Três caminhos reais: Ollama HTTP direto (local
ou via túnel SSH), CLI codex por subprocess, CLI claude por subprocess.

RESOLVIDOS: categoria inválida → adapter subiu para
taxonomy-v1-ollama-v4-json-schema com enum estrito no prompt. Concorrência →
file-lock cross-process (OLLAMA_REQUEST_LOCK_PATH). Injeção → escaping testado.
Superinferência → camada determinística de repair. NENHUM foi corrigido do lado
do gateway/infra; todos no código da aplicação.

PENDENTE: MAX_CODEX_LENS_CALLS_PER_DAY fora da validação central (só ADR-0005);
RETENTION_DAYS ausente é bloqueio operacional real para a próxima feature; margem
de quota zero sem contingência; causa raiz do staging de 23/08 nunca investigada;
frequência real de 429/5xx desconhecida; se/como o projeto atravessa o gateway é
invisível para ele.

REGISTRADO: docs/validation/phase5-triage-2026-08-22.md,
docs/validation/phase6-local-omarchy-2026-08-23.md (topologia do túnel + staging
interrompido, sem post-mortem), src/insights_collector/llm... (truncado na
leitura).

---

## acervo-exec (lido da tela, pode estar truncado)

PROBLEMAS, caminho zoning (Ollama/Codex/Grok direto, TASK-97): schema oneOf
discriminado rejeitado pela API real ("'oneOf' is not permitted" em qualquer
nível) — só apareceu contra a API real, mocks nunca pegaram. Decorrente:
_validate_conclusion rejeitava os null que o schema achatado força. Filtro de
campo por tipo furou a guarda anti-alucinação em duas direções opostas.
Amplificação de prompt: action.params/summary iam crus pro histórico, medido 50KB
× 10 obs → ~1MB. OLLAMA DEVOLVE RESPOSTA VAZIA no meio do laço — vi acontecer
duas vezes (CPU local, contexto 4096; e GPU remota com qwen3.5:9b, turno ~8-9),
NUNCA INVESTIGOU; hipótese não confirmada: format:json + wrapper de thinking do
qwen produzindo conteúdo final vazio. DEFAULT_OLLAMA_MODEL nunca existiu no
Ryzen9 — OllamaReasoner() sem args quebrado desde sempre, silenciosamente (erro
genérico de provider, não "modelo ausente"). Porta 11434 fechada antes de
expormos na tailnet — contornou com túnel SSH. LENTIDÃO PERCEBIDA — investigada
antes de subir timeout (GPU confirmada saudável via nvidia-smi/journalctl; causa
provável é fila OLLAMA_NUM_PARALLEL=1 compartilhada, não bug). Estrutural:
run_research_loop termina no primeiro conclude inválido, sem devolver o erro pro
modelo tentar de novo — em 50+ casos reais, ZERO conclude automático teve
sucesso, sempre cai em needs_human_review. GrokReasoner (api.x.ai direto) fora do
gateway inteiramente. GrokReasoner tem fallback documentado (HTTP 400 → recuo pra
json_object) herdado de sessão anterior, nunca verificado ao vivo.

CAMINHO GATEWAY (benchmark_plan_layout_proposals.py): nenhum problema registrado
— mas porque NUNCA VIU RODAR DE VERDADE. Um commit só desde a criação (24/07),
nunca mais tocado, sem task própria. Os 11 testes cobrem só a fronteira de
segurança (URL/proxy) e a lógica de geometria/score — nenhum teste exercita o
ciclo real de request/resposta contra o gateway, nem mockado.

RESOLVIDOS: oneOf, params inesperados, guarda de invenção (2 rodadas),
amplificação de prompt — lado dele, 4 rodadas de review (acervo-77 a 80). Modelo
ausente no Ryzen9 — lado nosso (pull). Porta fechada — lado nosso (tailnet).
Lentidão — não era bug; timeouts subidos (60→120s Ollama, 180→300s Codex) por
precaução. Grok ungoverned — decisão de plano/negócio, documentou sem remover.

PENDENTE: resposta vazia do Ollama mid-loop, aberto, não sabe de que lado é;
falta de retry após conclude inválido, aberto por decisão explícita do usuário;
sugestão de validar modelo na inicialização (GET /api/tags), registrada e não
implementada; fallback HTTP-400→json_object nunca verificado (truncado).

---

## mfc-exec (lido da tela, pode estar truncado)

PROBLEMAS: comparação numérica errada no perfil backtest-analysis (qwen2.5:14b
via /v1/tasks), DUAS VEZES em produção real (journal_seq=31 e 32) — apontou o
motor com líquido mais negativo como "melhor". budget_usd rejeitado no registro
do perfil (gt=0) — não investigou a fundo, só reportou. CSS_LLM_GATEWAY_URL
INOPERANTE — resolveu sozinho, nunca reportou: era lida como constante de módulo
na importação, nos dois caminhos reais nunca valia nada, sempre caía no default
18080; achado pelo revisor dele (mfc-rev-2), não por ele. RESPOSTA SEM TETO DE
TAMANHO — também resolvido sozinho e nunca reportado; nada limitava o tamanho do
result antes de gravar num JSON versionado em git reescrito por inteiro a cada
anexação; nunca viu estourar, foi achado por revisão. PORTA 8080 JÁ OCUPADA: 8080
no Ryzen9 pertence a um sistema de trading AO VIVO não relacionado
(pairtrading-server.service); descobriu batendo no /health dele por engano antes
de escolher 18080.

RESOLVIDOS: comparação numérica fechada dos dois lados (eu reescrevi o
system_prompt, ele pré-ordena os motores por líquido em _build_llm_analysis_text;
reverificado com journal_seq=32, ranking correto). budget_usd resolvido do meu
lado (ge=0). CSS_LLM_GATEWAY_URL resolvido do lado dele (função lida na hora, não
constante de import). Teto de tamanho resolvido do lado dele (descarta acima de
32KB). Porta 8080 não foi resolvida, foi contornada (18080, documentado).

PENDENTE: ZERO OBSERVABILIDADE SE O TÚNEL CAIR — systemd do túnel está active,
mas se morrer _call_backtest_analysis() retorna None silenciosamente
(try/except best-effort de propósito), nenhum alerta, nenhum log visível fora do
log_tail; ninguém notaria além de "sumiu o badge". Não implementou nada e não
pensou em quem seria dono da checagem. NUNCA TESTOU CHAMADA CONCORRENTE de
verdade — dois disparos de backtest próximos rodariam compare() serializado, mas
a chamada ao gateway acontece FORA desse lock; dois httpx.post pro mesmo modelo
podem se sobrepor; nunca reproduziu. MARGEM DE TIMEOUT (190s vs 180s do perfil)
nunca estressada — pegou o "~28s frio" que passei e somou margem, nunca testou
frio+rede lenta junto. NÃO VALIDA O SCHEMA CLIENT-SIDE de propósito, então nunca
viu de verdade um caso onde a resposta bateu no schema errado depois do
raise_for_status() passar (truncado).
