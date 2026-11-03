# Base de conhecimento — Empório da Música

Índice da base de políticas usada pelo assistente virtual. O assistente **recebe primeiro a lista de seções** e só carrega a seção de que precisa para responder (divulgação progressiva), em vez de receber o manual inteiro em todo atendimento.

Fonte: *Manual de Políticas e Procedimentos — Atendimento ao Cliente*, versão 2.1 (junho de 2025), em `data/raw/políticas_da_loja.pdf`.

## Política ou sistema?

| A pergunta é sobre... | Onde buscar |
|---|---|
| Preço, estoque, disponibilidade, promoção **vigente**, parcelas de um produto | **Sistema** (catálogo) |
| Status, rastreio ou itens de um pedido | **Sistema** (pedidos), após verificar a identidade |
| Regras, prazos, condições, horários, contatos, como a loja funciona | **Esta base** (seções abaixo) |
| Exemplo: "posso devolver meu pedido?" | **Os dois**: a regra vem da base, as datas do pedido vêm do sistema |

Nunca responder sobre preço, estoque ou prazo de um pedido sem consultar o sistema (manual, seção 7.1).

## Seções

| id | Arquivo | Conteúdo | Quando consultar |
|---|---|---|---|
| `sobre-a-loja` | `politicas/01-sobre-a-loja.md` | História, o que vende e não vende, endereço, contatos, CNPJ | Endereço, telefone, WhatsApp, e-mail; se a loja vende acessórios |
| `horario-de-funcionamento` | `politicas/02-horario-de-funcionamento.md` | Horários da loja e do WhatsApp, datas especiais | Se está aberta, domingo e feriado, atendimento fora do expediente |
| `formas-de-pagamento` | `politicas/03-formas-de-pagamento.md` | PIX, débito, crédito, boleto, regras de parcelamento | Formas de pagamento, desconto no PIX, parcela mínima, combinar formas |
| `trocas-e-devolucoes` | `politicas/04-trocas-e-devolucoes.md` | Arrependimento, troca por defeito, troca por preferência, itens não elegíveis | Devolução, reembolso, troca, prazos |
| `frete-e-entregas` | `politicas/05-frete-e-entregas.md` | Frete na região metropolitana e em outras cidades, prazos, rastreio, avaria | Frete, prazo de entrega, rastreamento, produto danificado |
| `promocoes-e-descontos` | `politicas/06-promocoes-e-descontos.md` | Calendário de campanhas e regras de promoção | Regras de desconto, Black Friday, cumulatividade |
| `procedimentos-de-atendimento` | `politicas/07-procedimentos-de-atendimento.md` | **Interno.** Fluxo de atendimento e situações especiais | Produto sem estoque ou descontinuado, promoção vencida, reclamação |
| `garantia` | `politicas/08-garantia.md` | Garantia legal e do fabricante, o que não cobre | Defeito após o prazo de troca, cobertura da garantia |
| `privacidade-e-dados` | `politicas/09-privacidade-e-dados.md` | LGPD, uso e exclusão de dados | Privacidade, exclusão de dados, por que é pedida identificação |

## Outros arquivos

| Arquivo | Para quê | Carregado pelo assistente? |
|---|---|---|
| `soul.md` | Persona, tom de voz e princípios de atendimento (manual, seção 7.1) | Sim, sempre (prompt de sistema) |
| `pendencias_gerencia.md` | Contradições e lacunas do manual para a gerência resolver | Não: é para a equipe |
| `_fonte/manual_extraido.md` | Texto bruto extraído do PDF, para rastrear a origem de cada seção | Não |

## Governança

- Cada seção tem no cabeçalho a versão do manual, as páginas de origem e o campo `revisao_humana`. Uma seção só deve ir para produção com `revisao_humana: aprovada`.
- As seções têm dois tipos de bloco que não fazem parte do manual original:
  - `> **Orientação ao assistente:**` diz ao assistente como agir (ex.: não estimar frete, avisar que a data de entrega é estimada). **O assistente lê.**
  - `> **Nota de curadoria:**` registra a origem de decisões e lacunas para quem mantém a base (referências a `docs/decisoes.md`, alertas e pendências). **O assistente não lê**: `src/agente/kb.py` remove esses blocos antes de entregar o texto.
- O assistente não lê este índice diretamente: recebe uma lista gerada dos cabeçalhos das seções (`id`, `titulo` e `quando_consultar`), que nunca fica desatualizada.
- Quando o manual for atualizado: rodar `python -m etl.extrair_politicas`, comparar o diff de `_fonte/manual_extraido.md` e atualizar as seções afetadas. Os testes (`tests/test_kb.py`) conferem que os valores citados nas seções existem no manual.
