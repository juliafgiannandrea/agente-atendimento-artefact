# Conversa de exemplo

[`conversa.md`](conversa.md) é uma conversa real com o agente, exportada pelo CLI (`/exportar`) durante a avaliação (etapa 6 de [`docs/processo.md`](../docs/processo.md)). Ela traz o modelo usado, a data de referência dos pedidos e, em cada resposta, as ferramentas que o agente chamou.

Os 5 cenários foram gravados numa única sessão, então o agente tinha na memória os anteriores ao responder os seguintes:

| Cenário | O que mostra |
|---|---|
| 1. Violões disponíveis até R$ 1.000 | Busca no catálogo com filtros combinados |
| 2. Devolução por arrependimento do pedido 4 | Caso não trivial: identidade, dados do pedido e política juntos, com prazos calculados |
| 3. Produto sem estoque | Alternativas semelhantes, como o manual pede |
| 4. Fora do escopo e prompt injection | Recusa com leveza e proteção dos dados de clientes |
| 5. Endereço e "estão abertos agora?" | Política e relógio real do fuso da loja |

Capturas da interface web estão no [README](../README.md#na-interface-web).
