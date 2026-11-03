# vw_catalogo

Um produto por linha (65 produtos), com preço vigente e disponibilidade já calculados.

## Colunas

| Coluna | Tipo | Descrição |
|---|---|---|
| `product_id` | inteiro | Identificador do produto. |
| `name` | texto | Nome do produto, como exibido ao cliente (ex.: "Yamaha FG800 Dreadnought Natural"). |
| `name_search` | texto | Nome em minúsculas e sem acento, para buscas com `LIKE`. |
| `categoria` | texto | Nome da categoria: Violões, Ukuleles, Guitarras, Baixos, Baterias e Percussão, Teclados e Pianos. |
| `description` | texto | Descrição comercial do produto. |
| `specs` | texto (JSON) | Especificações técnicas; chaves por categoria abaixo. |
| `status` | texto | `active`, `discontinued` ou `coming_soon`. |
| `disponibilidade` | texto | `disponivel`, `sem_estoque`, `descontinuado` ou `em_breve`. |
| `disponibilidade_rotulo` | texto | Rótulo para o cliente: "Disponível", "Temporariamente indisponível", "Descontinuado", "Em breve". |
| `vendavel` | 0 ou 1 | 1 se o produto pode ser oferecido agora (ativo e com estoque). |
| `stock_quantity` | inteiro | Unidades em estoque. Não informe a quantidade exata ao cliente; use a disponibilidade. |
| `preco_tabela` | real | Preço de tabela, em reais. |
| `em_promocao` | 0 ou 1 | 1 se há promoção ativa aplicada. |
| `promocao_descricao` | texto | Nome da promoção ativa (ex.: "Oferta Especial"), ou nulo. |
| `desconto_percentual` | real | Percentual da promoção ativa, ou nulo. |
| `preco_final` | real | **Preço vigente**: com a promoção ativa, se houver. É o preço a informar. |
| `preco_pix` | real | Preço no PIX (5% de desconto só quando não há promoção). |
| `max_parcelas` | inteiro | Maior número de parcelas sem juros permitido para o preço final. |
| `valor_parcela_maxima` | real | Valor de cada parcela no parcelamento máximo. |

## Chaves de `specs` por categoria

| Categoria | Chaves | Valores encontrados |
|---|---|---|
| Violões | `top`, `back_sides`, `neck`, `strings`, `scale`, `electronics`, `color` | `strings`: "nylon" ou "steel" (aço); `electronics`: "yes" ou "no"; `top` contém "Sólido" quando o tampo é sólido |
| Ukuleles | `top`, `back_sides`, `neck`, `strings`, `scale`, `electronics`, `color` | `electronics`: "yes" ou "no" |
| Guitarras | `body`, `neck`, `strings`, `color` | `strings`: "6" |
| Baixos | `body`, `neck`, `strings`, `color` | `strings`: "4" |
| Baterias e Percussão | `shells`, `pieces`, `hardware`, `color` | `pieces`: "5" |
| Teclados e Pianos | `keys`, `type`, `polyphony`, `color` | `keys`: "61" |

## Exemplos

Violão elétrico com tampo sólido mais barato, disponível:

```sql
SELECT name, preco_final, json_extract(specs, '$.top') AS tampo
FROM vw_catalogo
WHERE categoria = 'Violões' AND vendavel = 1
  AND json_extract(specs, '$.electronics') = 'yes'
  AND json_extract(specs, '$.top') LIKE '%Sólido%'
ORDER BY preco_final
LIMIT 3
```

Quantidade de ukuleles disponíveis por tipo:

```sql
SELECT CASE
         WHEN name_search LIKE '%soprano%'  THEN 'Soprano'
         WHEN name_search LIKE '%concert%'  THEN 'Concert'
         WHEN name_search LIKE '%tenor%'    THEN 'Tenor'
         WHEN name_search LIKE '%baritono%' THEN 'Barítono'
       END AS tipo,
       COUNT(*) AS quantidade
FROM vw_catalogo
WHERE categoria = 'Ukuleles' AND vendavel = 1
GROUP BY tipo
```
