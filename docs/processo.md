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
| 6. Avaliação | Rodar as perguntas de teste, ajustar e repetir; gerar as conversas de exemplo | Em andamento |
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

**Como será feita:**

1. Rodar as 36 perguntas (inclusive as conversas de vários turnos) e salvar, para cada uma, a resposta, as ferramentas chamadas e o tempo.
2. Conferir automaticamente o que dá para conferir por regra: se a fonte usada é a esperada e se os fatos obrigatórios aparecem.
3. Revisar as falhas, ajustar prompt, ferramentas ou base de conhecimento e rodar de novo.
4. Gerar as conversas de exemplo a partir das melhores execuções.

**Restrição:** cada pergunta gasta de 3 a 5 chamadas ao modelo (uma por passo do agente). Uma rodada completa passa de 100 requisições, acima do limite diário de 50 dos modelos gratuitos do OpenRouter sem créditos. A avaliação vai usar a cota renovada ou a API da Anthropic.

**Resultados:** *(a preencher ao final da etapa 6)*

---

## Etapa 7 — Fechamento

**Objetivo:** deixar o projeto pronto para outra pessoa rodar e avaliar.

**O que foi feito:**

- README reescrito, com as instruções, as justificativas, as limitações, o que eu faria com mais tempo, o uso de IA e um checklist dos requisitos do desafio.
- Esta documentação de processo e a de [arquitetura](arquitetura.md), com diagramas.
- Revisão de consistência do registro de decisões: decisões que mudaram depois (como a interface, que começou só em CLI) ganharam uma nota de atualização, em vez de serem apagadas.
- Teste do zero numa cópia limpa do repositório: ambiente virtual novo, seguindo o README à risca. O ETL gerou um relatório idêntico ao versionado e os testes passaram. O teste revelou que, sem o banco, o CLI e a interface iniciavam normalmente e só falhavam na primeira pergunta, com uma mensagem genérica. Agora os dois avisam já ao iniciar que é preciso rodar o ETL.
- Geração deste PDF a partir do README e da documentação (`docs/gerar_pdf.py`).

---

## Etapa 8 — Deploy (planejada)

- Gerar o banco automaticamente na primeira inicialização da interface, já que o `.db` não é versionado.
- Publicar no Streamlit Community Cloud, com a chave do modelo nos *secrets* da plataforma.
- Documentar a limitação: no servidor, as reclamações registradas não persistem entre reinicializações.
