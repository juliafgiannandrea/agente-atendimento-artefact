# Conversas de exemplo

Conversas reais com o agente, exportadas pelo CLI (`/exportar`) durante a avaliação (etapa 6 de [`docs/processo.md`](../docs/processo.md)). Cada arquivo traz o modelo usado, a data de referência dos pedidos e, em cada resposta, as ferramentas que o agente chamou.

| Arquivo | Cenário |
|---|---|
| [`01-catalogo.md`](01-catalogo.md) | Violões disponíveis até R$ 1.000: busca no catálogo com filtros combinados |
| [`02-devolucao.md`](02-devolucao.md) | Devolução por arrependimento do pedido 4: identidade, dados do pedido e política juntos (caso não trivial) |
| [`03-sem-estoque.md`](03-sem-estoque.md) | Produto sem estoque, com alternativas semelhantes |
| [`04-fora-do-escopo.md`](04-fora-do-escopo.md) | Pergunta fora do escopo e tentativa de prompt injection |
| [`05-loja.md`](05-loja.md) | Endereço e "estão abertos agora?", com o relógio real do fuso da loja |

Capturas da interface web estão no [README](../README.md#na-interface-web).
