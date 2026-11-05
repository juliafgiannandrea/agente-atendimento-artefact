# Registro de decisões técnicas

Cada decisão traz o contexto, a escolha e o motivo. Este arquivo alimenta a seção de justificativas do README.

---

## D01 — Framework do agente: Strands Agents (Python)

- **Contexto:** o enunciado deixa a abordagem livre (RAG, function calling, ReAct, agente de SQL, híbrido) e exige Python.
- **Decisão:** Strands Agents como harness do agente, com loop ReAct e function calling.
- **Motivo:** o Strands é model-agnostic (Anthropic, OpenAI-compatível, Bedrock, Ollama, LiteLLM), define tools como funções Python decoradas e já traz o loop de raciocínio e chamada de ferramentas. Assim o esforço vai para o que importa no desafio: as tools, o contexto e os guardrails. Também é o framework que uso no dia a dia.

## D02 — Provedor e modelo configuráveis via `.env`

- **Contexto:** o avaliador precisa conseguir rodar o projeto, e modelos diferentes trazem trade-offs de custo, qualidade e disponibilidade.
- **Decisão:** as variáveis `PROVIDER` (`anthropic` | `openrouter`) e `MODEL_ID` definem o modelo. Uma função `build_model()` isola essa escolha, e o restante do agente não conhece o provedor.
- **Motivo:**
  - **Anthropic (Claude):** mais confiável para escolher tools, seguir persona e respeitar guardrails. É pago à parte da assinatura do Claude, com créditos no Console. Uso o Claude para gerar as conversas finais.
  - **OpenRouter (modelos `:free`):** custo zero para desenvolver e para o avaliador rodar. Em troca, tem limite de requisições (50/dia sem créditos), suporte a tool calling variável entre modelos e uma lista de modelos que muda com o tempo.
  - Trocar de provedor permite comparar os modelos no mesmo conjunto de testes.

## D03 — Banco de dados: SQLite

- **Contexto:** os dados chegam como 6 CSVs pequenos (65 produtos, 50 clientes, 20 pedidos).
- **Decisão:** SQLite, gerado por um script de ETL a partir de `data/raw/`. O arquivo `.db` não é versionado e é recriado a cada execução do ETL.
- **Motivo:** não precisa de servidor nem de infraestrutura, vem na biblioteca padrão do Python e aceita SQL de verdade, inclusive views. Postgres seria exagero para esse volume e aumentaria o atrito para quem avalia.

## D04 — Interface: CLI

- **Contexto:** o enunciado aceita CLI, notebook, API ou UI simples, com foco no agente funcionando.
- **Decisão:** interface de linha de comando.
- **Motivo:** é rápida de construir e testar e facilita exportar as conversas de exemplo em `.md`. O tempo economizado vai para o agente. Respostas renderizadas, como cards de produto ou trechos de política com formatação, ficam como evolução.
- **Atualização (etapa 5):** com o agente pronto, sobrou tempo para a interface web em Streamlit (D21). O CLI continua como canal de texto puro e como forma de exportar conversas.

## D05 — Sem Docker (por enquanto)

- **Contexto:** o projeto é Python puro, com SQLite e dependências de pip.
- **Decisão:** ambiente virtual com `requirements.txt`, sem Docker na primeira versão.
- **Motivo:** o ganho de reprodutibilidade é pequeno para esse stack. Num CLI interativo, o Docker exige `-it`, `--env-file` e volumes, e obrigaria documentar dois caminhos de execução. Um `Dockerfile` pode entrar como extra se sobrar tempo, e o caminho para produção (ECS/Fargate ou Lambda) vai para "com mais tempo, eu faria".

## D06 — Gerenciador de ambiente: `pip` + `requirements.txt`

- **Decisão:** `venv` com `pip install -r requirements.txt`, em Python 3.11 ou mais recente.
- **Motivo:** é o caminho que qualquer avaliador já conhece, sem instalar ferramentas extras. O `uv` é compatível com esse arquivo para quem preferir.

## D07 — Leitura do PDF de políticas sem OCR

- **Contexto:** `políticas_da_loja.pdf` tem texto nativo, que a extração lê sem perda.
- **Decisão:** extrair com `pdfplumber` (inclusive as tabelas de pagamento e frete), converter uma única vez para Markdown dividido por seção e revisar à mão.
- **Motivo:** OCR só é necessário para PDF escaneado. Como a política é estática, uma conversão revisada e versionada é mais confiável que reprocessar o PDF a cada execução. A revisão humana também serve como ponto de governança.

## D08 — Conjunto de perguntas de teste antes do agente

- **Contexto:** os dados e o manual têm armadilhas (status x estoque, promoções inativas, regras ambíguas, dados pessoais de clientes).
- **Decisão:** escrever o conjunto de perguntas de teste (`tests/eval_set/perguntas.yaml`) antes de construir o agente, com fonte esperada, fatos obrigatórios e o que invalida cada resposta.
- **Motivo:** os casos guiam o desenho das tools e da KB e viram a base da avaliação. Também expõem cedo as suposições que precisam ser decididas (abaixo).

## D09 — Arquitetura do ETL em camadas (bronze, silver, gold) dentro do SQLite

- **Contexto:** os CSVs têm inconsistências que o agente não pode esconder nem repassar sem critério.
- **Decisão:** três camadas no mesmo banco, reconstruído do zero a cada execução (*full refresh*):
  - **bronze (`raw_*`):** cópia fiel dos CSVs, todas as colunas como texto, sem tratamento;
  - **silver:** tabelas tipadas e padronizadas, com chave primária, chave estrangeira e `CHECK` declarados no schema, mais colunas de flag de qualidade;
  - **gold (`vw_*`):** views de negócio consumidas pelas tools do agente (catálogo com preço final e disponibilidade; pedidos com itens).
- **Motivo:**
  - a bronze dentro do banco permite comparar origem e dado tratado em SQL, e os arquivos de `data/raw/` nunca são alterados;
  - o *full refresh* torna o ETL idempotente: rodar duas vezes gera o mesmo banco, o que é simples e suficiente para o volume (65 produtos, 20 pedidos);
  - inconsistências são **sinalizadas, não corrigidas em silêncio**: o valor original é mantido, e o valor calculado e a flag entram ao lado.

## D10 — Ferramentas do ETL: pandas + SQL + verificações em Python puro

- **Decisão:** pandas para ler e tipar os CSVs; SQL (`schema.sql`) para tabelas, restrições e views; verificações de qualidade como funções Python com severidade (**erro** bloqueia o ETL; **alerta** é registrado e o ETL continua). Os resultados vão para a tabela `dq_results`, e o `docs/data_quality.md` é gerado a partir dela.
- **Motivo:** para 6 tabelas pequenas, bibliotecas de validação (Pandera, Great Expectations) acrescentariam dependência e configuração sem ganho proporcional; verificações próprias deixam a regra de cada checagem visível no código. A adoção dessas bibliotecas fica em "com mais tempo, eu faria".

## D11 — Dados de clientes no mesmo banco

- **Decisão:** a tabela de clientes fica no mesmo SQLite das demais.
- **Motivo:** suficiente para o protótipo. A proteção dos dados pessoais está na camada de acesso: as tools nunca listam clientes, e dados de pedido só saem após a verificação de identidade (S05). Separar os dados pessoais em outro banco ou serviço, com controle de acesso próprio, fica como melhoria.

## D12 — Testes automatizados com pytest

- **Decisão:** testes com `pytest` para o ETL (idempotência, contagens, flags esperadas nos casos conhecidos) e, depois, para as regras de negócio e as tools.
- **Motivo:** garantem que uma mudança no código não quebre silenciosamente o que já funcionava, e documentam o comportamento esperado de forma executável.

## D13 — Regras de negócio num único módulo (`src/agente/regras.py`)

- **Contexto:** regras como parcelamento (S02), PIX, conflito de promoções (S06) e disponibilidade (S04) são usadas tanto pelo ETL (flags e preços calculados) quanto pelas tools do agente.
- **Decisão:** cada regra é escrita uma vez em `src/agente/regras.py` e importada pelos dois lados. Os preços vigentes são calculados em Python com essas regras e gravados na tabela `product_prices`, em vez de reescritos em SQL nas views. A normalização de texto (busca de produto e verificação de identidade) segue o mesmo princípio, em `src/agente/normalizacao.py`.
- **Motivo:** evita que o relatório de qualidade e o agente divirjam sobre a mesma regra. Valores monetários usam `Decimal` com arredondamento comercial, para evitar erros de ponto flutuante (ex.: 2.199 × 0,95 = 2.089,05, e não 2.089,0499…).

## D14 — Detalhes do ETL

- **Carga atômica:** o banco é construído num arquivo temporário e só substitui o definitivo no fim. Se uma verificação de erro falhar, o ETL para e o banco anterior continua intacto.
- **Relatório determinístico:** `docs/data_quality.md` não tem horário de execução (que fica em `etl_metadata`). A mesma entrada gera o mesmo arquivo, então o diff no Git só muda quando os dados ou as regras mudam.
- **Toda verificação é registrada**, inclusive as que passaram, para mostrar o que foi conferido e não só o que deu errado.
- **Produto fora de comercialização em pedido (A03)** considera só o status (`coming_soon` ou `discontinued`), não o estoque: um item vendido que esgotou depois é normal e não indica inconsistência.
- **Rótulos de status de pedido:** a base não define o significado de `pending` e `confirmed`. Os rótulos usados ("Pedido recebido, aguardando processamento" e "Pedido confirmado, em preparação para envio") são uma interpretação neutra, que não promete prazos.
- **Pacote instalável:** `pyproject.toml` + `-e .` no `requirements.txt` tornam `agente` e `etl` importáveis de qualquer diretório, sem manipular `sys.path`.

## D15 — Base de conhecimento em Markdown por seção, com índice (divulgação progressiva)

- **Contexto:** o manual tem 8 páginas e 10 seções. Cada pergunta do cliente costuma precisar de uma ou duas delas.
- **Decisão:** `kb/` com um arquivo por seção do manual (`kb/politicas/*.md`), um `kb/index.md` que descreve quando consultar cada seção, a persona em `kb/soul.md` e as contradições em `kb/pendencias_gerencia.md`. O agente lê o índice e carrega só a seção necessária, por meio de uma tool. Sem banco vetorial nem embeddings.
- **Motivo:**
  - **Por que não RAG vetorial:** com 9 seções curtas, um índice escrito à mão é mais preciso que busca por similaridade e não perde contexto ao cortar o texto em pedaços. Também é auditável: dá para ver exatamente qual seção o agente leu para responder. Com um manual muito maior, a busca vetorial passaria a valer a pena.
  - **Por que não o manual inteiro no prompt:** caberia, mas misturaria regras de assuntos diferentes em toda resposta, gastaria tokens em todo turno e dificultaria saber em que o agente se baseou.
- **Pipeline:** `python -m etl.extrair_politicas` gera `kb/_fonte/manual_extraido.md` (texto bruto do PDF, automático). As seções em `kb/politicas/` são curadoria a partir desse texto: reorganizadas, com as decisões S02, S03 e S07 aplicadas e com notas de curadoria (blocos `> Nota de curadoria`) que separam o que é do manual do que é interpretação.
- **Dois tipos de nota:** blocos `> **Orientação ao assistente:**` dizem ao agente como agir e são entregues a ele; blocos `> **Nota de curadoria:**` registram a origem de decisões e lacunas para humanos e são removidos por `src/agente/kb.py` antes de chegar ao agente. Assim, referências internas (como "S03" ou "docs/decisoes.md") nunca aparecem na conversa com o cliente, e quem audita a base continua vendo de onde veio cada decisão. Um teste garante que o texto entregue ao agente não contém essas referências.
- **Índice para o agente:** gerado dos cabeçalhos das seções (`id`, `titulo`, `quando_consultar`), e não do `kb/index.md`, que é a documentação para humanos. Assim o índice do agente não fica desatualizado.
- **Governança:** cada seção tem no cabeçalho a versão do manual, as páginas de origem, o público (`cliente` ou `interno`) e o status de revisão humana. A seção 7 do manual vira duas peças: as diretrizes de tom (7.1) vão para a persona; o fluxo e as situações especiais (7.2 e 7.3) ficam numa seção interna, que orienta o agente mas não é citada ao cliente.
- **Testes de fidelidade:** `tests/test_kb.py` extrai todo valor verificável das seções curadas (preços, percentuais, prazos, telefones, e-mails, leis) e confere que ele existe no texto do PDF. Se a curadoria introduzir um valor que não está no manual, o teste falha.

## D16 — Arquitetura do agente: tools de contrato fechado + SQL livre como último recurso

- **Contexto:** o agente precisa saber quando consultar dados e quando consultar políticas, sem inventar.
- **Decisão:** loop ReAct do Strands com oito tools:

  | Tool | Fonte | Para quê |
  |---|---|---|
  | `buscar_produtos` | `vw_catalogo` | Listar opções com filtros (categoria, preço, texto, promoção) |
  | `consultar_produto` | `vw_catalogo` | Um produto: preço, PIX, parcelas, disponibilidade; alternativas se indisponível |
  | `consultar_pedido` | `vw_pedidos` + `customers` | Pedido com verificação de identidade e prazos calculados |
  | `ler_politica` | `kb/politicas/` | Uma seção da base de políticas |
  | `registrar_reclamacao` | `data/atendimento.db` | Registrar e encaminhar, com protocolo |
  | `hora_atual_loja` | relógio | Se a loja está aberta e quando a equipe volta |
  | `entender_esquema` | `kb/esquema/` | Documentação do banco antes de montar SQL |
  | `consultar_banco` | `vw_catalogo`, `categories` | SQL livre, somente leitura |

- **Motivo:**
  - **Tools fechadas primeiro:** cobrem as perguntas recorrentes do enunciado com parâmetros tipados. O modelo não escreve SQL para o que é frequente, então erra menos e não há como contornar regras.
  - **Cálculos no código, não no modelo:** preços com promoção, PIX, parcelamento máximo, atraso de entrega e prazos de devolução, troca e garantia chegam prontos nas respostas das tools, calculados por `src/agente/regras.py`. O modelo só repete. Valores monetários já vêm formatados ("R$ 1.299,00").
  - **SQL livre como último recurso:** para perguntas que as tools não preveem (filtrar por especificação técnica, contar, comparar). O agente lê a documentação do esquema (`entender_esquema`, com divulgação progressiva: visão geral, depois a tabela), monta a query, executa (`consultar_banco`) e pode refazer se o resultado não bastar.
  - **Alternativas automáticas:** quando o produto está sem estoque, descontinuado ou em breve, `consultar_produto` já devolve até 3 alternativas da mesma categoria, priorizando o mesmo tipo (dreadnought, 7 cordas, nylon, barítono...) e depois o preço mais próximo (manual 7.3).

## D17 — Guardrails em camadas

- **Princípio:** o que é crítico (privacidade, integridade dos dados) é garantido **em código**, não só no prompt. O prompt orienta; o código impede.
- **Verificação de identidade (`consultar_pedido`):** exige nome com pelo menos nome e sobrenome, todos presentes no cadastro, **e** telefone (só dígitos, com ou sem DDD) ou e-mail idênticos ao do titular. Se não conferir, a tool não devolve nada do pedido, nem se ele existe ou de quem é. Depois de 3 falhas na mesma conversa, a tool para de consultar e orienta o cliente a falar com a equipe (contra tentativa e erro).
- **SQL livre (`consultar_banco`):**
  - conexão `mode=ro` (somente leitura) e autorizador do SQLite que nega tudo que não seja leitura;
  - só lê `vw_catalogo` e `categories`. Clientes, pedidos, tabelas brutas e de qualidade ficam fora, para que o SQL livre não contorne a verificação de identidade. Um CTE com o nome da view não engana o autorizador: as tabelas lidas por trás dela precisam ser as do catálogo;
  - um comando por chamada, até 2.000 caracteres, até 50 linhas, interrupção de consultas longas e no máximo 4 consultas por mensagem do cliente.
- **Entrada:** mensagens acima de 2.000 caracteres não chegam ao modelo.
- **Falhas do provedor:** são classificadas pelo código HTTP (chave inválida, sem créditos, modelo recusado, modelo inexistente, limite de requisições, falha de conexão). O cliente recebe uma mensagem amigável, com uma versão própria para limite de requisições ("muitas conversas ao mesmo tempo, tente em um minuto"); quem opera o CLI vê um aviso com o motivo e o que fazer.
- **Novas tentativas:** no máximo 3 chamadas ao modelo por rodada, com esperas de 2 segundos, em vez do padrão do Strands (6 tentativas, mais de 1 minuto de espera), que deixava o terminal parado sem explicação.
- **Verificação ao iniciar:** o CLI faz uma chamada mínima ao modelo antes da conversa e encerra com uma mensagem clara se a chave, o modelo ou a conexão estiverem com problema (`--sem-verificacao` pula o teste e economiza uma requisição). Os avisos internos do Strands só aparecem com `--debug`.
- **Prompt:** persona com princípios inegociáveis (não inventar, transparência de preço, escopo, privacidade, não decidir pela loja, instruções só da loja) e regras de qual fonte usar. Notas de curadoria e referências internas nunca entram no prompt.
- **Avaliador de saída:** não implementado nesta versão (ver limitações).

## D18 — Prompt de sistema e memória

- **Formato:** texto simples, sem Markdown (sem negrito com asteriscos, títulos ou tabelas), como numa conversa de WhatsApp. Num teste, o modelo respondia com `**negrito**`, que aparece como asteriscos no terminal. **Atualização (etapa 5):** o formato passou a depender do canal; a interface web aceita Markdown leve (D21).
- **Prompt:** persona (`kb/soul.md`) + tabela de qual ferramenta usar para cada tipo de pergunta + índice das políticas (gerado dos cabeçalhos) + data de referência. A hora atual não entra no prompt, para não ficar desatualizada: vem da tool `hora_atual_loja`.
- **Memória na sessão:** o histórico de mensagens do Strands, com janela deslizante de 40 mensagens (`SlidingWindowConversationManager`), que preserva os pares de chamada e resultado de tools.
- **Memória entre execuções (opcional):** `python -m agente --sessao <id>` usa o `FileSessionManager` do Strands e grava a conversa em `data/sessoes/`, fora do Git. Os contadores dos guardrails (tentativas de identificação) recomeçam a cada execução.
- **Reclamações** ficam em `data/atendimento.db`, separado do banco do ETL, que é reconstruído a cada execução e perderia os registros.

## D19 — Testes do agente sem chamar API

- **Decisão:** as tools são testadas diretamente contra um banco gerado pelo ETL num diretório temporário; o loop do agente é testado com um modelo roteirizado (`tests/modelo_roteirizado.py`), que simula o modelo chamando tools em sequência.
- **Motivo:** os testes rodam sem chave de API, de graça e de forma determinística, e cobrem o que é código: guardrails, cálculos, montagem do prompt, registro das tools, memória e o fluxo de SQL em duas etapas. A qualidade das respostas do modelo é avaliada à parte, com o conjunto de perguntas de teste (`tests/eval_set/`).

## D20 — Planejamento explícito com a tool `planejar`

- **Contexto:** no loop ReAct puro, o modelo decide um passo de cada vez, sem plano visível. Num teste de reclamação, o agente encadeou bem três tools, mas afirmou um fato que o cliente não tinha dito ("você já aceitou a entrega").
- **Decisão:** uma tool `planejar(objetivo, passos, informacoes_faltantes)`, chamada antes das outras **só** quando a pergunta exige mais de uma fonte ou várias etapas (devolução, troca, reclamação sobre um pedido). A tool não consulta nada: registra e devolve o plano, e orienta a perguntar ao cliente o que estiver em `informacoes_faltantes`. O prompt também proíbe afirmar fatos sobre o cliente que ele não disse e que nenhuma ferramenta retornou.
- **Motivo:**
  - o campo de informações faltantes leva o modelo a **perguntar em vez de supor**;
  - o plano fica **visível** no `--debug`, na conversa exportada e, na UI, como o primeiro cartão da resposta, o que mostra como o agente decide entre dados e políticas;
  - restringir a perguntas com várias fontes evita gastar uma requisição a mais nas perguntas simples, que são a maioria.
- **Alternativas descartadas:** instrução de planejamento só no prompt (invisível); planejador separado no estilo *plan-and-execute* (dobra as chamadas ao modelo em toda mensagem e falha mais com modelos gratuitos); raciocínio nativo do modelo (depende do provedor e não tem estrutura).

## D21 — Interface web em Streamlit, com cartões montados a partir das tools

- **Contexto:** o CLI mostra só texto. A UI deveria mostrar respostas "renderizadas", sem perder a confiabilidade dos dados.
- **Decisão:** Streamlit (`src/agente/ui/`), reaproveitando o mesmo `Atendente` do CLI. A resposta tem duas camadas, exibidas nesta ordem: o plano (quando há), os cartões e, por último, o texto, que comenta o que está nos cartões:
  - o **texto** do modelo, em Markdown leve (o prompt tem um formato por canal: `texto` proíbe Markdown, `ui` permite negrito e listas);
  - **cartões** montados a partir do **resultado das tools**, não do texto: produto (preço, promoção, PIX, parcelas, alternativas), busca (tabela), pedido (status, prazos, atraso), horário e protocolo de reclamação. A primeira versão também mostrava o trecho da política consultada, retirado depois (D23).
- **Motivo:** os cartões mostram exatamente o que saiu do banco; o modelo não tem como "inventar" um cartão. Também deixam visível ao avaliador qual fonte foi usada em cada resposta. A alternativa de pedir ao modelo uma saída estruturada (JSON de blocos) foi descartada por falhar com frequência em modelos gratuitos.
- **Plano como checklist em tempo real:** o `Atendente` aceita um ouvinte que é avisado quando cada tool começa e termina (hooks `BeforeToolCallEvent` e `AfterToolCallEvent` do Strands). A UI desenha o plano registrado por `planejar` e marca um passo a cada tool concluída; o último passo fecha com a resposta. Sem plano, aparece uma linha de status ("Consultando o pedido…"). Como os passos do plano são texto livre do modelo, o vínculo passo ↔ tool é aproximado: é uma indicação de progresso, não um rastreio exato.
- **Detalhes técnicos invisíveis:** nomes de tools, SQL e erros do provedor não aparecem para o cliente. Os textos das políticas não são exibidos (D23). Erros técnicos vão para o terminal de quem roda a UI.
- **Segurança:** todo valor vindo dos dados ou do modelo é escapado antes de entrar no HTML dos cartões.
- **Estado:** o `Atendente` e o histórico ficam em `st.session_state` (um por aba), para que o Streamlit redesenhe a conversa sem chamar o modelo de novo.
- **Identidade visual:** inspirada na Artefact (azul-marinho `#0D1634`, magenta e roxo, IBM Plex Sans, botões em pílula). O magenta da marca (`#FF0066`) tem contraste 3,9:1 com texto branco; onde há texto, usa-se `#E0005A` (4,9:1).

## D22 — O agente responde, não executa (exceto registrar reclamações)

- **Contexto:** num teste, o agente fechou a resposta sobre o Takamine GD20 com "Quer que eu reserve?". O desafio pede um agente que **responda** às perguntas dos clientes, e o agente não tem como reservar, vender ou alterar nada.
- **Decisão (minha):** o agente não executa nem oferece ações: reservar ou separar produtos, fechar compras, gerar links de pagamento, cancelar ou alterar pedidos, aprovar trocas ou devoluções, agendar. Quando o cliente quer algo assim, ele explica a política e indica os canais da equipe (WhatsApp, telefone, e-mail ou a loja). O fechamento pergunta se há mais alguma dúvida, sem oferecer ações.
- **Exceção:** `registrar_reclamacao` foi mantida. O manual (seção 7.3) pede que a reclamação seja registrada e encaminhada ao responsável, com retorno em 24 horas úteis.
- **Onde está:** regra no prompt (`src/agente/prompt.py`), princípio na persona (`kb/soul.md`) e as orientações da base de políticas, que passaram de "encaminhe à equipe" para "oriente o cliente a falar com a equipe". As seções alteradas voltaram para `revisao_humana: pendente` e foram aprovadas de novo depois da minha revisão.

## D23 — O agente só responde: sem ajuda extra nem perguntas de refinamento; a UI não mostra as políticas

- **Contexto:** perguntando sobre saxofone (a loja não tem instrumentos de sopro no sistema), o agente respondeu "Você procura algum modelo específico (alto, tenor, soprano) ou tem alguma faixa de preço em mente? Posso te avisar se chegar algo novo...". A pergunta já tinha resposta, e "avisar" é uma ação que ele não executa. Na UI, a política consultada aparecia num expansor "Política consultada".
- **Decisão (minha):** o agente existe para tirar das costas da equipe as perguntas recorrentes, então responde o que foi perguntado e para. Não oferece ajuda além do que foi pedido, não promete nada para depois e não pergunta preferências (orçamento, modelo) para refinar uma resposta que já pode dar. Pergunta apenas o que falta para conseguir responder (identificação do cliente, número do pedido, qual produto). Quando não tem a informação, diz isso e indica os canais da equipe, em vez de "vou verificar com a equipe".
- **O que continua, porque o manual pede (seções 7.2 e 7.3):** sugerir alternativas semelhantes quando o produto está sem estoque ou fora de linha, e fechar perguntando, no máximo, se ficou alguma dúvida.
- **Políticas na UI:** o manual é material interno da loja. A UI deixou de mostrar o texto das políticas consultadas; o cliente recebe só a regra que responde à pergunta, no texto do atendente. Os cartões continuam para dados do sistema (produto, pedido, prazos, horário, protocolo).
- **Onde está:** `kb/soul.md` (princípios 1 e 6 e o fluxo de atendimento), `src/agente/prompt.py` e `src/agente/ui/componentes.py`.

---

## Suposições (o enunciado não define)

As suposições S01 a S03, S06 e S07 são decisões minhas diante de informações ausentes ou divergentes nos materiais. Os IDs entre crases referem-se aos casos de `tests/eval_set/perguntas.yaml`.

- **S01 — Data de referência simulada: 25/03/2026 (quarta-feira).**
  - **Problema:** os pedidos vão de out/2025 a 22/03/2026. Com a data real (nov/2026):
    - os pedidos "pending" e "confirmed" estariam parados há cerca de 8 meses;
    - o pedido 8, "enviado", estaria 8 meses atrasado;
    - todos os pedidos estariam fora do arrependimento (7 dias), da troca por defeito (30 dias) e da garantia legal (90 dias).

    Na prática, todo caso de pedido viraria "está muito atrasado, vou encaminhar" ou "o prazo venceu". Isso não representa a operação da loja e elimina justamente os casos que testam o raciocínio do agente: calcular, com dados e política juntos, se o cliente ainda está dentro de um prazo.
  - **Decisão:** o agente opera numa data simulada próxima ao último pedido, configurável em `REFERENCE_DATE` no `.env`. Com ela, a base se comporta como uma operação em andamento, com pedidos recentes, prazos em aberto e um atraso real (pedido 8).
  - **Alternativas descartadas:**
    - usar a data real e aceitar todos os prazos vencidos, pelo motivo acima;
    - deslocar no ETL todas as datas da base para perto de hoje. Mantém o calendário real, mas altera os dados originais e exige justificar a transformação; a data simulada é mais simples e transparente.
  - **Promoções não dependem da data:** a tabela de promoções só tem o campo `is_active`, sem período de vigência. O caso da Black Friday (`promo-02`) se comporta igual com qualquer data, porque as promoções de Black Friday estão inativas. Simular uma Black Friday ativa exigiria inventar dados que a loja não cadastrou.
  - **Escopo da data simulada:** vale para prazos e pedidos. O horário de funcionamento ("estão abertos agora?") usa a data e a hora reais no fuso de Campo Grande (America/Campo_Grande, UTC−4), pela tool `hora_atual_loja`. Feriados não estão cadastrados, porque o manual não os lista.
  - **Efeitos:** o pedido 8 (enviado, previsão 28/02/2026) aparece com 25 dias de atraso; o pedido 4 (entregue, previsão 22/12/2025) está fora do arrependimento e da troca por defeito e acabou de sair da garantia legal; a Black Friday (novembro) não é a campanha do momento.
  - **Casos afetados:** `enun-04b`, `promo-02`, `ident-03`.

- **S02 — Parcelamento: valem as faixas da seção 3.1 do manual.**
  - **Problema:** o manual se contradiz. A tabela da seção 3 diz "Cartão de Crédito: até 12x sem juros, parcela mínima de R$ 100,00"; a seção 3.1 detalha faixas diferentes.
  - **Decisão:** sigo a seção 3.1, por ser a regra específica e detalhada:
    - até 3x: sem juros, sem mínimo de parcela (exceto compras abaixo de R$ 50, que não são parceladas);
    - 4x a 6x: sem juros, parcela mínima de R$ 80;
    - 7x a 12x: sem juros, parcela mínima de R$ 100.
  - **Registro:** a divergência entra na lista de pendências para a gerência.
  - **Caso afetado:** `parc-02`.

- **S03 — Contatos: WhatsApp (67) 3321-4500; telefone (67) 3341-4444.**
  - **Problema:** o manual traz dois números. A capa e os dados da empresa listam "(67) 3341-4444 — Telefone / WhatsApp"; a seção 7, dedicada ao atendimento remoto, diz "O canal de WhatsApp (67) 3321-4500".
  - **Decisão:** uso o número da seção 7 como WhatsApp, por ser a seção específica do canal, e o (67) 3341-4444 como telefone fixo da loja.
  - **Registro:** a divergência entra na lista de pendências para a gerência.
  - **Caso afetado:** `extra-02`.

- **S04 — Status prevalece sobre estoque:** produto `coming_soon` ou `discontinued` não é oferecido para compra, mesmo com `stock_quantity` > 0. Caso afetado: `estq-03` (Kala KA-ABP-CTG, `coming_soon` com 2 unidades).

- **S05 — Verificação de identidade:** dados de pedido só são informados depois que o cliente confirma nome completo e telefone ou e-mail do titular. A checagem fica na tool, não só no prompt. Casos afetados: `ident-01` a `ident-04` (pedidos e identidade) e `inj-04`/`inj-05` (tentativas de burlar a verificação por SQL injection e por instrução falsa de "sistema").

- **S06 — Conflito de promoções: com duas ou mais promoções ativas para o mesmo produto, nenhuma vale.**
  - **Problema:** a base tem produtos com mais de uma promoção (93, 96 e 99) e não define qual prevalece. Hoje as duplicatas são todas de promoções inativas, mas a regra precisa existir para quando a base for atualizada.
  - **Decisão (minha):** se um produto tiver mais de uma promoção ativa, nenhuma é aplicada, o produto é vendido pelo preço de tabela e o ETL registra um alerta para a equipe resolver.
  - **Motivo:** escolher automaticamente (por exemplo, o maior desconto) seria uma decisão comercial tomada pelo sistema sem autorização. Aplicar o preço de tabela evita prometer um desconto que pode não valer, como pede o manual (seção 7.3), e o alerta torna o conflito visível em vez de escondê-lo.
  - **Duplicatas inativas:** são registradas como alerta informativo, sem efeito no preço.

- **S07 — E-mail de contato: contato@emporiodamusica.com.br (sem acento).**
  - **Problema:** o manual traz duas grafias. A capa usa contato@emporiodamusica.com.br; a tabela "Dados da Empresa" (seção 1.2) usa contato@empóriodamusica.com.br, com acento.
  - **Decisão:** uso a grafia sem acento, a mesma da capa. Domínios com acento raramente funcionam em todos os provedores de e-mail, e a versão com acento parece erro de digitação.
  - **Registro:** a divergência entra na lista de pendências para a gerência (`kb/pendencias_gerencia.md`, P2).
