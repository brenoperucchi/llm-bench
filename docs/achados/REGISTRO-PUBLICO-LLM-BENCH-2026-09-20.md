# Registro público de achados — llm-bench

**Data de corte:** 2026-09-20

**Bancada principal:** Ryzen9/WSL Arch CUDA + RTX 5090 de 32 GB
**Objetivo:** avaliar modelos e runtimes locais para uso no stack de LLM, com atenção especial ao papel de um guardião que lê panes e artifacts, resume e ranqueia candidatos, mas não tem autoridade para agir.

> Este documento é uma síntese para leitura humana e para uso como contexto em conversas futuras. Ele não substitui os artifacts hash-addressed. Quando houver conflito, o resultado bruto e o registro específico da execução vencem esta síntese.

## 1. Resumo executivo

O trabalho produziu cinco conclusões principais:

1. **O problema não é escolher o modelo mais rápido.** Throughput alto pode significar apenas que o modelo gastou todo o orçamento pensando e não entregou uma resposta utilizável. A bateria passou a separar velocidade, conclusão e aderência ao contrato.
2. **O runtime faz parte do resultado.** Um modelo pode carregar sem erro e ainda calcular errado. Isso aconteceu com o Bonsai no fork Codacus: o arquivo carregou, mas a perplexidade ficou em centenas de milhares; no fork Prism, o mesmo modelo produziu PPL saudável.
3. **A instrumentação foi o maior risco inicial.** Várias rodadas do T87 mediram preparação incompleta, sandbox remoto, permissões, canal de resposta ou teto de tokens — não a capacidade do modelo. Esses resultados foram excluídos, não reinterpretados como qualidade.
4. **Para o guardião, uma arquitetura híbrida é mais segura:** coletor determinístico faz a triagem e reúne evidências; um LLM sem tools, escrita, callbacks ou poder de interrupção pode resumir e ranquear; regras determinísticas continuam sendo a única autoridade para notificar o humano.
5. **Decisão tipada por logprobs é uma rota promissora para decisões fechadas.** Coder e a3b sem raciocínio devolveram distribuições sobre opções de uma letra. Isso mede mecânica, custo e concentração da decisão, não acurácia: os packets usados não tinham labels gold.

O projeto ainda **não fechou um candidato de produção**. O critério inicial “entendimento de código melhor que qwen3-14b” foi retirado pelo owner antes de ser medido de forma válida; é necessário substituí-lo por um critério de rejeição aprovado.

## 2. O que estava sendo avaliado

O llm-bench começou como uma bancada para responder: “um modelo local pode entrar no nosso stack?”. A pergunta foi refinada durante os testes:

- para benchmarks gerais: carregar, velocidade, qualidade e comportamento precisam ser medidos separadamente;
- para o guardião: a pergunta é se um modelo consegue ler buffers/artifacts, produzir uma classificação ou resumo auditável e operar continuamente;
- o modelo do guardião **não recebe tools, não escreve, não executa comandos e não interrompe o humano**;
- evidência, estado, listeners, PIDs e transições observáveis vêm do coletor/regras;
- o LLM pode interpretar, resumir e ranquear, mas a decisão externa continua determinística.

Essa separação é importante: um modelo que gera JSON bonito não ganha autoridade operacional por isso.

## 3. Como ler os resultados

Cada afirmação deve ser entendida em conjunto com quatro dimensões:

| Dimensão | Exemplos | Por que importa |
|---|---|---|
| artefato | GGUF, shard, blob do Ollama, prompt | arquivos diferentes não são o mesmo experimento |
| runtime | Ollama, Codacus/llama.cpp, PrismML/llama.cpp | o mesmo modelo pode carregar ou calcular de forma diferente |
| rota/contexto | LAN, tailnet, SSH forward, sessão Windows/WSL | latência e acesso à GPU mudam com a rota e a sessão |
| configuração | offload, `-ngl`, `--cpu-moe`, `--n-cpu-moe`, `--load-mode`, contexto, sampling | movimentar pesos muda a saída e o throughput |

Por isso, uma `series_key` correta inclui, no mínimo, runtime, commit/binário, hash do artefato, rota, configuração de offload, contexto, prompt, schema, versão do harness e parâmetros efetivamente enviados. Séries com chaves diferentes não devem compartilhar média, tendência ou dispersão.

### Proveniência usada neste registro

- **observado/canônico:** manifesto, request/response, log e hash disponíveis no repositório;
- **derivado:** cálculo reproduzível a partir de artifacts observados;
- **fraco:** relato owner-supplied por `curl`/SSH sem manifesto completo;
- **invalidado:** execução que não satisfazia o contrato do experimento;
- **unknown:** o dado não foi observado; não é permissão para preencher por inferência.

Proveniência da medição e disponibilidade pública são eixos diferentes. Alguns números abaixo foram canônicos dentro da bancada, mas os manifests, logs e respostas brutas correspondentes não fazem parte deste primeiro bundle. Eles ficam marcados como `observado internamente; artifact público ausente` e não constituem benchmark público reproduzível.

## 4. Linha do tempo resumida

### 4.1 T87 P1: do experimento à higiene experimental

O P1 pretendia verificar a estabilidade de uma suíte de 17 tarefas. A campanha passou por várias versões porque cada tentativa revelou uma falha de preparação:

1. sandbox remoto encerrou antes do marcador; o harness não capturou exit code, sinal e stderr, portanto a causa original ficou `unknown`;
2. a dependência `flask` não estava instalada; o agente enfrentou um obstáculo criado pelo laboratório, não a armadilha da tarefa;
3. o agente chegou a ter acesso a artefatos privados de solução e gabarito do checkout protegido; essa rodada foi invalidada;
4. o corretor foi chamado pelo caminho errado e um `app.py` órfão segurou a porta `5000`, produzindo timeout;
5. o harness tinha classes de resposta e limites de tokens que precisavam ser registrados explicitamente.

O laboratório só ficou válido na série protegida: checkout fora do alcance do usuário medido, dependências congeladas, usuário de execução sem acesso ao gabarito, reset privilegiado por regra estreita e corretor usando o Python correto. A autorização owner encerrou a campanha antes de gastar as 92 gerações restantes.

O fechamento é uma decisão owner-approved de 2026-09-19 sobre a campanha `t87-p1-harness-v8`. A conclusão correta é limitada ao par `(harness-v8, qwen3.6-35b-a3b)` e não é um veredito geral do modelo. A série não produziu as cinco corridas homogêneas necessárias para estimar a dispersão; os scores parciais não formam uma estatística final.

### 4.2 Correção do canal de resposta

Os transcripts mostraram `content` vazio, `reasoning_content` preenchido e `tool_calls` presentes. O harness v9 passou a registrar classes de canal e a tratar `tool_calls` como única fonte de ação. `reasoning_content` nunca é promovido a comando. A v9 foi implementada, mas o fechamento owner-approved não autorizou consumir novamente as gerações devolvidas.

O detalhe metodológico é essencial: em modelos de raciocínio, `content` vazio pode significar canal de ação separado ou truncamento do orçamento de tokens. Sem `finish_reason`, `tool_calls` e contagem de tokens, não se pode atribuir a causa ao modelo.

## 5. Infraestrutura: o que aprendemos na prática

### 5.1 GPU, sessão e daemon

Houve duas instâncias do Ollama na máquina Windows. O daemon em Session 0 tomou a porta `11434` e carregou em CPU (`size_vram=0`); a instância da sessão interativa voltou a acessar a RTX 5090 depois da correção. A versão também mudou de 0.33.3 para 0.34.2 e as bibliotecas de runner CUDA foram restauradas.

**Regra:** `/api/version`, `/api/tags` e `health=200` não provam que um modelo está residente na GPU. Sempre registrar `GET /api/ps`, `nvidia-smi`, PID, sessão, listener, VRAM, RAM e flags.

### 5.2 LAN, tailnet e SSH forward

Havia duas rotas para a máquina Ryzen9. A rota LAN foi preferida para P1 por reduzir ruído; a tailnet permanece relevante quando a pergunta é latência de produção. O endpoint dedicado de llama.cpp e a rota usada devem constar na série, sem transformar endereços privados em parte do registro público.

Quando o acesso LAN direto não estava disponível em um contexto, o harness usou forward SSH. Isso preservou o contrato local do cliente, mas não torna a latência de uma rota equivalente à de outra.

### 5.3 CUDA e builds

A distro nova só tinha CUDA 13.4 (`libcudart.so.13`); o binário antigo dependia de CUDA 12 e não era executável nesse ambiente. Recompilar com `CMAKE_CUDA_ARCHITECTURES=120a-real`, Flash Attention e CUDA graphs foi preferível a misturar bibliotecas e criar uma série de runtime ambígua. Em uma máquina com 32 cores, `-j24` reduziu o build do fork Codacus de horas estimadas para aproximadamente seis minutos.

O build Prism foi mantido separado. O fork Prism é obrigatório para artefatos PrismML/Ternary Bonsai; o fork Codacus suporta qwen4exp do Flash-Next, mas não deve ser usado para calcular perplexidade de Bonsai.

### 5.4 Armazenamento WSL

`/` dentro do WSL mostrava o teto do VHDX, não o espaço físico real do host. Uma cópia de 53,8 GB para o filesystem da distro inflou o VHDX. O arquivo foi removido; grandes GGUFs e logits devem ficar em um diretório montado do host. Para espaço real, consultar os mounts do host, não somente o teto reportado pelo filesystem virtual.

Mover o F16 do Bonsai do mount do host para o filesystem nativo WSL reduziu o tempo de carga, mas não melhorou o tempo de chunk:

| Configuração | Tempo de chunk |
|---|---:|
| `-ngl 20`, mount do host | 27,74 s |
| `-ngl 24`, mount do host | 25,66 s |
| `-ngl 24`, filesystem da distro | 25,99 s |

Resultado: não se deve declarar que drvfs é o gargalo do cálculo com base nessa troca. A hipótese de releitura de um modelo de 53,8 GB com apenas 47 GB de RAM continua sendo uma interpretação de trabalho, não uma prova universal.

## 6. Candidatos, runtimes e medições

### 6.1 Visão geral

| Candidato | Artefato | Runtime medido | Resultado de qualidade/contrato | Velocidade registrada |
|---|---|---|---|---:|
| Qwen3-Coder 30B-A3B | UD-Q5_K_XL, 21,74 GB | Codacus | 2/5 válidos em cada uma das quatro fases T1/T2; todas terminaram | 267,86 tok/s mediana quente |
| Qwen3.6-35B-A3B | Q4_K_M, blob Ollama 21,72 GB | Codacus | T1 unconstrained 4/5; T2 0/5 com teto 2048; no-think foi uma série separada sem artifact público neste release | 233,30 tok/s com raciocínio; observado internamente, artifact público ausente |
| Qwen3.8-27B | UD-Q5_K_XL, 20,88 GB | Codacus | T1 unconstrained 5/5; T2 unconstrained 0/5; GBNF pendente por gate de GPU residual | 63,77 tok/s fraca; não canônica |
| Ternary Bonsai 2 | PTQ1_0, 5,95 GB | PrismML | T1 unconstrained 4/5; GBNF 0/5 no `content`, 3/5 no raciocínio | aproximadamente 121,3 tok/s fraca; não canônica |
| Flash-Next | UD-IQ3_XXS, 3 shards, 81,96 GB | Codacus | carrega e conclui, mas fora do escopo de avaliação | 16,18 `--cpu-moe`; 26,98 `--n-cpu-moe 32`, procedência fraca |

Os números de velocidade da tabela não têm todos o mesmo nível de formalidade. As medições canônicas usam manifesto, hash, warm-up descartado e mediana de três gerações quentes. Os números explicitamente marcados como fracos vieram de SSH/curl sem manifesto completo e servem apenas como histórico. A ausência de artifact público é indicada separadamente e não rebaixa automaticamente a proveniência observada dentro da bancada.

### 6.2 Qwen3-Coder 30B-A3B

Os números desta subseção foram observados internamente com protocolo estruturado; o artifact público correspondente não faz parte deste release.

- GGUF: `21,740,305,568` bytes;
- SHA-256: `eb331a4eee8eb6b5a8eb25f44f96f45c71b8d10f553c0a456190dd590a7ef77d`;
- T1 unconstrained, T2 unconstrained, T2 GBNF e T1 GBNF: `2/5` respostas válidas em cada fase;
- cinco de cinco requests terminaram com `stop` em cada fase;
- velocidade: warm-up `261,89`; quentes `265,14 / 267,86 / 270,78`; mediana `267,86 tok/s`;
- saída da medição de velocidade: 885 tokens, `stop`, `content` preenchido.

O Coder foi o melhor comportamento estrutural dentro desta bateria, mas `2/5` não é um critério de promoção. O critério owner-facing precisa ser definido antes de escolher um candidato.

### 6.3 Qwen3.6-35B-A3B

Com raciocínio ligado, o modelo foi muito rápido, mas nas quatro chamadas do probe de throughput com `max_tokens=2048` terminou em `length`, com `content` vazio e raciocínio preenchido. Isso não prova que o modelo não conclui; prova que o teto escolhido era insuficiente para aquela tarefa.

Foi explorado um teste separado com `chat_template_kwargs: {"enable_thinking": false}`. Ele deve ser tratado como uma série diferente: desligar raciocínio é configuração do modelo/runtime e não pode ser misturado com a série normal. O detalhe numérico desse smoke test não é reivindicado nesta publicação porque seu artifact não está no bundle público.

### 6.4 Qwen3.8-27B

O T1 com `max_tokens=8192` terminou em `5/5`, mostrando que o teto de 2048 não era uma base justa para avaliar conclusão. A medição fraca anterior de 63,77 tok/s foi feita com poucos calls e sem protocolo formal de frio/quente; ela não deve ser usada como número operacional.

### 6.5 Ternary Bonsai 2

O Bonsai mostrou por que qualidade e velocidade precisam estar separadas. A medição antiga de aproximadamente 121 tok/s com teto 2048 terminou por `length`; a fase T1 com 8192 terminou `4/5` no modo unconstrained. Com GBNF, todas as cinco chamadas pararam, mas três objetos válidos apareceram somente em `reasoning_content`; o consumidor correto manteve `content` como canal canônico e contou isso como zero respostas válidas no contrato. A condição GBNF foi aplicada na inicialização do servidor, mas o artifact público não registra essa propriedade; portanto a conclusão é uma observação interna com evidência indireta, e uma reprodução futura deve registrar a gramática ativa junto do resultado.

Esse resultado não é “o modelo não sabe JSON”. Ele mostra que gramática pode garantir forma em um canal que o consumidor não pode aceitar como ação.

### 6.6 Flash-Next

O Flash-Next carregou com `--cpu-moe`, concluiu uma resposta e produziu `16,18 tok/s` quente; `--n-cpu-moe 32` produziu `26,98 tok/s` quente. O offload mudou a saída mesmo com seed e temperatura iguais; portanto offload pertence à `series_key`.

Ele saiu do escopo de avaliação por decisão do owner: uso de 33–44 GB de RAM, mmap de aproximadamente 82 GB em storage montado do host, carga longa, dependência do fork Codacus e números obtidos com máquina ociosa. Além disso, o artifact local (177B/qwen4exp) não foi comprovado como o mesmo modelo do scorecard histórico que mencionava 125B/17/17. O artefato não foi apagado; permanece como referência histórica de uma classe de modelo grande, não como reprodução daquele scorecard.

## 7. Achado crítico: KL e runtime PrismML

### 7.1 O erro silencioso

O primeiro F16 do Bonsai foi processado pelo `llama-perplexity` Codacus. O arquivo carregou sem erro, mas a PPL foi absurda:

- Codacus, controle comum: `1.165.154,2284`;
- Codacus, corpus interno, 100 chunks: `838.794,2256`.

O mesmo F16 no binário Prism produziu `1,1045` no controle curto e `5,4163` em um chunk do corpus interno. A causa comprovada é a incompatibilidade silenciosa do runtime: para modelos PrismML, carregar não basta; é preciso verificar a computação com o fork correto.

O controle comum era repetitivo e não deve ser citado como “PPL do Bonsai”. Ele serviu apenas para diferenciar o runtime errado do correto.

### 7.2 Base e curva de quantização válidas

Os números desta subseção foram calculados na bancada e estão preservados como referência interna; o corpus e os artifacts brutos não fazem parte deste release público.

Com o Prism, a base F16 de 100 chunks sobre o corpus interno de artifacts operacionais produziu `PPL = 6,0012 ± 0,04775`. O arquivo de logits da base tem `50.807.909.620` bytes; o F16 de referência tem `53.808.408.928` bytes. Esses tamanhos identificam arquivos diferentes e não devem ser confundidos. O corpus não é publicado; portanto a curva é reproduzível apenas dentro da bancada. Uma verificação externa exige refazer a base com um corpus público, sabendo que os valores absolutos mudarão.

Comparações contra a mesma base Prism:

| Quantização | Tamanho | Mean KLD | Mediana | p99 | p99.9 | Same top-p |
|---|---:|---:|---:|---:|---:|---:|
| PTQ1_0 | 5,95 GB | 0,000368 ± 0,000020 | 0,000184 | 0,001760 | 0,015705 | 98,630% |
| PQ2_0 | 7,21 GB | 0,000385 ± 0,000020 | 0,000183 | 0,001725 | 0,016675 | 98,593% |

Leitura correta: PTQ1_0 e PQ2_0 preservam de forma muito próxima os pesos ternários representados pelo F16. Isso é **fidelidade de armazenamento**, não prova de mérito do Bonsai contra um modelo denso. O PQ2_0 não mostrou ganho material que justificasse 1,26 GB extra; PTQ1_0 é a escolha mais econômica para esse modelo.

A fração exata de tokens acima de `0,01` nats é `unknown`: o binário publicou quantis, não contagem por token. Não se deve inventar esse percentual a partir do p99.

## 8. O que o teste do guardião realmente mediu

O packet congelado contém cinco rodadas reais, mas `labels_loaded=false`. Portanto T1/T2 medem conclusão e aderência mecânica ao contrato, não acurácia.

O schema v1 exige `agent_session`, `suggested_state`, `abstain`, `evidence`, `confidence` e `escalation_requested`. A evidência precisa resolver para arquivo/trecho; confiança tem bandas operacionais (`low`, `review`, `high`), mas é heurística. O modelo não executa a ação.

Dois limites ficaram explícitos:

- GBNF/JSON Schema podem produzir JSON válido no canal de raciocínio, que o consumer deve rejeitar;
- coordenada/path válido não prova relevância semântica do trecho; essa dimensão continua não medida.

As medições atuais não autorizam afirmar que um modelo detecta corretamente `stalled`, `correction-in-progress` ou qualquer outra classe. Para isso ainda é necessário um corpus rotulado, labels independentes e um threshold owner-approved.

## 9. Decisão tipada por logprobs

Foi criada e executada uma sonda independente de decisão tipada. Ela usa cinco opções de uma letra (`A`–`E`), porque palavras como `correction-in-progress` podem ser vários tokens. As IDs de token foram verificadas antes de usar a massa.

O protocolo usou `max_tokens=1`, `temperature=0`, `seed=42`, `logprobs=true` e `top_logprobs=10`, com quatro perguntas sobre cada packet: estado, necessidade de atenção, escalonamento e confiança.

Os resultados numéricos da sonda permanecem fora deste primeiro bundle porque os packets e os JSONs brutos contêm material privado. Sem esse bundle hash-addressed, não há uma tabela pública de latência ou entropia a reivindicar.

O resultado demonstra mecânica e custo, não acerto. Não havia gold labels. Também não resolve evidência literal: decisão tipada deve receber sua evidência do coletor determinístico. Os números brutos e os packets permanecem fora deste bundle público.

## 10. O que está invalidado, o que é histórico e o que falta

### Não usar como veredito

- resultados do T87 com suite acessível, dependência ausente ou corretor errado;
- scores parciais do P1 como dispersão final;
- PPL Codacus do Bonsai como qualidade ou como base KL;
- velocidade medida com build/download concorrente sem marcação;
- throughput sob `max_tokens=2048` como prova de que um modelo não conclui;
- comparação entre runtime, rota, artefato ou offload diferentes como se fosse efeito puro de uma variável.

### Mantido como referência histórica

- Flash-Next e suas duas configurações de offload;
- números owner-supplied por SSH/curl sem manifesto;
- tentativa de copiar o F16 para o filesystem da distro, registrada como experimento negativo de otimização e lição de armazenamento;
- tentativas do P1 que revelaram falhas de laboratório.

### Pendências reais

1. substituir o critério removido “melhor que qwen3-14b” por uma régua owner-approved; o modelo continua disponível como possível baseline operacional, mas deixou de ser a régua desta campanha;
2. decidir se o guardião usará decisão tipada, geração estruturada ou composição híbrida;
3. construir corpus rotulado independente para medir acerto, abstention e falso positivo;
4. repetir somente as medições necessárias com `series_key` completa;
5. especificar o p95 operacional: eventos frios, cadência, carga da máquina e amostras;
6. medir relevância semântica da evidência, sem promover coordenadas válidas a prova de pertinência;
7. determinar se e quando o no-think do a3b é aceitável para o papel fechado.

## 11. Limite da publicação e reprodução

Este registro é um documento público autossuficiente. Packets, transcripts, manifests derivados de `.herdr`, respostas brutas, métricas internas e caminhos locais não entram automaticamente na publicação, porque podem conter nomes de usuário, endereços privados, conteúdo de panes e material de revisão não destinado ao GitHub.

O código de avaliação e a sonda tipada permanecem fora deste primeiro commit público enquanto passam por sanitização e revisão de contrato. O bundle também não inclui a propriedade de inicialização que provaria externamente a gramática GBNF ativa; esse campo deve ser registrado em uma futura reprodução.

Uma futura reprodução deve publicar um bundle hash-addressed com artifact, binário, flags, rota em forma pública, prompt, schema, sampling, ambiente, estado de cache e proveniência por campo. Sem esse bundle, os números marcados como fracos continuam históricos e não devem ser tratados como benchmark canônico.

## 12. Conclusão atual

O trabalho não terminou com “o modelo X ganhou”. Ele entregou algo mais necessário para uma decisão confiável:

- um laboratório protegido e uma taxonomia de resultados inválidos;
- evidência de que runtime e configuração mudam o resultado;
- uma curva de fidelidade de quantização do Bonsai contra sua própria referência F16;
- comparação inicial de conclusão/estrutura entre candidatos;
- uma alternativa de decisão tipada que reduz os riscos de canal, truncamento e parsing;
- uma separação operacional entre coleta determinística, interpretação do LLM e autoridade de ação.

O próximo passo correto não é executar mais chamadas por inércia. É fixar a régua de aceitação, congelar o packet rotulado e só então medir o candidato que melhor atende ao papel real.
