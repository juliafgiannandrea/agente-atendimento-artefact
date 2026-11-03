# Agente de Atendimento — Empório da Música

Protótipo de um agente de atendimento por mensagens de texto para a Empório da Música, loja fictícia de instrumentos musicais em Campo Grande/MS. Desenvolvido como desafio técnico para a vaga de AI Engineer na Artefact.

> 🚧 Em construção. As decisões técnicas estão sendo registradas em [`docs/decisoes.md`](docs/decisoes.md) e o uso de assistentes de IA em [`docs/uso-de-ia.md`](docs/uso-de-ia.md).

## Estrutura

```
data/raw/        CSVs e PDF de políticas originais, intocados
etl/             ETL: schema, pipeline, verificações de qualidade e relatório → data/emporio.db
kb/              políticas em Markdown, índice e persona
src/agente/      agente (Strands), tools, configuração do modelo e CLI
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

### 2. Rodar os testes

```bash
pytest
```

Os testes usam um banco temporário e não alteram `data/` nem `docs/`.

O comando do chat será adicionado nas próximas etapas.
