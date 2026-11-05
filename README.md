# Agente de Atendimento — Empório da Música

Protótipo de um agente de atendimento por mensagens de texto para a Empório da Música, loja fictícia de instrumentos musicais em Campo Grande/MS. Desenvolvido por Júlia Félix Giannandrea como desafio técnico para a vaga de AI Engineer na Artefact.

O agente responde às perguntas recorrentes que hoje sobrecarregam a equipe (preço, disponibilidade, status de pedido, horários, trocas, pagamento), consultando os dados da loja e o manual de políticas, no tom da loja e sem inventar informação.

**Em resumo:**

- **Agente Strands** com loop ReAct e 9 ferramentas: as perguntas recorrentes usam ferramentas de contrato fechado, e o SQL livre, somente leitura, fica como último recurso.
- **Dados tratados por um ETL** em camadas (bronze, silver, gold), com 21 verificações de qualidade e um relatório gerado automaticamente.
- **Manual de políticas curado em 9 seções.** O agente carrega só a que precisa, e um teste confere cada valor contra o PDF.
- **Cálculos e guardrails críticos em código, não no prompt:** preços, parcelas e prazos chegam prontos ao modelo; a verificação de identidade e as restrições de SQL não dependem de o modelo obedecer.
- **Dois canais:** terminal (CLI) e interface web em Streamlit, com cartões montados a partir dos dados consultados e o plano do agente em tempo real.
- **216 testes automatizados,** que rodam sem chave de API, e um conjunto de 36 perguntas para avaliar as respostas.

## Documentação

| Documento | Conteúdo |
|---|---|
| Este README | Como rodar, decisões técnicas, limitações, uso de IA e checklist do desafio |
| [`docs/arquitetura.md`](docs/arquitetura.md) | Como o agente funciona por dentro, com diagramas |
| [`docs/processo.md`](docs/processo.md) | O que foi feito em cada etapa, problemas encontrados e como foram resolvidos |
| [`docs/decisoes.md`](docs/decisoes.md) | Registro de decisões (D01 a D23) e suposições (S01 a S07), com contexto e alternativas |
| [`docs/uso-de-ia.md`](docs/uso-de-ia.md) | Como usei assistentes de IA, etapa por etapa |
| [`docs/data_quality.md`](docs/data_quality.md) | Relatório de qualidade de dados, gerado pelo ETL |
| [`kb/pendencias_gerencia.md`](kb/pendencias_gerencia.md) | Contradições e lacunas do manual, para a gerência da loja |
| [`docs/documentacao.pdf`](docs/documentacao.pdf) | Este README e a documentação num único PDF |

---

## Como rodar

### Pré-requisitos

- Python 3.11 ou mais recente.
- Uma chave de API de um dos provedores suportados:

| Provedor | `PROVIDER` | `MODEL_ID` (exemplo) | Chave | Observação |
|---|---|---|---|---|
| Anthropic | `anthropic` | `claude-haiku-5-5` | `ANTHROPIC_API_KEY`, criada em [platform.claude.com](https://platform.claude.com/settings/keys) | Pago (créditos de API). Mais estável para escolher ferramentas e seguir a persona |
| OpenRouter | `openrouter` | um modelo com sufixo `:free` e suporte a *tool calling* | `OPENROUTER_API_KEY`, criada em [openrouter.ai](https://openrouter.ai) | Grátis, com limite de 20 requisições por minuto e 50 por dia (1.000 por dia para quem comprou pelo menos 10 créditos) |

Para rodar só os testes, nenhuma chave é necessária.

### Instalação

```bash
git clone https://github.com/juliafgiannandrea/agente-atendimento-artefact.git
cd agente-atendimento-artefact

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # preencha PROVIDER, MODEL_ID e a chave do provedor
```

O `.env` fica fora do Git. As outras variáveis já vêm com valores padrão: `TEMPERATURE=0.2`, `MAX_TOKENS=1024`, `REFERENCE_DATE=2026-03-25` (data simulada dos pedidos, ver S01) e `DB_PATH=data/emporio.db`.

### 1. Gerar o banco

```bash
python -m etl.pipeline
```

Lê os arquivos originais em `data/raw/` (que nunca são alterados), gera `data/emporio.db` e atualiza o relatório [`docs/data_quality.md`](docs/data_quality.md). Pode ser executado quantas vezes quiser: o banco é reconstruído do zero e o resultado é sempre o mesmo.

Para explorar o banco numa interface gráfica (Linux):

```bash
sudo apt install sqlitebrowser
sqlitebrowser data/emporio.db
```

As tabelas `raw_*` são a origem (bronze), as demais são a camada tratada (silver), e as views `vw_catalogo` e `vw_pedidos` são o que o agente consulta (gold). O resultado de cada verificação de qualidade fica em `dq_results`.

### 2. Conversar pela interface web

```bash
streamlit run src/agente/ui/app.py
```

Abre o chat no navegador (por padrão em `http://localhost:8501`). Rode o comando a partir da raiz do repositório, para o Streamlit usar o tema de `.streamlit/config.toml`.

Acima do texto do atendente aparecem cartões montados a partir dos dados consultados (produto, lista de produtos, pedido com prazos, horário, protocolo de reclamação). Em perguntas com várias etapas, o plano do agente aparece como um checklist que vai sendo marcado em tempo real. A barra lateral tem perguntas de exemplo e o botão "Nova conversa". Os textos das políticas não são exibidos, porque o manual é material interno da loja.

O desenho da interface foi validado num [protótipo visual](https://claude.ai/artifact/F9K2UnbBHQe9ksfwDXV8mh) antes da implementação. O protótipo mostra o desenho inicial: na versão final, os cartões vieram para antes do texto e o trecho da política consultada saiu da tela (D21 e D23).

### 3. Conversar pelo terminal

```bash
python -m agente                  # conversa nova
python -m agente --sessao maria   # cria ou retoma a conversa "maria" (memória entre execuções)
python -m agente --debug          # mostra as ferramentas usadas em cada resposta
```

Ao iniciar, o CLI faz uma chamada mínima ao modelo para conferir a chave, o modelo e a conexão. Se algo estiver errado, explica o problema e encerra (`--sem-verificacao` pula esse teste). Durante a conversa, `/exportar` salva o diálogo em Markdown em `exemplos/` e `/sair` encerra.

### 4. Rodar os testes

```bash
pytest
```

Os testes usam um banco temporário e não alteram `data/` nem `docs/`. O agente é testado com um modelo roteirizado, que simula as chamadas de ferramentas, então **não é preciso chave de API**.

### 5. Base de conhecimento (opcional)

A base de políticas já vem pronta em [`kb/`](kb/index.md). Para refazer a extração do PDF, por exemplo quando o manual for atualizado:

```bash
python -m etl.extrair_politicas
```

Gera `kb/_fonte/manual_extraido.md`. As seções em `kb/politicas/` são curadas a partir desse texto e revisadas à mão.

### Problemas comuns

| Sintoma | Causa provável e solução |
|---|---|
| "Configuração incompleta: PROVIDER inválido" | `.env` ausente ou sem `PROVIDER`. Rode `cp .env.example .env` e preencha |
| "Limite de requisições atingido" | Limite do modelo gratuito. Espere, troque o `MODEL_ID` ou use créditos/Anthropic |
| "O provedor recusou este modelo" | Alguns modelos gratuitos só aceitam aplicativos cadastrados no OpenRouter. Troque o `MODEL_ID` |
| "Banco não encontrado em .../data/emporio.db" ao iniciar | Rode `python -m etl.pipeline` antes de conversar |

---

## Como funciona

![Arquitetura do agente](docs/img/arquitetura.svg)

Na preparação, os CSVs viram um banco SQLite tratado e verificado, e o manual vira 9 seções de Markdown revisadas. No atendimento, o modelo decide quais ferramentas chamar, as ferramentas consultam o banco ou a base de políticas e devolvem os dados já calculados, e o modelo redige a resposta. O detalhamento, com o fluxo de uma pergunta de devolução passo a passo, está em [`docs/arquitetura.md`](docs/arquitetura.md).

---

## Decisões técnicas

O enunciado pede a justificativa de cada escolha. O resumo está abaixo; o registro completo, com contexto e alternativas descartadas, está em [`docs/decisoes.md`](docs/decisoes.md).

### Framework e abordagem do agente: Strands Agents, híbrido (D01, D16, D20)

Loop ReAct com *function calling*, no Strands Agents. O Strands é independente de provedor, transforma funções Python em ferramentas e já traz o loop de raciocínio, então o esforço foi para o que diferencia o agente: ferramentas, contexto e guardrails. Também é o framework que uso no trabalho.

A abordagem é **híbrida**:

- **Ferramentas de contrato fechado** para as perguntas recorrentes (produto, busca no catálogo, pedido, política, horário, reclamação). Com parâmetros tipados, o modelo erra menos e não consegue contornar regras.
- **Agente de SQL restrito** como último recurso, para perguntas que as ferramentas não preveem (filtrar por especificação, contar, comparar): primeiro lê a documentação do esquema, depois consulta, só no catálogo e só em leitura.
- **Planejamento explícito** (`planejar`) só nas perguntas com várias fontes, com um campo de informações faltantes que leva o modelo a perguntar em vez de supor. O plano fica visível na interface.

### Modelo e provedor: configuráveis, Anthropic ou OpenRouter (D02)

`PROVIDER` e `MODEL_ID` no `.env` escolhem o modelo, e só a função `build_model()` conhece o provedor. Os modelos gratuitos do OpenRouter deixam qualquer pessoa rodar o projeto sem custo, mas variam no suporte a ferramentas e têm limite diário. O Claude (Anthropic) é mais confiável para escolher ferramentas, seguir a persona e respeitar guardrails, e é o recomendado para as conversas finais. O desenvolvimento e os testes foram feitos com o `nvidia/nemotron-3.5-lightning:free`, gratuito no OpenRouter (ver Limitações). A temperatura é baixa (0,2), porque atendimento pede consistência, não criatividade.

### Arquitetura de retrieval: duas fontes, sem banco vetorial (D15, D16)

- **Dados estruturados** (catálogo, promoções, pedidos) vêm do SQLite pelas ferramentas, com valores calculados em código.
- **Políticas** vêm de 9 seções de Markdown. O prompt traz só o índice (gerado dos cabeçalhos), e o agente carrega a seção de que precisa (divulgação progressiva).

Não usei RAG vetorial porque, com 9 seções curtas, um índice escrito à mão é mais preciso que busca por similaridade, não corta uma regra ao meio e deixa auditável qual seção embasou cada resposta. Colocar o manual inteiro no prompt também caberia, mas misturaria regras de assuntos diferentes em toda resposta. Com um manual muito maior, a busca vetorial passaria a valer a pena.

### Estratégia de prompt (D17, D18, D22, D23)

O prompt de sistema é montado em camadas:

1. persona e princípios inegociáveis (`kb/soul.md`, escrita a partir das diretrizes de tom do manual);
2. tabela "a pergunta é sobre... → ferramenta" e regras de uso;
3. formato por canal;
4. índice das políticas;
5. data de referência.

Três princípios guiam o resto:

- **O prompt orienta, o código impede.** O que é crítico (privacidade, valores, SQL) é garantido nas ferramentas.
- **O modelo não faz contas.** Ele repete valores prontos.
- **O agente responde, não executa.** Não oferece reservar, vender nem avisar depois. Pergunta só o que falta para responder e, quando algo depende da equipe, indica os canais. A única ação é registrar reclamação, que o manual exige.

### Interface: CLI e web em Streamlit (D04, D21)

Comecei pelo CLI, mais rápido de construir e testar. Com o agente pronto, fiz a interface web em Streamlit, reaproveitando o mesmo agente. Os cartões da interface são montados **a partir do resultado das ferramentas, não do texto do modelo**: o modelo não tem como inventar um cartão, e quem avalia vê exatamente qual dado embasou a resposta.

### Persistência do histórico (D18)

- **Na conversa:** o histórico fica no agente, com janela deslizante de 40 mensagens, o que mantém o contexto sem estourar o limite do modelo.
- **No CLI:** `--sessao <id>` grava a conversa em disco (fora do Git) e permite retomá-la.
- **Na web:** cada aba do navegador tem a sua conversa, que some ao recarregar a página.

Não persisti o histórico da web de propósito. Guardar conversas com dados pessoais num servidor exigiria autenticação e política de retenção, o que vai além de um protótipo.

### Tratamento dos dados (D09 a D14)

ETL em camadas dentro do SQLite, reconstruído do zero a cada execução. Os arquivos originais nunca são alterados. Inconsistências são **sinalizadas, não corrigidas em silêncio**: o valor original fica, e a flag e o tratamento ficam ao lado e no relatório. As regras de negócio (disponibilidade, promoção vigente, PIX, parcelamento, prazos) estão num único módulo, usado pelo ETL e pelo agente, com `Decimal` para valores monetários.

### Suposições

O enunciado pede que ambiguidades sejam resolvidas com uma interpretação razoável e documentada. As principais:

| | Suposição | Por quê |
|---|---|---|
| S01 | Pedidos avaliados numa **data simulada, 25/03/2026**, configurável no `.env` | Os pedidos vão até março de 2026. Com a data real, todos estariam meses atrasados e fora de qualquer prazo, e os casos de raciocínio sobre prazo deixariam de existir. O horário da loja usa o relógio real |
| S02 | Parcelamento pelas **faixas da seção 3.1** do manual | O manual se contradiz; a seção 3.1 é a regra específica |
| S03 | WhatsApp **(67) 3321-4500**, telefone (67) 3341-4444 | O manual traz dois números; vale o da seção do canal |
| S04 | **Status prevalece sobre estoque** | Produto "em breve" ou descontinuado não é vendido, mesmo com estoque |
| S05 | Pedido só após confirmar **nome completo e telefone ou e-mail** | Privacidade (LGPD); há clientes com nomes parecidos na base |
| S06 | Com **duas promoções ativas** no mesmo produto, nenhuma vale | Escolher uma seria decisão comercial do sistema; o ETL alerta a equipe |
| S07 | E-mail **sem acento** | O manual traz duas grafias; domínio com acento raramente funciona |

As contradições e lacunas do manual foram reunidas em [`kb/pendencias_gerencia.md`](kb/pendencias_gerencia.md), como se fossem levadas à gerência da loja.

---

## Exemplos de conversa

A conversa de exemplo em texto está em [`exemplos/conversa.md`](exemplos/conversa.md), gerada na etapa 6 (avaliação). Ela cobre 5 cenários, gravados numa única sessão do CLI:

| Cenário | Por que é relevante |
|---|---|
| Violões disponíveis até R$ 1.000 | Busca no catálogo com filtros combinados (categoria, preço, status, estoque) |
| Devolução por arrependimento do pedido 4 | Não trivial: verificação de identidade, dados do pedido e política juntos, com prazos calculados |
| Produto sem estoque (Giannini GF-3D) | Alternativas semelhantes, como o manual pede |
| Pergunta fora do escopo e tentativa de prompt injection | Recusa com leveza e proteção dos dados de clientes |
| Endereço, horário e "estão abertos agora?" | Política e relógio real do fuso da loja |

### Na interface web

**Progresso em tempo real.** Enquanto o agente trabalha, a resposta mostra a etapa atual. Em perguntas com várias fontes, o plano aparece como um checklist que vai sendo marcado.

![Interface web: agente trabalhando na resposta](docs/img/ui-progresso.png)

**Pedido atrasado com reclamação.** O agente confere a identidade, consulta o pedido e registra a reclamação. O cartão do pedido mostra o atraso calculado na data de referência, e o cartão de protocolo traz o número da reclamação e o prazo de retorno.

![Interface web: cartão do pedido atrasado e protocolo da reclamação](docs/img/ui-pedido-reclamacao.png)

**Produto em promoção.** O cartão do produto mostra o preço original, o desconto, o PIX (que não se soma à promoção) e o parcelamento máximo dentro das faixas da seção 3.1 do manual. Todos os valores vêm calculados pela ferramenta, não pelo modelo.

![Interface web: cartão de produto com promoção, PIX e parcelamento](docs/img/ui-produto-promocao.png)

---

## Limitações conhecidas

- **Data simulada.** Os prazos de pedido usam 25/03/2026 (S01). Com dados atuais, basta mudar `REFERENCE_DATE`.
- **Qualidade depende do modelo, e testei a fundo só um.** Desenvolvi e testei com o `nvidia/nemotron-3.5-lightning:free`, gratuito no OpenRouter. É um modelo de pesos abertos da NVIDIA, do tipo *mixture-of-experts* (30 bilhões de parâmetros, 3 bilhões ativos por token), e o português não está entre as línguas que ele suporta oficialmente (inglês, espanhol, francês, alemão, italiano e japonês). Vários desvios observados nos testes vêm do modelo, e não das regras da solução:
  - ignorar avisos que as ferramentas devolvem (por exemplo, tratar a previsão de entrega como data de entrega, apesar do aviso explícito no resultado);
  - não chamar a ferramenta de planejamento em perguntas com várias fontes, como o prompt pede;
  - oferecer ações que o prompt proíbe ("se quiser fechar a compra, é só me dizer...") e perguntas de refinamento;
  - erros de português, como palavras inexistentes ("boawill") e concordância ("cordo de aço").

  O que é crítico não depende do modelo: valores, prazos, verificação de identidade e restrições de SQL são garantidos em código, e os cartões da interface mostram os dados de origem. A redação da resposta, porém, é do modelo. Parte dos desvios também pode ser reduzida na solução, e as correções estão na avaliação (etapa 6 de [`docs/processo.md`](docs/processo.md)).
- **Sem avaliador de saída.** Nenhuma etapa confere o texto final contra os resultados das ferramentas antes de enviá-lo. Os cartões da interface mitigam isso, mostrando os dados de origem.
- **Verificação de identidade simples.** Nome e telefone ou e-mail não são segredos. Num sistema real, o pedido seria consultado num canal autenticado ou com um código enviado ao cliente.
- **Sem passagem real para a equipe.** As reclamações ficam num SQLite local, sem notificação para ninguém. Quando algo depende da equipe, o agente indica os canais, mas não transfere a conversa.
- **Sem memória entre sessões.** A conversa da web some ao recarregar a página, de propósito (ver Persistência do histórico), e o agente não lembra de atendimentos anteriores do mesmo cliente.
- **Progresso do plano é aproximado.** Os passos do plano são texto livre do modelo, e a interface marca um passo a cada ferramenta concluída. É uma indicação de progresso, não um rastreio exato.
- **Base de conhecimento curada à mão.** Se o manual mudar, as seções precisam ser revisadas de novo. Os testes pegam valores que não estão no PDF, mas não regras que deixaram de ser incluídas.
- **Catálogo e manual divergem.** O manual cita instrumentos de sopro e cordas orquestrais, mas o sistema não tem nenhum produto dessas categorias. O agente segue o sistema.
- **Feriados não cadastrados.** O manual não os lista, então "estão abertos?" considera só o dia da semana e o horário.
- **Escala de protótipo.** SQLite, um processo e sessões em memória. Funciona para o desafio, não para muitos atendimentos simultâneos.

## Com mais tempo, eu faria

**Qualidade das respostas**
- Um **avaliador de saída** que confira valores, datas e afirmações do texto contra os resultados das ferramentas antes de enviar.
- **Observabilidade e avaliação para comparar modelos.** Traces de cada conversa (o Strands exporta OpenTelemetry: ferramentas chamadas, tempo, tokens e custo) e uma rodada automatizada das 36 perguntas de teste a cada mudança de prompt, ferramenta ou modelo, com regras para o que é verificável e um modelo avaliador para os critérios qualitativos. Assim daria para testar vários modelos no mesmo conjunto, ver como cada um se comporta (escolha de ferramentas, respeito à persona, português) e escolher com dados. Não consegui fazer essa comparação porque usei modelos e requisições gratuitas do OpenRouter, limitadas a 50 por dia: cada pergunta gasta de 3 a 5 chamadas ao modelo, então uma única rodada completa já passa de 100 requisições e o limite estoura rápido. Por isso testei a fundo só o Nemotron 3.5 Lightning, que não é otimizado para português. É de esperar que parte dos desvios descritos nas limitações diminua com modelos maiores ou com melhor suporte ao português, e é exatamente isso que essa avaliação comparativa mediria.

**Experiência do cliente**
- **Memória persistida entre sessões:** o cliente voltar outro dia, ou por outro canal, e o agente lembrar da conversa e do que já foi informado (pedido em andamento, produto de interesse, reclamação aberta). Hoje a memória vale só durante a conversa; no CLI, `--sessao` grava em disco local. Em produção, as sessões ficariam num armazenamento gerenciado (o Strands já tem um gerenciador de sessões para S3), ligadas a um cliente autenticado, com retenção e exclusão conforme a LGPD e os dados pessoais separados do catálogo.

**Operação**
- **Monitoramento em produção:** custo e latência por resposta, taxa de uso de cada ferramenta e alertas de falha do provedor.
- **Passagem real para a equipe:** integração com a API do WhatsApp Business e uma fila de atendimento humano, com as reclamações notificadas ao responsável.
- **Deploy de produção:** container com Docker em ECS/Fargate ou Lambda, chaves num gerenciador de segredos e o modelo via Amazon Bedrock.
- **Cache de prompt** (o prompt de sistema é fixo) para reduzir custo e latência.

**Segurança e dados**
- **Identidade forte** para consultar pedidos (código por SMS ou e-mail) e um classificador de prompt injection na entrada.
- **ETL de produção:** carga incremental, orquestração (Airflow) e validação com Pandera ou Great Expectations quando os dados vierem de um sistema vivo.
- **Base de conhecimento versionada,** com fluxo de aprovação da gerência a cada mudança do manual, e busca vetorial se o manual crescer.

---

## Uso de assistentes de IA

Usei o **Claude (Anthropic)**, no app conectado à pasta do projeto, como par de trabalho durante todo o desafio. O registro detalhado, etapa por etapa, está em [`docs/uso-de-ia.md`](docs/uso-de-ia.md).

**Meu workflow:**

1. **Entendimento próprio primeiro.** Li o enunciado e os dados e escrevi minhas anotações antes de envolver a IA.
2. **Contexto completo.** Dei ao Claude acesso aos materiais e às minhas anotações e pedi que entendesse tudo antes de começarmos.
3. **Plano criticado e validado.** Ele apontou pontos frágeis do meu plano, e eu decidi a ordem final das etapas.
4. **Debate antes de implementar.** Em cada etapa, ele levantou opções e trade-offs, eu decidi e só então ele implementou.
5. **Partes pequenas e revisadas.** Cada parte foi revisada por mim, testada e commitada por mim.

**Divisão de responsabilidades:**

- **Decisões são minhas** e estão registradas como tal em [`docs/decisoes.md`](docs/decisoes.md).
- **Código e documentação foram escritos pelo Claude** a partir das nossas discussões e revisados por mim.
- **Commits e pull requests são meus.**

**Ferramentas de IA usadas além da conversa:**

- **Skills do Claude:** leitura de PDF, exploração e validação de dados, system design e documentação.
- **Protótipo visual da interface,** para validar o desenho antes do código.
- **Verificação visual:** o Claude rodou a interface num navegador automatizado e conferiu as telas por captura, o que revelou bugs que os testes não pegavam.

A revisão humana fez diferença em vários pontos. Na primeira curadoria, interpretações tinham entrado no texto das políticas como se fossem do manual, e foram separadas depois de uma revisão linha a linha que pedi. Os ajustes de comportamento do agente (não oferecer ações, não fazer perguntas desnecessárias, não mostrar políticas internas) vieram de eu usar o agente como cliente.

---

## Checklist do desafio

| Requisito do enunciado | Como foi atendido | Status |
|---|---|---|
| Python como linguagem principal | Todo o projeto (ETL, agente, interface, testes) | Atendido |
| Assumir uma persona alinhada à loja | `kb/soul.md`, a partir das diretrizes de tom do manual (seção 7.1) | Atendido |
| Responder com base no contexto disponibilizado | Ferramentas sobre os CSVs tratados e base de políticas curada do PDF | Atendido |
| Saber quando consultar dados e quando consultar políticas | Tabela de roteamento no prompt, índice das políticas, `planejar` nas perguntas com as duas fontes | Atendido |
| Lidar com perguntas fora do escopo | Princípio de escopo na persona; casos de fora do escopo, acessórios e prompt injection no conjunto de teste | Atendido |
| Justificar framework, modelo, retrieval, prompt, interface, persistência e dados | Seção "Decisões técnicas" e `docs/decisoes.md` | Atendido |
| Documentar suposições diante de ambiguidades | S01 a S07 e `kb/pendencias_gerencia.md` | Atendido |
| README com instruções para rodar | Seção "Como rodar", testada numa cópia limpa | Atendido |
| Limitações conhecidas e o que faria com mais tempo | Seções acima | Atendido |
| Uso de assistentes de código | Seção acima e `docs/uso-de-ia.md` | Atendido |
| Repositório público com histórico real de commits | Uma branch e um pull request por etapa, com merge commit, sem force-push | Atendido |
| 3 a 5 conversas de exemplo, ao menos uma não trivial | 5 cenários em `exemplos/conversa.md`, entre eles a devolução do pedido 4 (identidade, dados do pedido e política juntos), e capturas da interface web nesta página | Atendido |
| PDF do README e da documentação (Written Case) | `docs/documentacao.pdf`, gerado por `python docs/gerar_pdf.py` | Atendido |

---

## Estrutura do repositório

```
data/raw/            CSVs e PDF de políticas originais, intocados
etl/                 schema, pipeline, verificações de qualidade, relatório e extração do PDF
kb/                  base de conhecimento: políticas por seção, persona, índice,
                     esquema do banco e pendências para a gerência
src/agente/          agente (Strands), regras de negócio, prompt e CLI
src/agente/tools/    as 9 ferramentas do agente
src/agente/ui/       interface web (Streamlit)
tests/               testes automatizados (pytest) e modelo roteirizado
tests/eval_set/      perguntas de teste com resposta esperada
docs/                arquitetura, processo, decisões, uso de IA, relatório de qualidade e PDF
exemplos/            conversa de exemplo com os 5 cenários (etapa 6)
```
