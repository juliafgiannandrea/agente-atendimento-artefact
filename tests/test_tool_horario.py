"""Tool hora_atual_loja (horário da seção 2 do manual)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from agente.tools.horario import situacao

TZ = ZoneInfo("America/Campo_Grande")


@pytest.mark.parametrize("agora, aberta, retorno", [
    (datetime(2026, 3, 25, 10, 30, tzinfo=TZ), True, None),                          # quarta
    (datetime(2026, 3, 25, 18, 0, tzinfo=TZ), False, "quinta-feira, 26/03 às 09:00"),  # fecha às 18h
    (datetime(2026, 3, 28, 12, 59, tzinfo=TZ), True, None),                          # sábado
    (datetime(2026, 3, 28, 13, 0, tzinfo=TZ), False, "segunda-feira, 30/03 às 09:00"),
    (datetime(2026, 3, 29, 10, 0, tzinfo=TZ), False, "segunda-feira, 30/03 às 09:00"),  # domingo
    (datetime(2026, 3, 30, 8, 0, tzinfo=TZ), False, "segunda-feira, 30/03 às 09:00"),
])
def test_situacao(agora, aberta, retorno):
    s = situacao(agora)
    assert s["loja_aberta_agora"] is aberta
    assert s.get("equipe_retorna_em") == retorno


def test_tool_informa_data_de_referencia(tools):
    r = tools["hora_atual_loja"]()
    assert r["dia_da_semana"] == "quarta-feira"
    assert r["data_de_referencia_para_pedidos"] == "25/03/2026"


def test_horario_coincide_com_a_base_de_politicas():
    from agente import kb
    texto = kb.ler_secao("horario-de-funcionamento")
    assert "| Segunda a sexta-feira | 09:00 às 18:00 |" in texto
    assert "| Sábado | 09:00 às 13:00 |" in texto
