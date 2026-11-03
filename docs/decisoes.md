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

---

## Suposições (o enunciado não define)

As suposições S01 a S03 e S06 são decisões minhas diante de informações ausentes ou divergentes nos materiais. Os IDs entre crases referem-se aos casos de `tests/eval_set/perguntas.yaml`.

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
  - **Escopo da data simulada:** vale para prazos e pedidos. A decisão sobre o horário de funcionamento ("estão abertos agora?"), que pode usar data e hora reais no fuso de Campo Grande (America/Campo_Grande, UTC−4), fica para a etapa das tools.
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
