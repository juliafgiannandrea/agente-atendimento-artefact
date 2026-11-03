"""Tool planejar: torna explícito o plano do agente antes de agir.

Não consulta nada: só registra o plano e o devolve. O valor está em (1)
obrigar o modelo a listar o que ainda não sabe, para perguntar ao cliente em
vez de supor, e (2) deixar o raciocínio visível no debug, na conversa
exportada e na UI (primeiro cartão da resposta). Ver docs/decisoes.md, D20.
"""

from __future__ import annotations

from strands import tool

from agente.contexto import Contexto

MAX_PASSOS = 6


def criar(ctx: Contexto) -> list:  # noqa: ARG001 (mesma assinatura das demais)

    @tool
    def planejar(objetivo: str, passos: list[str], informacoes_faltantes: list[str] | None = None) -> dict:
        """Registra o plano de atendimento ANTES de chamar outras ferramentas, quando a
        pergunta exige mais de uma fonte (ex.: dados de um pedido + uma política) ou
        várias etapas. Não use para perguntas simples de uma fonte só.

        Args:
            objetivo: O que o cliente quer, em uma frase.
            passos: Etapas na ordem, citando a fonte de cada uma (ex.: "consultar o pedido",
                "ler a política de trocas"). No máximo 6.
            informacoes_faltantes: O que o cliente ainda precisa informar e você não deve supor
                (ex.: "número do pedido", "se a compra foi online").
        """
        faltantes = [i.strip() for i in (informacoes_faltantes or []) if i.strip()]
        return {
            "registrado": True,
            "objetivo": objetivo.strip(),
            "passos": [p.strip() for p in passos if p.strip()][:MAX_PASSOS],
            "informacoes_faltantes": faltantes,
            "orientacao": (
                "Antes de seguir, pergunte ao cliente o que falta. Não suponha essas informações."
                if faltantes else "Siga os passos e responda com base no que as ferramentas retornarem."
            ),
        }

    return [planejar]
