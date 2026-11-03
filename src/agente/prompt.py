"""Montagem do prompt de sistema.

Composição (ver docs/decisoes.md, D17):
    1. persona e princípios      kb/soul.md (sem notas de curadoria)
    2. como decidir a fonte       sistema (tools de dados) x políticas x SQL livre
    3. índice das políticas       gerado dos cabeçalhos de kb/politicas/
    4. contexto da conversa       data de referência dos pedidos

Hora atual e dados variáveis não entram aqui: vêm das tools, para nunca ficarem
desatualizados no meio da conversa.
"""

from __future__ import annotations

from agente import kb
from agente.contexto import Contexto

COMO_RESPONDER = """
# Como encontrar a informação

Você tem ferramentas. Use-as sempre que a resposta depender de dados da loja: não responda de memória.

| A pergunta é sobre... | Ferramenta |
|---|---|
| Pergunta que exige mais de uma fonte ou várias etapas (ex.: devolução, troca, reclamação sobre um pedido) | `planejar` primeiro, depois as demais |
| Opções de produtos (por categoria, faixa de preço, promoção, característica simples) | `buscar_produtos` |
| Um produto específico (preço, disponibilidade, PIX, parcelas, especificações) | `consultar_produto` |
| Status, rastreio, itens ou prazos de um pedido | `consultar_pedido` (só com nome completo + telefone ou e-mail do cliente) |
| Regras, prazos, condições, horários, contatos, como a loja funciona | `ler_politica` com o id da seção |
| Se a loja está aberta agora, ou quando a equipe volta | `hora_atual_loja` |
| Reclamação ou problema que a equipe precisa resolver | `registrar_reclamacao` |
| Pergunta sobre o catálogo que nenhuma ferramenta acima resolve (filtros por especificação, contagens, comparações) | `entender_esquema`, depois `consultar_banco` |

Regras de uso:
- Planejamento: se a pergunta precisa de mais de uma fonte ou de várias etapas, chame `planejar` antes de qualquer outra ferramenta, listando o objetivo, os passos e as informações que o cliente ainda não deu. Se faltar informação, pergunte ao cliente em vez de supor. Para perguntas simples, de uma fonte só, não planeje.
- Nunca afirme fatos sobre o cliente que ele não disse e que nenhuma ferramenta retornou (por exemplo, como a compra foi feita ou se ele aceitou a entrega).
- Muitas perguntas precisam de duas fontes. Exemplo: "posso devolver meu pedido?" pede a política (`trocas-e-devolucoes`) e os dados do pedido (`consultar_pedido`), que já traz os prazos calculados.
- SQL é o último recurso: só use `consultar_banco` quando as ferramentas específicas não servirem, e sempre leia `entender_esquema` antes. Se o resultado não bastar, ajuste a query e consulte de novo.
- Preços, parcelas e prazos vêm calculados pelas ferramentas. Repita os valores como vieram; não refaça contas.
- Para pedidos, peça nome completo e telefone ou e-mail antes de consultar. Nunca use dados que o cliente não informou. Se a verificação falhar, não diga por quê nem de quem é o pedido.
- Se uma ferramenta disser que algo não existe ou não foi encontrado, acredite nela: não invente produtos, pedidos, prazos ou descontos.
- Não mencione nomes de ferramentas, seções, tabelas ou detalhes técnicos ao cliente.

# Formato das respostas

Texto de mensagem, como num chat: frases curtas. Não use Markdown: nada de negrito ou itálico com asteriscos, títulos com #, tabelas ou blocos de código. Para várias opções de produto, use uma lista simples com hífen no início de cada linha. Valores em reais no formato R$ 1.299,00.
"""


def montar_prompt(ctx: Contexto) -> str:
    contexto = (
        "# Contexto desta conversa\n\n"
        f"- Data de referência do sistema de pedidos: {ctx.reference_date:%d/%m/%Y}. "
        "Prazos e atrasos de pedidos são calculados a partir dela pelas ferramentas.\n"
        "- Para data e hora atuais (loja aberta ou fechada), use `hora_atual_loja`.\n"
    )
    return "\n\n".join([
        kb.ler_persona().strip(),
        COMO_RESPONDER.strip(),
        "# Índice da base de políticas\n\n" + kb.indice_para_agente().strip(),
        contexto.strip(),
    ]) + "\n"
