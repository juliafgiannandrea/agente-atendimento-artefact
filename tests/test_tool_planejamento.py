"""Tool planejar."""

from agente.prompt import montar_prompt
from agente.tools.planejamento import MAX_PASSOS


def test_registra_plano_e_pede_o_que_falta(tools):
    r = tools["planejar"](
        "Verificar se o pedido pode ser devolvido",
        ["consultar o pedido", "ler a política de trocas"],
        ["número do pedido", "  ", "se a compra foi online"])
    assert r["registrado"] is True
    assert r["informacoes_faltantes"] == ["número do pedido", "se a compra foi online"]
    assert "pergunte ao cliente" in r["orientacao"]


def test_sem_faltantes_segue_os_passos(tools):
    r = tools["planejar"]("Informar preço", ["consultar o produto"])
    assert r["informacoes_faltantes"] == [] and "Siga os passos" in r["orientacao"]


def test_limita_numero_de_passos(tools):
    r = tools["planejar"]("x", [f"passo {i}" for i in range(10)])
    assert len(r["passos"]) == MAX_PASSOS


def test_prompt_orienta_quando_planejar(ctx):
    prompt = montar_prompt(ctx)
    assert "chame `planejar` antes" in prompt
    assert "Nunca afirme fatos sobre o cliente" in prompt
