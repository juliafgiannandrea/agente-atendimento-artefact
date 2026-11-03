# Agente de Atendimento — Empório da Música

Protótipo de um agente de atendimento por mensagens de texto para a Empório da Música, loja fictícia de instrumentos musicais em Campo Grande/MS. Desenvolvido como desafio técnico para a vaga de AI Engineer na Artefact.

> 🚧 Em construção. As decisões técnicas estão sendo registradas em [`docs/decisoes.md`](docs/decisoes.md) e o uso de assistentes de IA em [`docs/uso-de-ia.md`](docs/uso-de-ia.md).

## Estrutura

```
data/raw/        CSVs e PDF de políticas originais, intocados
etl/             ETL: schema, pipeline, verificações de qualidade e relatório → data/emporio.db
kb/              base de conhecimento: políticas por seção, índice, persona, pendências e esquema do banco
src/agente/      agente (Strands), tools, regras de negócio, prompt, CLI e interface web (ui/)
tests/           testes automatizados (pytest)
tests/eval_set/  perguntas de teste do agente com resposta esperada
docs/            decisões técnicas, relatório de qualidade de dados e registro de uso de IA
```

## Como rodar

Requer Python 3.11 ou mais recente.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # escolha PROVIDER e MODEL_ID e preencha a chave
```

### 1. Gerar o banco (ETL)

```bash
python -m etl.pipeline
```

Lê `data/raw/`, gera `data/emporio.db` (SQLite, com camadas bronze, silver e gold) e o relatório [`docs/data_quality.md`](docs/data_quality.md). Pode ser executado quantas vezes quiser: o banco é reconstruído do zero e o resultado é sempre o mesmo.

Para explorar o banco numa interface gráfica (Linux), use o DB Browser for SQLite:

```bash
sudo apt install sqlitebrowser
sqlitebrowser data/emporio.db
```

Tabelas `raw_*` são a origem (bronze), as demais tabelas são a camada tratada (silver), e as views `vw_catalogo` e `vw_pedidos` são o que o agente consulta (gold). Os resultados das verificações de qualidade ficam em `dq_results`.

### 2. Base de conhecimento (opcional)

A base de políticas já vem pronta em [`kb/`](kb/index.md). Para refazer a extração do PDF (por exemplo, quando o manual for atualizado):

```bash
python -m etl.extrair_politicas
```

Gera `kb/_fonte/manual_extraido.md`. As seções em `kb/politicas/` são curadas a partir desse texto e revisadas à mão.

### 3. Conversar com o atendente

Com o `.env` preenchido (provedor, modelo e chave) e o banco gerado:

```bash
python -m agente                  # conversa nova
python -m agente --sessao maria   # cria ou retoma a conversa "maria" (memória entre execuções)
python -m agente --debug          # mostra as ferramentas usadas em cada resposta
```

Ao iniciar, o CLI faz uma chamada mínima ao modelo para conferir a chave, o modelo e a conexão; se algo estiver errado, ele explica o problema e encerra. Use `--sem-verificacao` para pular esse teste.

Se usar um modelo gratuito do OpenRouter, escolha um com suporte a *tool calling* e saiba que eles têm limite de requisições por minuto e por dia. Alguns modelos gratuitos só aceitam chamadas de aplicativos cadastrados no OpenRouter e serão recusados.

Durante a conversa, `/exportar` salva o diálogo em Markdown em `exemplos/` e `/sair` encerra.

### 4. Interface web

```bash
streamlit run src/agente/ui/app.py
```

Abre o chat no navegador (por padrão em `http://localhost:8501`). A resposta do atendente aparece como texto e, abaixo, em cartões montados a partir dos dados consultados (produtos, pedidos, prazos, trecho da política). Em perguntas com várias etapas, o plano do atendente aparece como um checklist que vai sendo marcado em tempo real. A sidebar tem perguntas de exemplo e o botão "Nova conversa".

Rode o comando a partir da raiz do repositório, para o Streamlit usar o tema de `.streamlit/config.toml`.

O desenho da interface foi validado antes da implementação num protótipo visual, com a tela do chat (incluindo o checklist do plano animado), os cartões de cada ferramenta e o diagrama de arquitetura: [protótipo da interface](https://claude.ai/artifact/F9K2UnbBHQe9ksfwDXV8mh).

### 5. Rodar os testes

```bash
pytest
```

Os testes usam um banco temporário e não alteram `data/` nem `docs/`. O agente é testado com um modelo roteirizado, então **não é preciso chave de API** para rodar os testes.

