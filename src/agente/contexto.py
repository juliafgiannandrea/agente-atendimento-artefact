"""Contexto de uma conversa: onde estão os bancos, qual a data de referência e
o estado que os guardrails das tools precisam lembrar entre chamadas.

Cada conversa (sessão do CLI) tem o seu Contexto. As tools são criadas a
partir dele (ver agente/tools/__init__.py), então não há estado global.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from agente.config import ROOT_DIR, STORE_TIMEZONE, get_db_path, get_reference_date

ATENDIMENTO_DB_PADRAO = ROOT_DIR / "data" / "atendimento.db"


@dataclass
class EstadoConversa:
    """Contadores usados pelos guardrails das tools."""
    falhas_verificacao: int = 0          # tentativas de identificação que não conferiram
    consultas_sql_no_turno: int = 0      # chamadas a consultar_banco na mensagem atual

    def novo_turno(self) -> None:
        self.consultas_sql_no_turno = 0


@dataclass
class Contexto:
    db_path: Path
    reference_date: date
    atendimento_db_path: Path = ATENDIMENTO_DB_PADRAO
    agora: Callable[[], datetime] = field(
        default=lambda: datetime.now(ZoneInfo(STORE_TIMEZONE)))
    estado: EstadoConversa = field(default_factory=EstadoConversa)

    @classmethod
    def padrao(cls) -> "Contexto":
        """Contexto lido do .env. Falha já ao iniciar se o banco não existir, em vez de
        só na primeira pergunta do cliente, com uma mensagem genérica."""
        ctx = cls(db_path=get_db_path(), reference_date=get_reference_date())
        ctx.exigir_banco()
        return ctx

    def exigir_banco(self) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Banco não encontrado em {self.db_path}. Rode `python -m etl.pipeline` primeiro.")

    @contextmanager
    def conexao_leitura(self) -> Iterator[sqlite3.Connection]:
        """Conexão somente leitura com o banco gerado pelo ETL, fechada ao final."""
        self.exigir_banco()
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
