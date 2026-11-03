"""Tool hora_atual_loja: data, hora e se a loja está aberta agora.

O modelo não sabe que horas são; sem esta tool, ele inventaria. Usa a hora
real no fuso de Campo Grande (manual, seção 2). Os prazos de pedidos usam a
data de referência simulada (S01), informada à parte.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from strands import tool

from agente import regras
from agente.contexto import Contexto


def _horario(dia: int) -> tuple[time, time] | None:
    faixa = regras.HORARIO_FUNCIONAMENTO[dia]
    if faixa is None:
        return None
    abre, fecha = (time.fromisoformat(h) for h in faixa)
    return abre, fecha


def proxima_abertura(agora: datetime) -> datetime:
    for dias in range(0, 8):
        dia = agora + timedelta(days=dias)
        faixa = _horario(dia.weekday())
        if faixa is None:
            continue
        abertura = dia.replace(hour=faixa[0].hour, minute=faixa[0].minute, second=0, microsecond=0)
        if abertura > agora:
            return abertura
    raise RuntimeError("Horário de funcionamento sem nenhum dia aberto.")


def situacao(agora: datetime) -> dict:
    faixa = _horario(agora.weekday())
    aberta = faixa is not None and faixa[0] <= agora.time() < faixa[1]
    resultado = {
        "agora": agora.strftime("%d/%m/%Y %H:%M"),
        "dia_da_semana": regras.DIAS_SEMANA[agora.weekday()],
        "loja_aberta_agora": aberta,
        "horario_de_hoje": (f"{faixa[0]:%H:%M} às {faixa[1]:%H:%M}" if faixa else "fechado"),
    }
    if not aberta:
        abertura = proxima_abertura(agora)
        resultado["equipe_retorna_em"] = (
            f"{regras.DIAS_SEMANA[abertura.weekday()]}, {abertura:%d/%m} às {abertura:%H:%M}")
    resultado["observacao"] = "Feriados não estão cadastrados; em feriados a loja fecha."
    return resultado


def criar(ctx: Contexto) -> list:

    @tool
    def hora_atual_loja() -> dict:
        """Informa data e hora atuais em Campo Grande (MS), se a loja está aberta agora
        e, se estiver fechada, quando a equipe volta a atender. Use para perguntas sobre
        "está aberto?" e para avisar o horário de retorno fora do expediente.
        """
        resultado = situacao(ctx.agora())
        resultado["data_de_referencia_para_pedidos"] = ctx.reference_date.strftime("%d/%m/%Y")
        return resultado

    return [hora_atual_loja]
