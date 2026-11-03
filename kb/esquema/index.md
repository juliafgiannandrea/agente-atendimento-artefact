# Banco do catálogo — visão geral

> **Nota de curadoria:** documentação lida pelo agente através da tool `entender_esquema`, antes de montar SQL livre. Reflete `etl/schema.sql`; `tests/test_tool_sql.py` confere que toda coluna das tabelas permitidas está documentada aqui. Clientes, pedidos e tabelas internas ficam fora de propósito (decisão D16 de `docs/decisoes.md`).

Banco SQLite, somente leitura. Contém o catálogo de produtos da loja.

## Quando usar SQL

Só quando nenhuma outra ferramenta responde. Exemplos:

- "Qual o violão elétrico com tampo sólido mais barato?" (filtro por especificação)
- "Quantos ukuleles vocês têm por tipo?" (contagem e agrupamento)
- "Qual a guitarra mais cara?", "Qual o preço médio dos violões de aço?"

Para listar produtos por categoria, preço ou promoção, use `buscar_produtos`. Para um produto específico, use `consultar_produto`. Para pedidos, use `consultar_pedido`.

## O que pode ser consultado

| Tabela | Conteúdo |
|---|---|
| `vw_catalogo` | Um produto por linha, com categoria, especificações, disponibilidade e preço vigente (já com promoção ativa, PIX e parcelamento). **Use esta na maioria dos casos.** |
| `categories` | As 9 categorias da loja, inclusive as que não têm produtos. |

Dados de clientes e pedidos **não** estão acessíveis por SQL.

## Regras

1. Um único `SELECT` (ou `WITH ... SELECT`) por chamada. Não use `;` no meio.
2. Preço para o cliente é sempre `preco_final` (já considera promoção ativa). Nunca calcule desconto por conta própria.
3. Para oferecer um produto, filtre `vendavel = 1`. Produtos com `vendavel = 0` estão sem estoque, descontinuados ou em breve.
4. Para buscar texto no nome, use `name_search` (minúsculas, sem acento): `name_search LIKE '%baritono%'`.
5. Especificações estão em JSON na coluna `specs`: `json_extract(specs, '$.strings')`. As chaves mudam por categoria (veja `vw_catalogo`).
6. O resultado volta com no máximo 50 linhas. Use `ORDER BY` e `LIMIT` para trazer só o necessário.
7. Se a query der erro ou não trouxer o que precisa, ajuste e tente de novo (até 4 consultas por mensagem do cliente).
