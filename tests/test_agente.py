"""Agente montado de ponta a ponta, com um modelo roteirizado (sem API)."""

from agente.agente import MAX_CARACTERES_MENSAGEM, Atendente
from agente.prompt import montar_prompt

from .modelo_roteirizado import ModeloRoteirizado, resultados_de_tools

TOOLS_ESPERADAS = {"planejar", "buscar_produtos", "consultar_produto", "consultar_pedido", "ler_politica",
                   "registrar_reclamacao", "hora_atual_loja", "entender_esquema", "consultar_banco"}


def test_prompt_tem_persona_regras_e_indice(ctx):
    prompt = montar_prompt(ctx)
    assert prompt.startswith("# Persona do assistente virtual")
    assert "amigo que entende de música" in prompt
    assert "`trocas-e-devolucoes`" in prompt
    assert "25/03/2026" in prompt
    assert "Nota de curadoria" not in prompt and "docs/" not in prompt


def test_agente_registra_todas_as_tools(ctx):
    modelo = ModeloRoteirizado([("texto", "Oi!")])
    atendente = Atendente(ctx, model=modelo)
    atendente.responder("oi")
    assert {s["name"] for s in modelo.tool_specs} == TOOLS_ESPERADAS
    assert modelo.system_prompt == montar_prompt(ctx)


def test_loop_chama_tool_e_devolve_resultado_ao_modelo(ctx):
    modelo = ModeloRoteirizado([
        ("tool", "consultar_produto", {"nome": "Takamine GD20"}),
        ("texto", "O Takamine GD20 sai por R$ 2.199,00."),
    ])
    atendente = Atendente(ctx, model=modelo)
    resposta = atendente.responder("Quanto custa o Takamine GD20?")
    assert resposta.texto == "O Takamine GD20 sai por R$ 2.199,00."
    assert resposta.ferramentas == ["consultar_produto"]
    assert "R$ 2.199,00" in resultados_de_tools(atendente.agente.messages)[0]


def test_fluxo_sql_livre_em_duas_etapas(ctx):
    modelo = ModeloRoteirizado([
        ("tool", "entender_esquema", {"tabelas": ["vw_catalogo"]}),
        ("tool", "consultar_banco", {"sql": "SELECT nome_errado FROM vw_catalogo"}),
        ("tool", "consultar_banco", {"sql": "SELECT name FROM vw_catalogo WHERE categoria = 'Guitarras' "
                                            "ORDER BY preco_final DESC LIMIT 1"}),
        ("texto", "A guitarra mais cara é a Gibson Les Paul Standard '50s."),
    ])
    resposta = Atendente(ctx, model=modelo).responder("Qual a guitarra mais cara?")
    assert resposta.ferramentas == ["entender_esquema", "consultar_banco", "consultar_banco"]


def test_memoria_da_conversa_entre_turnos(ctx):
    modelo = ModeloRoteirizado([("texto", "Oi, Ana!"), ("texto", "Claro.")])
    atendente = Atendente(ctx, model=modelo)
    atendente.responder("Oi, sou a Ana")
    atendente.responder("Você lembra meu nome?")
    textos = [b.get("text") for m in atendente.agente.messages for b in m["content"] if "text" in b]
    assert textos[:3] == ["Oi, sou a Ana", "Oi, Ana!", "Você lembra meu nome?"]


def test_sessao_persiste_entre_execucoes(ctx, tmp_path):
    a1 = Atendente(ctx, model=ModeloRoteirizado([("texto", "Anotado!")]),
                   session_id="maria", sessoes_dir=tmp_path)
    a1.responder("Meu violão favorito é o Yamaha C40")
    a2 = Atendente(ctx, model=ModeloRoteirizado([("texto", "ok")]),
                   session_id="maria", sessoes_dir=tmp_path)
    textos = [b.get("text") for m in a2.agente.messages for b in m["content"] if "text" in b]
    assert "Meu violão favorito é o Yamaha C40" in textos


def test_mensagem_longa_nao_chega_ao_modelo(ctx):
    modelo = ModeloRoteirizado([])
    resposta = Atendente(ctx, model=modelo).responder("a" * (MAX_CARACTERES_MENSAGEM + 1))
    assert modelo.chamadas == 0 and "longa" in resposta.texto


def test_erro_do_modelo_vira_mensagem_amigavel(ctx):
    modelo = ModeloRoteirizado([])            # roteiro vazio: o "modelo" quebra
    resposta = Atendente(ctx, model=modelo).responder("oi")
    assert "problema técnico" in resposta.texto and resposta.erro


def test_contador_de_sql_reinicia_a_cada_mensagem(ctx):
    sql = {"sql": "SELECT 1"}
    modelo = ModeloRoteirizado([("tool", "consultar_banco", sql)] * 4 + [("texto", "a")]
                               + [("tool", "consultar_banco", sql), ("texto", "b")])
    atendente = Atendente(ctx, model=modelo)
    atendente.responder("primeira")
    atendente.responder("segunda")
    assert "Limite" not in resultados_de_tools(atendente.agente.messages)[-1]


# --- Falhas do provedor e verificação de conexão ------------------------------

import pytest  # noqa: E402
from strands import ModelRetryStrategy  # noqa: E402
from strands.types.exceptions import ModelThrottledException  # noqa: E402

from agente.agente import MSG_LIMITE, MSG_ERRO, diagnostica, verificar_conexao  # noqa: E402

SEM_RETRY = ModelRetryStrategy(max_attempts=1, initial_delay=0, max_delay=0)


class ErroHttp(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


@pytest.mark.parametrize("excecao, categoria", [
    (ModelThrottledException("rate limit"), "limite"),
    (ErroHttp(429), "limite"),
    (ErroHttp(401), "chave"),
    (ErroHttp(402), "creditos"),
    (ErroHttp(403), "permissao"),
    (ErroHttp(404), "modelo"),
    (type("APIConnectionError", (Exception,), {})("Connection error."), "conexao"),
    (RuntimeError("???"), "outro"),
])
def test_diagnostica(excecao, categoria):
    assert diagnostica(excecao)[0] == categoria


def test_diagnostica_erro_encadeado():
    try:
        try:
            raise ErroHttp(403)
        except ErroHttp as interno:
            raise RuntimeError("falha no stream") from interno
    except RuntimeError as externo:
        assert diagnostica(externo)[0] == "permissao"


def test_limite_de_requisicoes_tem_mensagem_propria(ctx):
    modelo = ModeloRoteirizado([("erro", ModelThrottledException("rate limit"))])
    resposta = Atendente(ctx, model=modelo, retry_strategy=SEM_RETRY).responder("oi")
    assert resposta.texto == MSG_LIMITE
    assert "Limite de requisições" in resposta.erro


def test_permissao_negada_usa_mensagem_generica(ctx):
    modelo = ModeloRoteirizado([("erro", ErroHttp(403))])
    resposta = Atendente(ctx, model=modelo, retry_strategy=SEM_RETRY).responder("oi")
    assert resposta.texto == MSG_ERRO
    assert "MODEL_ID" in resposta.erro


def test_verificar_conexao_ok():
    assert verificar_conexao(ModeloRoteirizado([("texto", "ok")]), SEM_RETRY) is None


def test_verificar_conexao_com_falha():
    falha = verificar_conexao(ModeloRoteirizado([("erro", ErroHttp(401))]), SEM_RETRY)
    assert falha[0] == "chave"


def test_prompt_pede_texto_sem_markdown(ctx):
    assert "Não use Markdown" in montar_prompt(ctx)


def test_contexto_padrao_exige_o_banco(monkeypatch, tmp_path):
    # Sem o banco, CLI e interface avisam ao iniciar, e não só na primeira pergunta.
    from agente.contexto import Contexto
    monkeypatch.setenv("DB_PATH", str(tmp_path / "nao_existe.db"))
    with pytest.raises(FileNotFoundError, match="python -m etl.pipeline"):
        Contexto.padrao()
