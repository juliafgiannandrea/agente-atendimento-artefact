# Processo: o que foi feito em cada etapa

Este documento conta como o projeto foi construído, na ordem em que aconteceu: o objetivo de cada etapa, o que foi feito, as decisões tomadas, os problemas encontrados e como foram resolvidos. As decisões estão detalhadas em [`decisoes.md`](decisoes.md) e o uso de assistentes de IA em [`uso-de-ia.md`](uso-de-ia.md).

## Plano

Antes de escrever código, montei um plano em etapas, cada uma com uma entrega que pudesse ser revisada sozinha:

| Etapa | Entrega | Status |
|---|---|---|
| 0. Entendimento e setup | Leitura dos materiais, análise inicial dos dados, decisões de stack, esqueleto do repositório | Concluída |
| 1. Conjunto de perguntas de teste | 36 perguntas com fonte esperada, fatos obrigatórios e o que invalida a resposta | Concluída |
| 2. ETL | Banco SQLite em camadas, verificações de qualidade e relatório | Concluída |
| 3. Base de conhecimento | Manual em seções revisadas, persona, índice e pendências para a gerência | Concluída |
| 4. Agente e ferramentas | Agente Strands com 9 ferramentas, guardrails e CLI | Concluída |
| 5. Interface | Interface web em Streamlit, com cartões e plano em tempo real | Concluída |
| 6. Avaliação | Conversas reais com o agente no CLI e na interface, conferidas contra as respostas esperadas; conversa de exemplo e capturas | Concluída |
| 7. Fechamento | README, documentação, checklist do desafio, teste num clone limpo e este PDF | Concluída |
| 8. Deploy | Publicação no Streamlit Community Cloud | Planejada |

A ordem tem dois motivos. As perguntas de teste vieram **antes** do agente para guiar o desenho das ferramentas e da base de conhecimento e expor cedo as suposições a decidir. Os dados e as políticas vieram antes do agente porque ele só é tão bom quanto as fontes que consulta.

Cada etapa foi desenvolvida numa branch própria (como `feat/etl`, `feat/kb`, `feat/agente` e `feat/ui`) e integrada à `main` por pull request com merge commit, para preservar no histórico os commits de cada etapa.

---

## Etapa 0 — Entendimento e setup

**Objetivo:** entender o problema e os materiais antes de decidir qualquer coisa.

**O que foi feito:**

- Li o enunciado, os 6 CSVs e o manual de políticas, e registrei nas minhas anotações o que achava que precisava ser construído.
- A análise inicial dos dados encontrou problemas que o agente não pode esconder nem repassar sem critério:
  - um produto ativo sem estoque;
  - produtos "em breve" com estoque positivo;
  - pedidos com total diferente da soma dos itens;
  - produtos com mais de uma promoção cadastrada;
  - categorias do manual sem nenhum produto (sopro e cordas orquestrais).
- No manual, três contradições: dois números de WhatsApp, duas grafias de e-mail e duas regras de parcela mínima.

**Decisões (D01 a D07):** Strands Agents como framework; provedor e modelo configuráveis no `.env` (Anthropic ou OpenRouter); SQLite; CLI como primeira interface; sem Docker; `pip` + `requirements.txt`; extração do PDF sem OCR, porque o texto é nativo.

**Resultado:** esqueleto do repositório, `.env.example`, a função `build_model()` que isola o provedor e os primeiros registros de decisão.

---

## Etapa 1 — Conjunto de perguntas de teste

**Objetivo:** definir, antes de construir, o que o agente precisa responder, de qual fonte e o que ele nunca pode fazer.

**O que foi feito:** `tests/eval_set/perguntas.yaml` com 36 casos em 16 categorias: as 4 perguntas do enunciado, catálogo, estoque, promoções, parcelamento, pedidos e identidade, acessórios, fora do escopo, prompt injection, pedidos de ação, frete e reclamação. Cada caso tem as mensagens do cliente, a fonte esperada (dados, política, os dois ou nenhuma), os fatos que a resposta precisa conter (valores conferidos contra os CSVs) e o que invalida a resposta.

**Decisões:** escrever o conjunto montou a lista de suposições a decidir, porque vários casos não tinham resposta única:

- **S01, data de referência simulada (25/03/2026).** Com a data real, todos os pedidos estariam meses atrasados e fora de qualquer prazo de devolução, e os casos que testam o raciocínio de prazo deixariam de existir.
- **S02, parcelamento.** Valem as faixas da seção 3.1 do manual, a regra mais específica.
- **S03, contatos.** WhatsApp (67) 3321-4500 (seção do canal) e telefone (67) 3341-4444.
- **S04, status prevalece sobre estoque.** Produto "em breve" ou descontinuado não é vendido, mesmo com estoque.
- **S05, verificação de identidade.** Pedido só depois de confirmar nome completo e telefone ou e-mail.

---

## Etapa 2 — ETL

**Objetivo:** transformar os CSVs numa fonte confiável, sem perder a rastreabilidade do que foi tratado.

**O que foi feito:**

- Antes de implementar, debati boas práticas de ETL (camada bruta imutável, arquitetura medallion, idempotência, schema explícito, qualidade de dados como código, sinalizar em vez de corrigir, rastreabilidade) e como cada uma se aplicava aqui.
- O pipeline (`python -m etl.pipeline`) carrega as camadas bronze, silver e gold, executa 6 verificações de erro e 15 de alerta e gera o relatório [`data_quality.md`](data_quality.md).
- As regras de negócio ficaram num único módulo (`regras.py`), usado pelo ETL e pelas ferramentas, com valores monetários em `Decimal`.

**Decisões:** D09 a D14 e **S06** (com duas promoções ativas no mesmo produto, nenhuma vale e o ETL gera um alerta, porque escolher uma seria uma decisão comercial tomada pelo sistema).

**Problema e solução:** o primeiro relatório marcou como inconsistência um item vendido que só saiu de linha depois. Ajustei a verificação A03 para considerar apenas o status do produto, não o estoque (D14).

**Resultado:** nenhuma verificação de erro falhou. 8 dos 15 alertas têm ocorrências, por exemplo:

- dois pedidos com total diferente da soma dos itens;
- três pedidos com parcela abaixo do mínimo da seção 3.1;
- o Giannini GF-3D ativo e sem estoque;
- o pedido 8 com 25 dias de atraso na data de referência;
- clientes com nomes contidos um no outro, o que reforça a exigência de telefone ou e-mail na verificação.

---

## Etapa 3 — Base de conhecimento

**Objetivo:** levar o manual para um formato que o agente consulte com precisão e que um humano consiga auditar.

**O que foi feito:**

- Script de extração do PDF (`etl/extrair_politicas.py`) e curadoria das 9 seções em `kb/politicas/`, cada uma com cabeçalho de governança (páginas de origem, público, quando consultar, status de revisão humana).
- Persona em `kb/soul.md`, a partir das diretrizes de tom do manual (seção 7.1).
- Pendências para a gerência (`kb/pendencias_gerencia.md`): 3 contradições e 10 lacunas, cada uma com a decisão provisória que o agente segue.
- Testes de fidelidade: todo valor citado nas seções (preço, prazo, telefone, CEP, lei, e-mail) precisa existir no PDF.

**Decisões:** D15 (divulgação progressiva em vez de RAG vetorial) e S07 (e-mail sem acento). Separei as notas em dois tipos: **orientações ao assistente**, que o agente lê, e **notas de curadoria**, que registram decisões para humanos e são removidas antes de chegar ao agente.

**Problema e solução:** pedi uma revisão linha a linha das 9 seções contra o PDF. Ela encontrou interpretações que tinham entrado no texto principal: por exemplo, "exceto **compras** abaixo de R$ 50,00", quando o manual diz só "exceto abaixo de R$ 50,00". Esses trechos voltaram ao texto original, e a interpretação foi para um bloco separado e identificada como tal (lacuna L1).

**Resultado:** revisei e aprovei as 9 seções.

---

## Etapa 4 — Agente e ferramentas

**Objetivo:** um agente que saiba quando consultar dados e quando consultar políticas, sem inventar e sem expor dados de clientes.

**O que foi feito:**

- Ferramentas de contrato fechado para as perguntas recorrentes (catálogo, produto, pedido, política, horário, reclamação), cada uma com um commit próprio.
- SQL livre como **último recurso**, em duas etapas: primeiro ler a documentação do esquema, depois executar a consulta, podendo refazê-la.
- Guardrails em código: verificação de identidade com limite de tentativas, SQL somente leitura restrito ao catálogo, limites de linhas, tempo e consultas por mensagem, limite de tamanho da mensagem.
- Cálculos de preço, PIX, parcelas e prazos dentro das ferramentas, para o modelo só repetir valores prontos.
- Memória da conversa com janela deslizante e sessões opcionais em disco no CLI.
- Testes do loop do agente com um modelo roteirizado, sem gastar API.

**Decisões:** D16 a D20.

**Problemas e soluções:**

- **Modelos gratuitos do OpenRouter instáveis.** O primeiro modelo foi recusado pelo provedor (só aceita apps cadastrados) e o segundo bateu no limite de requisições, deixando o terminal parado por mais de um minuto. A partir disso:
  - as novas tentativas foram limitadas a 3, com esperas curtas;
  - as falhas passaram a ser classificadas pelo código HTTP, com mensagens claras;
  - o CLI passou a testar a conexão ao iniciar;
  - os logs internos ficaram escondidos fora do `--debug`.
- **Markdown no terminal.** As respostas vinham com `**negrito**`. O formato passou a ser definido por canal no prompt: texto puro no CLI, Markdown leve na web.
- **Agente afirmando o que o cliente não disse.** Num teste de reclamação, ele disse "você já aceitou a entrega". Perguntei se o agente planejava antes de responder; ele não planejava (ReAct puro). Entre as opções, escolhi uma ferramenta `planejar` com um campo de informações faltantes, usada só em perguntas com várias fontes, e uma regra no prompt contra afirmar fatos não informados (D20).

---

## Etapa 5 — Interface

**Objetivo:** mostrar respostas "renderizadas", sem perder a confiabilidade dos dados.

**O que foi feito:**

- **Design antes do código.** Documentei requisitos, arquitetura e opções de renderização e escolhi montar **cartões a partir do resultado das ferramentas**, não do texto do modelo. Assim o modelo não tem como inventar um cartão.
- **Protótipo visual.** Validei a tela do chat, os cartões de cada ferramenta e o diagrama de arquitetura antes de implementar. Nos ajustes:
  - detalhes técnicos ficaram invisíveis;
  - perguntas de exemplo foram para a barra lateral;
  - o plano virou um checklist que se completa em tempo real;
  - as cores seguiram a identidade visual da Artefact, com o magenta ajustado para passar no contraste mínimo de acessibilidade.
- **Implementação em Streamlit,** reaproveitando o mesmo agente do CLI. O progresso em tempo real usa os hooks do Strands, que avisam quando cada ferramenta começa e termina.

**Decisões:** D21 a D23.

**Problemas e soluções:**

- **Fonte da marca não aplicada.** A conferência por captura de tela mostrou que o Streamlit mantinha a fonte padrão. Corrigi com um seletor de CSS mais específico.
- **Cartões depois do texto.** Inverti a ordem para plano, cartões e texto, que comenta os dados.
- **Restos da resposta anterior.** Ao enviar uma segunda mensagem, a resposta anterior aparecia duplicada enquanto o agente respondia. A causa: o Streamlit reaproveita os elementos da tela pela posição, e a estrutura da página mudava entre uma execução e a seguinte. Fixei a estrutura (a saudação sempre presente e o mesmo contêiner para a resposta ao vivo e para a redesenhada a partir do histórico).
- **Valores em reais quebrando a formatação.** O Streamlit lê o texto entre dois `$` como fórmula matemática, então "R$ 2.089,05 ... R$ 183,25" virava uma fórmula. O cifrão passou a ser escapado antes de exibir.
- **Política interna visível ao cliente.** A interface mostrava o texto da política consultada. Como o manual é material interno da loja, os textos das políticas saíram da tela (D23).
- **Agente oferecendo ações.** Ele fechou uma resposta com "Quer que eu reserve?". Decidi que o agente responde e não executa ações. A exceção é registrar reclamação, que o manual exige (D22).
- **Perguntas de refinamento e promessas.** Sobre saxofone, o agente perguntou o modelo e a faixa de preço e ofereceu avisar quando chegasse algo. Ajustei a persona e o prompt: o agente responde o que foi perguntado e pergunta só o que falta para responder. Mantive as alternativas para produto sem estoque e o fechamento curto, porque o manual pede (D23).

**Resultado:** 215 testes automatizados, incluindo a página web testada com o `AppTest` do Streamlit.

---

## Etapa 6 — Avaliação

**Objetivo:** medir a qualidade das respostas com o conjunto de perguntas de teste, ajustar e repetir.

**Plano inicial:** rodar as 36 perguntas, conferir por regra a fonte usada e os fatos obrigatórios, corrigir e repetir.

**Restrição que mudou o plano:** cada pergunta gasta de 3 a 5 chamadas ao modelo, uma por passo do agente. Uma rodada completa passaria de 100 requisições, acima do limite de 50 por dia dos modelos gratuitos do OpenRouter. Em vez da rodada automatizada, a avaliação foi feita com uma amostra que cabia no limite.

**Como foi feita:**

1. **Conversas no CLI:** 5 cenários, escolhidos para cobrir os tipos de pergunta do enunciado. As mensagens foram digitadas exatamente como no conjunto de teste, para comparar as respostas com os valores esperados. Os 5 ficaram numa única sessão, exportada em [`exemplos/conversa.md`](../exemplos/conversa.md).
2. **Conversas na interface web:** 2 perguntas para mostrar os cartões, um pedido atrasado com reclamação e um produto em promoção. As capturas estão no README.
3. **Conferência:** cada resposta foi comparada com o caso correspondente em `tests/eval_set/perguntas.yaml` (fatos obrigatórios e o que invalida a resposta) e com o que as ferramentas devolveram.

Modelo usado: `nvidia/nemotron-3.5-lightning:free`, no OpenRouter. É um modelo de pesos abertos da NVIDIA, do tipo *mixture-of-experts* (30 bilhões de parâmetros, 3 bilhões ativos por token). O português não está entre as línguas que ele suporta oficialmente.

**O que funcionou:**

| Cenário | Resultado |
|---|---|
| Violões até R$ 1.000 | As 12 opções certas, sem o produto sem estoque nem o descontinuado |
| Devolução do pedido 4 | Pediu nome e telefone antes de consultar; com a identidade confirmada, aplicou a regra dos 7 dias com as datas calculadas pela ferramenta e indicou os canais da equipe |
| Produto sem estoque | Informou a indisponibilidade, o preço e o PIX certos e as 3 alternativas que a ferramenta trouxe |
| Fora do escopo e prompt injection | Recusou o restaurante com leveza; recusou listar clientes sem chamar nenhuma ferramenta |
| Endereço e horário | Endereço completo; pelo relógio real do fuso da loja, informou que estava fechada e quando reabre |
| Pedido atrasado com reclamação (web) | Verificou a identidade, reconheceu os 25 dias de atraso e registrou a reclamação com protocolo |
| Produto em promoção (web) | Preço com 18% de desconto, PIX sem desconto adicional e 12 parcelas, como a ferramenta calculou |

Os valores (preços, PIX, parcelas, prazos e atraso) saíram certos em todos os cenários, porque vêm calculados das ferramentas. Os guardrails de identidade e de privacidade também se comportaram como esperado.

**Desvios encontrados:**

| Desvio | Exemplo | Origem |
|---|---|---|
| Ignorar avisos das ferramentas | Tratou a previsão de entrega como data de entrega ("foi entregue em 22/12/2025"), apesar do aviso explícito no resultado da ferramenta | Modelo |
| Não usar o planejamento | Não chamou `planejar` nem na pergunta da reclamação, que junta pedido, política e registro; por isso o checklist não apareceu na interface | Modelo |
| Oferecer ações e ajuda extra | "Se quiser fechar a compra, é só me dizer qual forma de pagamento prefere"; "ou quer ver opções acima de R$ 1.000?" | Modelo: o prompt proíbe explicitamente (D22, D23) |
| Repetir os dados do cartão | Na interface, o texto repetiu quase tudo que o cartão do produto já mostrava | Modelo: o prompt pede para destacar só o que responde à pergunta |
| Erros de português | Palavra inexistente ("boawill"), concordância ("cordo de aço"), "Ele foi enviado em 15/02" para a data do pedido | Modelo |
| Faltou a garantia do fabricante | Na devolução, não citou a garantia do fabricante como alternativa, que é a resposta esperada para esse caso | Modelo e solução: a informação está na política de garantia, que o agente não consultou, e a ferramenta do pedido poderia indicá-la |
| Especificações mal traduzidas | "Pescoço Nato" (é braço) | Solução: a ferramenta entrega as chaves das especificações em inglês |

**Conclusões:**

- **O que está em código funcionou.** Valores, prazos, verificação de identidade, recusa a listar clientes e cartões da interface saíram certos com um modelo pequeno e gratuito. Era esse o objetivo de não depender do modelo para o que é crítico.
- **O que depende do modelo oscilou.** A redação, o tom e o cumprimento de regras do prompt variaram. Esses desvios devem diminuir com um modelo maior ou com melhor suporte ao português, mas não foi possível medir isso dentro do limite de requisições gratuitas (ver "Com mais tempo, eu faria", no README).

**Próximos passos identificados:**

1. Traduzir as chaves das especificações na ferramenta de produto, uma correção no código com resultado sempre igual.
2. Fazer a consulta do pedido indicar a garantia do fabricante quando a garantia legal já venceu.
3. Acrescentar ao prompt exemplos explícitos de fechamentos proibidos.
4. Rodar o conjunto completo de 36 perguntas com mais de um modelo, incluindo o Claude, e comparar os resultados.

---

## Etapa 7 — Fechamento

**Objetivo:** deixar o projeto pronto para outra pessoa rodar e avaliar.

**O que foi feito:**

- README reescrito, com as instruções, as justificativas, as limitações, o que eu faria com mais tempo, o uso de IA e um checklist dos requisitos do desafio.
- Esta documentação de processo e a de [arquitetura](arquitetura.md), com diagramas.
- Revisão de consistência do registro de decisões: decisões que mudaram depois (como a interface, que começou só em CLI) ganharam uma nota de atualização, em vez de serem apagadas.
- Teste do zero numa cópia limpa do repositório: ambiente virtual novo, seguindo o README à risca. O ETL gerou um relatório idêntico ao versionado e os testes passaram. O teste revelou que, sem o banco, o CLI e a interface iniciavam normalmente e só falhavam na primeira pergunta, com uma mensagem genérica. Agora os dois avisam já ao iniciar que é preciso rodar o ETL.
- Geração de dois PDFs a partir dos `.md` (`docs/gerar_pdf.py`): o do README, que é o arquivo de envio, e este, com a documentação completa.

---

## Etapa 8 — Deploy (planejada)

- Gerar o banco automaticamente na primeira inicialização da interface, já que o `.db` não é versionado.
- Publicar no Streamlit Community Cloud, com a chave do modelo nos *secrets* da plataforma.
- Documentar a limitação: no servidor, as reclamações registradas não persistem entre reinicializações.
