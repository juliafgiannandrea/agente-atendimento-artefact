# categories

As 9 categorias da loja. Algumas não têm produtos cadastrados no momento (sopro e cordas orquestrais): nesse caso, informe que não há itens dessa categoria agora, sem inventar produtos.

## Colunas

| Coluna | Tipo | Descrição |
|---|---|---|
| `category_id` | inteiro | Identificador da categoria. |
| `name` | texto | Nome da categoria (ex.: "Violões", "Instrumentos de Sopro (Madeiras)"). |
| `description` | texto | Descrição do que a categoria abrange. |

## Exemplo

Categorias e quantos produtos disponíveis cada uma tem:

```sql
SELECT c.name AS categoria, COUNT(v.product_id) AS disponiveis
FROM categories c
LEFT JOIN vw_catalogo v ON v.categoria = c.name AND v.vendavel = 1
GROUP BY c.name
ORDER BY disponiveis DESC
```
