# Agente de Atendimento — Empório da Música

Protótipo de um agente de atendimento por mensagens de texto para a Empório da Música, loja fictícia de instrumentos musicais em Campo Grande/MS. Desenvolvido como desafio técnico para a vaga de AI Engineer na Artefact.

> 🚧 Em construção. As decisões técnicas estão sendo registradas em [`docs/decisoes.md`](docs/decisoes.md) e o uso de assistentes de IA em [`docs/uso-de-ia.md`](docs/uso-de-ia.md).

## Estrutura

```
data/raw/        CSVs e PDF de políticas originais, intocados
etl/             tratamento dos dados → gera data/emporio.db (SQLite)
kb/              políticas em Markdown, índice e persona
src/agente/      agente (Strands), tools, configuração do modelo e CLI
tests/eval_set/  perguntas de teste com resposta esperada
docs/            decisões técnicas e registro de uso de IA
```

## Como rodar

Requer Python 3.11 ou mais recente.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # escolha PROVIDER e MODEL_ID e preencha a chave
```

Os comandos do ETL e do chat serão adicionados nas próximas etapas.
