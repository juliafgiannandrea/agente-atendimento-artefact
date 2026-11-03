"""UI: cartões montados a partir das tools e a página Streamlit (sem API, sem navegador)."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from agente.agente import Atendente, ChamadaTool, extrair_chamadas
from agente.config import ROOT_DIR
from agente.ui import componentes as c

from .modelo_roteirizado import ModeloRoteirizado

APP = str(ROOT_DIR / "src" / "agente" / "ui" / "app.py")

PLANO = {"objetivo": "Verificar devolução", "passos": ["Pedir dados", "Consultar o pedido", "Responder"],
         "informacoes_faltantes": []}


# --- Extração das chamadas -----------------------------------------------------

def test_extrai_chamadas_com_resultado(ctx):
    modelo = ModeloRoteirizado([("tool", "consultar_produto", {"nome": "Takamine GD20"}),
                                ("tool", "ler_politica", {"secao": "garantia"}), ("texto", "ok")])
    resposta = Atendente(ctx, model=modelo).responder("x")
    produto, politica = resposta.chamadas
    assert produto.resultado["produto"]["preco"] == "R$ 2.199,00"      # JSON vira dict
    assert politica.resultado.startswith("# Garantia")                  # texto continua texto
    assert resposta.ferramentas == ["consultar_produto", "ler_politica"]


def test_chamada_sem_resultado_nao_quebra():
    mensagens = [{"role": "assistant", "content": [{"toolUse": {"toolUseId": "a", "name": "x", "input": {}}}]}]
    assert extrair_chamadas(mensagens) == [ChamadaTool("x", {}, None)]


def test_ouvinte_recebe_inicio_e_fim(ctx):
    eventos = []
    modelo = ModeloRoteirizado([("tool", "hora_atual_loja", {}), ("texto", "ok")])
    Atendente(ctx, model=modelo).responder("x", ouvinte=lambda e, ch: eventos.append((e, ch.nome)))
    assert eventos == [("inicio", "hora_atual_loja"), ("fim", "hora_atual_loja")]


# --- Checklist do plano -------------------------------------------------------

@pytest.mark.parametrize("concluidas, rodando, finalizado, faltantes, esperado", [
    (0, True, False, False, ["rodando", "pendente", "pendente"]),
    (1, False, False, False, ["feito", "pendente", "pendente"]),
    (1, True, False, False, ["feito", "rodando", "pendente"]),
    (5, True, False, False, ["feito", "feito", "rodando"]),     # o último só fecha com a resposta
    (1, False, True, False, ["feito", "feito", "feito"]),       # resposta pronta: tudo concluído
    (0, False, True, True, ["feito", "pendente", "pendente"]),  # parou para perguntar ao cliente
])
def test_estado_dos_passos(concluidas, rodando, finalizado, faltantes, esperado):
    assert c.estado_dos_passos(3, concluidas, rodando, finalizado, faltantes) == esperado


def test_plano_aguardando_cliente_mostra_o_que_falta():
    plano = {**PLANO, "informacoes_faltantes": ["nome completo", "<script>"]}
    html = c.html_plano(plano, 0, rodando=False, finalizado=True)
    assert "Plano · 1 de 3" in html and "Aguardando do cliente" in html
    assert "<script>" not in html and "&lt;script&gt;" in html          # dado do modelo é escapado


def test_ultimo_plano_conta_tools_depois_dele():
    chamadas = [ChamadaTool("planejar", {}, PLANO), ChamadaTool("consultar_pedido", {}, {}),
                ChamadaTool("ler_politica", {}, "x")]
    assert c.ultimo_plano(chamadas) == (PLANO, 2)


# --- Cartões a partir das tools ------------------------------------------------

def test_cartao_de_produto_em_promocao(tools):
    html = c.html_produto(tools["consultar_produto"]("Kalani KAL-700T"))
    assert "R$ 359,00" in html and "R$ 323,10" in html and "−10% · Oferta Especial" in html
    assert "4x de R$ 80,78 sem juros" in html


def test_cartao_de_produto_indisponivel_com_alternativas(tools):
    html = c.html_produto(tools["consultar_produto"]("Giannini GF-3D"))
    assert "Temporariamente indisponível" in html and "Alternativas disponíveis" in html
    assert "PIX" not in html                                             # não oferece o que não vende


def test_cartao_de_pedido_com_prazos(tools):
    html = c.html_pedido(tools["consultar_pedido"]("Lucas Mendes da Silva", "67998123456", 4))
    assert "Pedido 4" in html and "até 29/12/2025" in html and html.count("Encerrado") == 3


def test_cartao_de_pedido_nao_verificado_nao_mostra_dados(tools):
    html = c.html_pedido(tools["consultar_pedido"]("Ana Carolina Ferreira", "(67) 99654-7821", 10))
    assert "Não foi possível confirmar" in html and "Pedido 10" not in html


def test_cartao_de_busca(tools):
    html = c.html_busca(tools["buscar_produtos"](categoria="Violões", preco_max=1000))
    assert "12 encontrado(s)" in html and html.count("<tr>") == 13


def test_politica_para_cliente_sem_orientacoes_internas(tools):
    chamada = ChamadaTool("ler_politica", {"secao": "frete-e-entregas"},
                          tools["ler_politica"]("frete-e-entregas"))
    titulo, texto = c.politica_para_cliente(chamada)
    assert titulo == "Frete, entregas e rastreamento"
    assert "R$ 35,00" in texto and "Orientação ao assistente" not in texto


def test_politica_interna_nao_e_exibida(tools):
    chamada = ChamadaTool("ler_politica", {"secao": "procedimentos-de-atendimento"},
                          tools["ler_politica"]("procedimentos-de-atendimento"))
    assert c.politica_para_cliente(chamada) is None


def test_resultado_inesperado_nao_gera_cartao():
    assert all(f("texto qualquer") is None for f in c.RENDERIZADORES_HTML.values())


# --- Página Streamlit -----------------------------------------------------------

def _app(atendente) -> AppTest:
    app = AppTest.from_file(APP, default_timeout=30)
    app.session_state["atendente"] = atendente
    return app.run()


def _textos(app) -> str:
    return "\n".join(m.value for m in app.markdown)


def test_pagina_inicial(ctx):
    app = _app(Atendente(ctx, model=ModeloRoteirizado([])))
    assert not app.exception
    assert "Sou o assistente virtual" in _textos(app)
    assert len(app.sidebar.button) == 7          # nova conversa + 6 perguntas de exemplo


def test_conversa_mostra_texto_e_cartao(ctx):
    modelo = ModeloRoteirizado([("tool", "consultar_produto", {"nome": "Takamine GD20"}),
                                ("texto", "O **Takamine GD20** sai por R$ 2.199,00.")])
    app = _app(Atendente(ctx, model=modelo, canal="ui"))
    app.chat_input[0].set_value("Quanto custa o Takamine GD20?").run()
    textos = _textos(app)
    assert not app.exception
    assert "O **Takamine GD20** sai por R$ 2.199,00." in textos
    assert "Fontes desta resposta" in textos and "R$ 2.089,05" in textos     # cartão do produto
    assert textos.index("R$ 2.089,05") < textos.index("O **Takamine GD20**")  # cartão antes do texto


def test_pergunta_de_exemplo_e_plano(ctx):
    modelo = ModeloRoteirizado([
        ("tool", "planejar", {"objetivo": "Verificar devolução", "passos": ["Pedir dados", "Consultar o pedido"],
                              "informacoes_faltantes": ["nome completo"]}),
        ("texto", "Me passa seu nome completo?")])
    app = _app(Atendente(ctx, model=modelo, canal="ui"))
    app.sidebar.button[4].click().run()          # "Me arrependi da compra..."
    textos = _textos(app)
    assert "Me arrependi da compra" in textos
    assert "Plano · 1 de 2" in textos and "Aguardando do cliente" in textos


def test_nova_conversa_limpa_historico_e_recria_o_atendente(ctx, monkeypatch):
    # Para recriar o atendente, o app lê o .env; aqui, um provedor fictício (nenhuma chamada é feita)
    for chave, valor in {"PROVIDER": "anthropic", "MODEL_ID": "teste", "ANTHROPIC_API_KEY": "x"}.items():
        monkeypatch.setenv(chave, valor)
    original = Atendente(ctx, model=ModeloRoteirizado([("texto", "Oi!")]))
    app = _app(original)
    app.chat_input[0].set_value("oi").run()
    assert len(app.session_state["historico"]) == 2
    app.sidebar.button[0].click().run()
    assert not app.exception
    assert app.session_state["historico"] == []
    assert app.session_state["atendente"] is not original


def test_configuracao_incompleta_mostra_erro(monkeypatch):
    monkeypatch.setenv("PROVIDER", "")
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert "Configuração incompleta" in app.error[0].value
