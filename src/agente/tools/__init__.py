"""Tools do agente. Cada módulo expõe `criar(ctx)`, que devolve as tools
ligadas ao contexto da conversa (bancos, data de referência e estado)."""

from __future__ import annotations

from agente.contexto import Contexto
from agente.tools import catalogo, horario, pedidos, politicas, reclamacoes, sql

MODULOS = [catalogo, pedidos, politicas, reclamacoes, horario, sql]


def criar_ferramentas(ctx: Contexto) -> list:
    ferramentas = []
    for modulo in MODULOS:
        ferramentas += modulo.criar(ctx)
    return ferramentas
