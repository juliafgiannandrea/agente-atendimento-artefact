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
- O Claude escreveu 34 casos em `tests/eval_set/perguntas.yaml`, com as respostas esperadas calculadas a partir dos CSVs (preços, promoções ativas, parcelas e titulares dos pedidos), e apontou as suposições que alguns casos exigem (S01 a S05 em `docs/decisoes.md`).
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
