# Relatório de qualidade de dados

> Gerado automaticamente por `python -m etl.pipeline` (`etl/report.py`). Não edite à mão:
> as alterações são sobrescritas na próxima execução.

Inconsistências são **sinalizadas, não corrigidas em silêncio** (ver `docs/decisoes.md`, D09):
o valor original é mantido, e a flag e o tratamento adotado ficam registrados abaixo.

## Execução

- **Data de referência (S01):** 2026-03-25
- **Verificações de erro:** 6 executadas, 0 com falha
- **Verificações de alerta:** 15 executadas, 8 com ocorrências

### Linhas carregadas na camada silver

| tabela | linhas |
|---|---|
| categories | 9 |
| products | 65 |
| promotions | 25 |
| product_prices | 65 |
| customers | 50 |
| orders | 20 |
| order_items | 22 |

### Arquivos de origem (SHA-256)

| arquivo | sha256 |
|---|---|
| desafio_tecnico_ai_eng - categories.csv | `7a7901e16c8c6357…` |
| desafio_tecnico_ai_eng - products.csv | `78d911d96ee891ab…` |
| desafio_tecnico_ai_eng - promotions.csv | `cbe08c7e91b00437…` |
| desafio_tecnico_ai_eng - customers.csv | `1cd724dc86eac625…` |
| desafio_tecnico_ai_eng - orders.csv | `deb9c2480605d8d2…` |
| desafio_tecnico_ai_eng - order_items.csv | `7656eb681821d48e…` |

## Resumo das verificações

| id | severidade | resultado | tabela | verificação | qtd |
|---|---|---|---|---|---|
| E01 | erro | ✅ ok | todas | Chave primária duplicada | 0 |
| E02 | erro | ✅ ok | todas | Campo obrigatório ausente ou com tipo inválido | 0 |
| E03 | erro | ✅ ok | todas | Chave estrangeira sem registro correspondente | 0 |
| E04 | erro | ✅ ok | todas | Valor fora do domínio permitido (status, forma de pagamento, flags) | 0 |
| E05 | erro | ✅ ok | products | Coluna specs não é um objeto JSON válido | 0 |
| E06 | erro | ✅ ok | todas | Valor numérico fora da faixa válida | 0 |
| A01 | alerta | ⚠️ ocorrências | orders | Total do pedido diferente da soma dos itens a preço de tabela atual | 2 |
| A02 | alerta | ⚠️ ocorrências | orders | Parcelamento abaixo da parcela mínima da seção 3.1 do manual (S02) | 3 |
| A03 | alerta | ⚠️ ocorrências | order_items | Pedido contém produto que hoje está fora de comercialização (em breve ou descontinuado) | 2 |
| A04 | alerta | ⚠️ ocorrências | promotions | Produto com mais de uma promoção cadastrada | 3 |
| A05 | alerta | ✅ ok | promotions | Produto com mais de uma promoção ativa ao mesmo tempo (S06) | 0 |
| A06 | alerta | ✅ ok | promotions | Promoção ativa em produto que não está disponível para venda | 0 |
| A07 | alerta | ⚠️ ocorrências | products | Produto ativo sem estoque | 1 |
| A08 | alerta | ⚠️ ocorrências | categories | Categoria sem nenhum produto cadastrado | 3 |
| A09 | alerta | ✅ ok | products | Chaves de specs diferentes entre produtos da mesma categoria | 0 |
| A10 | alerta | ⚠️ ocorrências | orders | Pedido enviado com previsão de entrega vencida na data de referência | 1 |
| A11 | alerta | ✅ ok | orders | Pedido com data posterior à data de referência | 0 |
| A12 | alerta | ✅ ok | orders | Código de rastreio ausente, fora do padrão ou incoerente com o status | 0 |
| A13 | alerta | ⚠️ ocorrências | customers | Clientes com nomes contidos um no outro | 3 |
| A14 | alerta | ✅ ok | customers | Telefone fora do formato (DD) NNNNN-NNNN | 0 |
| A15 | alerta | ✅ ok | orders | Pedido cancelado sem motivo registrado | 0 |

## Detalhe dos alertas

### A01 — Total do pedido diferente da soma dos itens a preço de tabela atual

**Tratamento:** Mantido o total_brl original (valor cobrado). A base não tem preço unitário por item: a diferença pode ser desconto ou mudança de preço, não necessariamente erro.

| order_id | total_brl | itens_total | diferenca |
|---|---|---|---|
| 3 | 3450.0 | 3498.0 | -48.0 |
| 20 | 1400.0 | 1488.0 | -88.0 |

### A02 — Parcelamento abaixo da parcela mínima da seção 3.1 do manual (S02)

**Tratamento:** Histórico mantido como está. O agente aplica a regra vigente ao simular parcelamentos novos; o pedido antigo não é contestado com o cliente.

| order_id | total_brl | parcelas | valor_parcela | parcela_minima |
|---|---|---|---|---|
| 9 | 349.9 | 6 | 58.32 | 80.0 |
| 16 | 429.9 | 6 | 71.65 | 80.0 |
| 18 | 459.9 | 12 | 38.33 | 100.0 |

### A03 — Pedido contém produto que hoje está fora de comercialização (em breve ou descontinuado)

**Tratamento:** Pedido mantido. O status atual pode ter mudado depois da venda; o agente segue o status atual para novas ofertas (S04).

| order_id | status_pedido | product_id | name | status_produto |
|---|---|---|---|---|
| 3 | delivered | 130 | Kala KA-ABP-CTG Barítono Cedar | coming_soon |
| 14 | pending | 130 | Kala KA-ABP-CTG Barítono Cedar | coming_soon |

### A04 — Produto com mais de uma promoção cadastrada

**Tratamento:** Informativo enquanto no máximo uma estiver ativa; o conflito entre ativas é o A05.

| product_id | promocoes | ativas |
|---|---|---|
| 93 | [6, 23] | 0 |
| 96 | [8, 22] | 0 |
| 99 | [9, 25] | 0 |

### A07 — Produto ativo sem estoque

**Tratamento:** Informado como temporariamente indisponível, com sugestão de alternativas (manual 7.3).

| product_id | name |
|---|---|
| 96 | Giannini GF-3D Dreadnought Sunburst |

### A08 — Categoria sem nenhum produto cadastrado

**Tratamento:** O agente informa que não há itens dessa categoria no momento, sem inventar produtos, mesmo que o manual cite a categoria.

| category_id | name |
|---|---|
| 6 | Instrumentos de Sopro (Madeiras) |
| 7 | Instrumentos de Sopro (Metais) |
| 8 | Cordas Orquestrais |

### A10 — Pedido enviado com previsão de entrega vencida na data de referência

**Tratamento:** O agente reconhece o atraso e encaminha à equipe (retorno em até 24 horas úteis).

| order_id | estimated_delivery | dias_atraso |
|---|---|---|
| 8 | 2026-02-28 | 25 |

### A13 — Clientes com nomes contidos um no outro

**Tratamento:** Risco na verificação de identidade: a tool exige nome completo + telefone ou e-mail (S05), nunca só o nome.

| cliente_a | nome_a | cliente_b | nome_b |
|---|---|---|---|
| 11 | Bruno Carvalho Martins | 27 | Bruno Carvalho |
| 11 | Bruno Carvalho Martins | 43 | Bruno Martins |
| 13 | Diego Fernandes Castro | 47 | Diego Castro |
