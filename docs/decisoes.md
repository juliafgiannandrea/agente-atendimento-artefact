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

---

## Suposições (o enunciado não define)

As suposições S01 a S03 são decisões minhas diante de informações ausentes ou divergentes nos materiais. Os IDs entre crases referem-se aos casos de `tests/eval_set/perguntas.yaml`.

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
