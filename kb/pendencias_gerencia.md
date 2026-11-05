# Pendências para a gerência

Contradições e lacunas encontradas no *Manual de Políticas e Procedimentos*, versão 2.1 (junho de 2025), durante a montagem da base de conhecimento do assistente virtual.

Enquanto não houver resposta da gerência, o assistente segue a decisão provisória indicada em cada item (registradas em `docs/decisoes.md`). Este arquivo **não é carregado pelo assistente**.

## Contradições

| # | Assunto | O que o manual diz | Decisão provisória | Ref. |
|---|---|---|---|---|
| P1 | Número do WhatsApp | Capa e "Dados da Empresa" (seção 1.2): "Telefone / WhatsApp (67) 3341-4444". Seção 7: "O canal de WhatsApp (67) 3321-4500". | WhatsApp (67) 3321-4500 (seção específica do canal); (67) 3341-4444 como telefone fixo. | S03 |
| P2 | E-mail de contato | Capa: contato@emporiodamusica.com.br. "Dados da Empresa" (seção 1.2): contato@empóriodamusica.com.br, com acento. | contato@emporiodamusica.com.br, sem acento. Endereços de e-mail com acento no domínio raramente funcionam em todos os provedores, e a capa usa a grafia sem acento. | S07 |
| P3 | Parcela mínima no cartão de crédito | Tabela da seção 3: "Até 12x sem juros — Parcela mínima de R$ 100,00". Seção 3.1: até 3x sem mínimo; 4x a 6x com mínimo de R$ 80,00; 7x a 12x com mínimo de R$ 100,00. | Valem as faixas da seção 3.1 (regra mais específica e detalhada). | S02 |

## Lacunas e ambiguidades

| # | Assunto | Dúvida | Como o assistente age hoje |
|---|---|---|---|
| L1 | Parcelamento de compras pequenas | "Até 3x: sem valor mínimo de parcela (exceto abaixo de R$ 50,00)". O "abaixo de R$ 50,00" se refere à compra ou à parcela? | Interpreta como compra: abaixo de R$ 50,00, não parcela. |
| L2 | PIX em pagamento combinado | Na combinação PIX + cartão (acima de R$ 2.000,00), o desconto de 5% vale sobre a parte paga no PIX? | Não afirma; orienta o cliente a confirmar com a equipe. |
| L3 | Troca por preferência | "Em até 7 dias": contados da compra ou do recebimento? Vale para compras presenciais? | Informa a regra e orienta o cliente a falar com a equipe. |
| L4 | Arrependimento em compra presencial | A seção 4.1 vale só para compras online. Não há regra para quem compra na loja e se arrepende. | Informa que o direito de arrependimento é para compras online e orienta o cliente a falar com a equipe. |
| L5 | Região metropolitana | Quais cidades contam como "região metropolitana de Campo Grande" para o frete fixo/grátis? E pedidos de exatamente R$ 500,00? | Não confirma frete grátis ou taxa fixa fora de Campo Grande; orienta o cliente a pedir a cotação à equipe. |
| L6 | Lojas parceiras | "Sugerir lojas parceiras quando possível", mas não há lista de parceiros. | Redireciona o pedido de acessório sem citar lojas. |
| L7 | Catálogo x manual | O manual cita "mais de 300 instrumentos", incluindo sopro e cordas orquestrais; o sistema tem 65 produtos e nenhum dessas categorias. | Segue o sistema: informa que não há itens dessas categorias no momento. |
| L8 | Status "em breve" | O manual não trata produtos que ainda vão chegar (status `coming_soon` no sistema). | Informa que ainda não está à venda e sugere alternativas disponíveis. |
| L9 | Significado dos status de pedido | O manual não define o que significam "pendente" e "confirmado". | Usa rótulos neutros, sem prometer prazos. |
| L10 | Data de recebimento | Prazos de arrependimento e garantia contam do recebimento, mas o sistema só registra a previsão de entrega. | Usa a previsão e avisa o cliente de que é uma estimativa. |
