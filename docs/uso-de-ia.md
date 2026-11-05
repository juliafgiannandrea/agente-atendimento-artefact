# Uso de assistentes de IA

O enunciado pede que eu explique quais assistentes de IA usei e como. Este arquivo registra isso etapa por etapa e alimenta a seção correspondente do README.

## Ferramenta

- **Claude (Anthropic):** uso o app do Claude conectado à pasta do projeto no meu computador. Com ele leio os materiais, discuto decisões e gero código e documentação.
- **Skills do Claude:** em cada etapa uso as skills que se aplicam ao tipo de tarefa (por exemplo, leitura de PDF, exploração e validação de dados, escrita de documentação).

## Meu workflow

1. **Entendimento próprio primeiro.** Antes de usar IA, li o enunciado e os requisitos e olhei a base de dados, para entender a estrutura e o que foi fornecido.
2. **Minhas anotações.** Registrei num arquivo de anotações o que eu achava que devia ser implementado e como queria fazer.
3. **Contexto para o Claude.** Conectei a pasta com todos os materiais (enunciado, dados, políticas e anotações) e pedi que ele entendesse o contexto antes de começarmos.
4. **Crítica do plano.** Com o retorno dele, identifiquei os pontos frágeis do meu plano e pedi um passo a passo de implementação, partindo da ordem que eu tinha pensado.
5. **Validação.** O Claude gerou o plano lógico; eu validei, ajustei e aprovei.
6. **Implementação em partes pequenas.** Seguimos o plano etapa por etapa. Cada parte é implementada, revisada por mim e commitada.

## Divisão de responsabilidades

- **Decisões são minhas.** O Claude levanta opções e trade-offs; a escolha é minha e fica registrada em `docs/decisoes.md`.
- **Documentação escrita pelo Claude, revisada por mim.** Toda a documentação (decisões, este arquivo, README) é redigida pelo Claude a partir das nossas discussões, e eu reviso antes de commitar.
- **Commits são meus.** O Claude cria e edita arquivos locais, mas não faz commit nem push. Cada commit marca uma etapa que revisei.

## Registro por etapa

### Etapa 0 — Entendimento e setup

- O Claude leu o enunciado, os CSVs, o manual de políticas e minhas anotações, e fez uma análise de qualidade dos dados: estoques zerados, status inconsistentes, totais de pedido divergentes, promoções duplicadas e contradições no manual.
- Discutimos o plano de ataque. Por sugestão dele, o conjunto de perguntas de teste foi para antes da construção do agente e as decisões passaram a ser registradas desde o início.
- Decidi provedor, banco, interface e Docker depois de pesar os trade-offs apresentados (ver `docs/decisoes.md`, D01 a D07).
- O Claude gerou o esqueleto do repositório, o `.env.example`, a função `build_model()` e estes documentos.

### Etapa 1 — Conjunto de perguntas de teste

- Defini as categorias que o conjunto precisava cobrir: as 4 perguntas do enunciado, estoque e status, promoções, parcelamento, verificação de identidade, acessórios, fora do escopo e prompt injection.
- O Claude escreveu os casos de `tests/eval_set/perguntas.yaml` (34 na primeira versão, 36 hoje), com as respostas esperadas calculadas a partir dos CSVs (preços, promoções ativas, parcelas e titulares dos pedidos), e apontou as suposições que alguns casos exigem (S01 a S05 em `docs/decisoes.md`).
- Decidi as suposições em aberto: data de referência simulada (S01), regra de parcelamento (S02) e contatos (S03).

### Etapa 2 — ETL

- Antes de implementar, debatemos boas práticas de ETL (camada raw imutável, medallion, idempotência, schema explícito, qualidade de dados como código, sinalizar em vez de corrigir, rastreabilidade) e como cada uma se aplicava a este projeto.
- Decidi: bronze dentro do banco, pandas + SQL + verificações em Python puro, nenhuma promoção vale quando há duas ativas (S06), dados de clientes no mesmo banco e testes com pytest (D09 a D12).
- O Claude implementou o pipeline, o schema, as verificações de qualidade, o gerador do relatório e 53 testes. Ao revisar o primeiro relatório, ajustamos a verificação A03, que marcava como inconsistência um item vendido que só esgotou depois (D14).

### Etapa 3 — Base de conhecimento

- Defini a estrutura: seções do manual em Markdown, índice para divulgação progressiva, persona (`soul.md`) a partir da seção 7.1 e uma nota de pendências para a gerência com as contradições do manual.
- O Claude escreveu o script de extração do PDF, curou as 9 seções, o índice, a persona e as pendências, e criou testes que conferem se cada valor citado nas seções existe no PDF. Além das três contradições que eu tinha levantado, ele apontou 10 lacunas do manual (L1 a L10) e sugeriu a decisão do e-mail (S07).
- Perguntei se o agente leria as notas de curadoria. Decidi separá-las em dois tipos: orientações ao assistente (o agente lê) e notas de curadoria (removidas pela tool).
- Pedi uma revisão de fidelidade das 9 seções contra o manual. A revisão comparou cada linha com o PDF e encontrou interpretações que tinham entrado no texto principal (por exemplo, "exceto compras abaixo de R$ 50,00", quando o manual diz só "exceto abaixo de R$ 50,00"). Elas voltaram ao texto original e foram para blocos de orientação ou de curadoria, identificadas como interpretação.

### Etapa 4 — Agente e tools

- Defini as tools de contrato fechado (catálogo, pedido, política, reclamação, horário) e a regra do SQL livre: só quando a pergunta não se encaixar nelas, primeiro lendo a documentação do esquema e depois executando a query, podendo repetir.
- O Claude propôs e implementou os guardrails em código: verificação de identidade com limite de tentativas, SQL somente leitura restrito ao catálogo (para não contornar a verificação de identidade), limites de linhas, tempo e consultas por mensagem. Também colocou os cálculos de preço, parcelas e prazos nas tools, para o modelo não fazer contas.
- Os testes usam um modelo roteirizado, que simula o modelo chamando ferramentas, para validar o loop do agente sem gastar API. Ao rodar os testes, um caso meu de expectativa estava errado (um violão de 7 cordas sem "nylon" no nome) e foi corrigido no teste, não no código.
- Testei o agente com modelos gratuitos do OpenRouter. O primeiro modelo foi recusado pelo provedor (só funciona em apps cadastrados) e o segundo deu limite de requisições, com o terminal parado por mais de um minuto. Com o Claude, analisei os erros e decidi: limitar as novas tentativas, classificar as falhas do provedor com mensagens claras, testar a conexão ao iniciar, esconder os logs internos fora do `--debug` e proibir Markdown nas respostas, que vinham com negrito.
- Perguntei se o agente fazia um planejamento antes de responder. Ele não fazia (loop ReAct puro). Avaliei as opções que o Claude levantou e escolhi uma tool `planejar`, usada só em perguntas com mais de uma fonte, com um campo de informações faltantes para o agente perguntar em vez de supor (D20).

### Etapa 5 — Interface

- Antes de implementar a UI em Streamlit, usei a skill de system design do Claude para documentar requisitos, arquitetura, trade-offs e as opções de renderização. Escolhi renderizar cartões a partir dos resultados das tools, e não a partir do texto do modelo.
- Gerei com o Claude um protótipo visual (tela do chat, cartões por tool e diagrama de arquitetura) para validar o desenho antes de escrever o código.
- Ajustei o protótipo: detalhes técnicos invisíveis, sem cartão de conexão e de exportação, perguntas de exemplo na sidebar, plano como checklist que se completa em tempo real e cores da identidade visual da Artefact. O Claude levantou as cores e a fonte direto do site da Artefact e ajustou o magenta para passar no contraste mínimo de acessibilidade.
- Aprovei o protótipo e o Claude implementou a UI em Streamlit: extração das chamadas de tools, hooks de progresso, cartões e página. Os testes usam o `AppTest` do Streamlit com o modelo roteirizado, sem API e sem navegador. Ele também rodou a UI com um modelo roteirizado e conferiu as telas por captura antes de entregar, o que revelou que a fonte da marca não estava sendo aplicada (corrigido).
- Testando a interface, encontrei problemas que levei ao Claude, e decidimos juntos como resolver:
  - **resposta anterior aparecendo duplicada** ao enviar uma nova mensagem: ele reproduziu o problema num servidor de demonstração com um modelo roteirizado lento, achou a causa (a estrutura da página mudava entre execuções) e confirmou a correção por captura de tela;
  - **valores em reais com a formatação quebrada:** ele identificou que o Streamlit lia o texto entre dois cifrões como fórmula e mostrou o antes e o depois;
  - **agente oferecendo ações e fazendo perguntas desnecessárias** ("quer que eu reserve?", "posso te avisar quando chegar"): a decisão de que o agente só responde foi minha (D22 e D23). O Claude conferiu no manual o que precisava continuar (alternativas para produto sem estoque e o fechamento) e me apresentou essa diferença para eu decidir;
  - **política interna visível ao cliente:** decidi retirar os textos das políticas da tela.

### Etapa 6 — Avaliação

- Fiz as conversas com o agente no CLI e na interface. O Claude sugeriu os cenários e as mensagens exatas, tiradas do conjunto de teste, para que as respostas pudessem ser conferidas contra os valores esperados.
- O Claude leu as conversas exportadas e as capturas e comparou cada resposta com o caso esperado e com o resultado das ferramentas. Ele separou o que funcionou dos desvios e, para cada desvio, apontou se a origem era o modelo ou a solução.
- Pedi que a documentação deixasse claro que parte dos erros vem do modelo usado. O Claude conferiu as características do modelo na página oficial (pesos abertos, *mixture-of-experts*, português fora das línguas suportadas) em vez de supor, e sugeriu manter separados os desvios que são da solução, para o argumento não soar como desculpa.
- O limite de 50 requisições por dia impediu a rodada completa das 36 perguntas e a comparação entre modelos. Isso ficou registrado como limitação e como o primeiro item do que eu faria com mais tempo.

### Etapa 7 — Fechamento

- Pedi uma documentação que explicasse o que foi feito em cada etapa, porque o PDF do README e da documentação faz parte da avaliação.
- O Claude reescreveu o README, criou os documentos de processo e de arquitetura (com diagramas), revisou o registro de decisões, montou o checklist do desafio e escreveu o script que gera o PDF. Revisei tudo antes de commitar.
- Ele também testou o projeto do zero numa cópia limpa, seguindo o README, para conferir se as instruções bastam para outra pessoa rodar.

## Onde a revisão humana fez diferença

O Claude acelerou muito o trabalho, mas a revisão não foi formalidade. Alguns exemplos:

- **Interpretação disfarçada de regra:** na primeira curadoria das políticas, interpretações entraram no texto como se fossem do manual. Pedi uma revisão linha a linha contra o PDF, e elas foram separadas e identificadas (etapa 3).
- **Falso positivo no relatório de qualidade:** ao ler o primeiro relatório, vimos que a verificação A03 marcava como problema uma venda normal (etapa 2).
- **Comportamento do agente:** os ajustes de tom (não oferecer ações, não fazer perguntas de refinamento, não mostrar políticas internas) vieram de eu usar o agente como cliente e não gostar do que vi (etapa 5).
- **Expectativa errada num teste:** quando um teste falhou, conferimos os dados antes de mexer no código. O erro estava no teste, e o código ficou como estava (etapa 4).

