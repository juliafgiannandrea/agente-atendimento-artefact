"""Tool ler_politica: divulgação progressiva da base de conhecimento.

O agente recebe no prompt de sistema só o índice das seções (gerado dos
cabeçalhos) e carrega a seção de que precisa. Notas de curadoria são
removidas por agente.kb antes de chegar ao modelo.
"""

from __future__ import annotations

from strands import tool

from agente import kb
from agente.contexto import Contexto


def criar(ctx: Contexto) -> list:  # noqa: ARG001 (mesma assinatura das demais)

    @tool
    def ler_politica(secao: str) -> str:
        """Lê uma seção da base de políticas da loja (regras, prazos, condições, horários,
        contatos). Use o id da seção, conforme o índice de políticas do prompt de sistema
        (ex.: "trocas-e-devolucoes", "formas-de-pagamento", "frete-e-entregas").

        Args:
            secao: Id da seção a ler.
        """
        try:
            return kb.ler_secao(secao.strip())
        except KeyError as erro:
            return str(erro.args[0])

    return [ler_politica]
