"""Tool registrar_reclamacao."""

import sqlite3


def test_registra_com_protocolo(tools, ctx):
    r = tools["registrar_reclamacao"]("João Silva", "(67) 99111-1234", "Violão chegou com o tampo rachado", 12)
    assert r == {"registrada": True, "protocolo": "REC-20260325-0001", "prazo_de_retorno": "24 horas úteis",
                 "mensagem": "Informe o protocolo e o prazo de retorno ao cliente."}
    with sqlite3.connect(ctx.atendimento_db_path) as conn:
        assert conn.execute("SELECT nome, pedido_id, status FROM reclamacoes").fetchone() == (
            "João Silva", 12, "aberta")


def test_protocolos_sequenciais(tools):
    tools["registrar_reclamacao"]("A B", "1", "x")
    assert tools["registrar_reclamacao"]("C D", "2", "y")["protocolo"] == "REC-20260325-0002"


def test_exige_dados_minimos(tools):
    assert tools["registrar_reclamacao"]("", "", "algo")["registrada"] is False
