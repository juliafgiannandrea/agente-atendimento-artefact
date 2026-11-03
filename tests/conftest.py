"""Fixtures compartilhadas pelos testes."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from etl import pipeline

REFERENCE_DATE = date(2026, 3, 25)


@pytest.fixture(scope="session")
def etl_result(tmp_path_factory):
    """Roda o ETL uma vez num diretório temporário (não toca em data/ nem docs/)."""
    pasta = tmp_path_factory.mktemp("etl")
    return pipeline.build(
        db_path=pasta / "emporio.db",
        reference_date=REFERENCE_DATE,
        report_path=pasta / "data_quality.md",
    )


@pytest.fixture()
def db(etl_result):
    conn = sqlite3.connect(etl_result.db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture()
def ctx(etl_result, tmp_path):
    """Contexto de uma conversa nova, apontando para o banco de teste."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from agente.contexto import Contexto

    return Contexto(
        db_path=etl_result.db_path,
        reference_date=REFERENCE_DATE,
        atendimento_db_path=tmp_path / "atendimento.db",
        agora=lambda: datetime(2026, 3, 25, 10, 30, tzinfo=ZoneInfo("America/Campo_Grande")),
    )


@pytest.fixture()
def tools(ctx):
    """Tools da conversa, por nome."""
    from agente.tools import criar_ferramentas

    return {f.tool_name: f for f in criar_ferramentas(ctx)}
