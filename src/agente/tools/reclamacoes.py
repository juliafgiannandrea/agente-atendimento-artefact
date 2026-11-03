"""Tool registrar_reclamacao (manual 7.3: registrar e encaminhar ao responsável).

As reclamações ficam em data/atendimento.db, separado do banco do ETL: o banco
do ETL é reconstruído a cada execução e perderia os registros.
"""

from __future__ import annotations

import sqlite3

from strands import tool

from agente.contexto import Contexto

PRAZO_RETORNO = "24 horas úteis"   # manual 7.3

DDL = """
CREATE TABLE IF NOT EXISTS reclamacoes (
    reclamacao_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    protocolo      TEXT UNIQUE,
    registrada_em  TEXT NOT NULL,
    nome           TEXT NOT NULL,
    contato        TEXT NOT NULL,
    pedido_id      INTEGER,
    descricao      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'aberta'
)
"""


def criar(ctx: Contexto) -> list:

    @tool
    def registrar_reclamacao(nome: str, contato: str, descricao: str, pedido_id: int | None = None) -> dict:
        """Registra uma reclamação do cliente e a encaminha à equipe responsável.
        Use quando o cliente relatar um problema (produto com defeito ou avariado,
        atraso, atendimento ruim). Antes, ouça com empatia e confirme os dados de contato.

        Args:
            nome: Nome do cliente.
            contato: Telefone ou e-mail para a equipe retornar.
            descricao: Resumo objetivo do problema, nas palavras do cliente.
            pedido_id: Número do pedido relacionado, se houver.
        """
        if not (nome.strip() and contato.strip() and descricao.strip()):
            return {"registrada": False,
                    "mensagem": "Faltam dados: peça nome, contato e a descrição do problema."}

        agora = ctx.agora()
        ctx.atendimento_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(ctx.atendimento_db_path) as conn:
            conn.execute(DDL)
            cursor = conn.execute(
                "INSERT INTO reclamacoes (registrada_em, nome, contato, pedido_id, descricao) "
                "VALUES (?, ?, ?, ?, ?)",
                (agora.isoformat(timespec="seconds"), nome.strip(), contato.strip(),
                 pedido_id, descricao.strip()[:2000]))
            protocolo = f"REC-{agora:%Y%m%d}-{cursor.lastrowid:04d}"
            conn.execute("UPDATE reclamacoes SET protocolo = ? WHERE reclamacao_id = ?",
                         (protocolo, cursor.lastrowid))

        return {
            "registrada": True,
            "protocolo": protocolo,
            "prazo_de_retorno": PRAZO_RETORNO,
            "mensagem": "Informe o protocolo e o prazo de retorno ao cliente.",
        }

    return [registrar_reclamacao]
