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

---

## Suposições (o enunciado não define)

- **S01 — Data de referência:** a definir na etapa de ETL. Os pedidos param em março de 2026, e a data de hoje deixaria pedidos "pending" há meses.
