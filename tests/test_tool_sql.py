"""Tools de SQL livre: documentação do esquema e guardrails da execução."""

import re
import sqlite3

import pytest

from agente.tools import sql as sql_tools


# --- entender_esquema ---------------------------------------------------------

def test_visao_geral_sem_notas_de_curadoria(tools):
    texto = tools["entender_esquema"]()
    assert "vw_catalogo" in texto and "categories" in texto
    assert "Nota de curadoria" not in texto and "docs/" not in texto


def test_detalha_tabelas_pedidas(tools):
    texto = tools["entender_esquema"](["vw_catalogo", "categories"])
    assert "# vw_catalogo" in texto and "# categories" in texto


def test_tabela_nao_documentada(tools):
    assert "não documentadas" in tools["entender_esquema"](["customers"])


@pytest.mark.parametrize("objeto", sorted(sql_tools.OBJETOS_PERMITIDOS))
def test_toda_coluna_permitida_esta_documentada(db, objeto):
    doc = (sql_tools.ESQUEMA_DIR / f"{objeto}.md").read_text(encoding="utf-8")
    documentadas = set(re.findall(r"^\| `(\w+)` \|", doc, flags=re.M))
    colunas = {c[1] for c in db.execute(f"PRAGMA table_info({objeto})")}
    assert colunas == documentadas


@pytest.mark.parametrize("objeto", sorted(sql_tools.OBJETOS_PERMITIDOS))
def test_exemplos_da_documentacao_executam(tools, objeto):
    doc = (sql_tools.ESQUEMA_DIR / f"{objeto}.md").read_text(encoding="utf-8")
    for exemplo in re.findall(r"```sql\n(.*?)```", doc, flags=re.S):
        r = tools["consultar_banco"](exemplo)
        assert "erro" not in r, (exemplo, r)
        assert r["quantidade"] > 0


# --- consultar_banco ----------------------------------------------------------

def test_consulta_valida(tools):
    r = tools["consultar_banco"](
        "SELECT name, preco_final FROM vw_catalogo WHERE categoria = 'Guitarras' "
        "ORDER BY preco_final DESC LIMIT 1")
    assert r["colunas"] == ["name", "preco_final"]
    assert r["linhas"] == [["Gibson Les Paul Standard '50s", 18900.0]]


@pytest.mark.parametrize("query", [
    "SELECT name, phone, email FROM customers",
    "SELECT * FROM orders",
    "SELECT * FROM vw_pedidos",
    "SELECT * FROM raw_customers",
    "SELECT * FROM sqlite_master",
    "SELECT * FROM products",
    "WITH vw_catalogo AS (SELECT * FROM customers) SELECT * FROM vw_catalogo",
    "SELECT name FROM vw_catalogo WHERE product_id IN (SELECT customer_id FROM customers)",
])
def test_bloqueia_dados_fora_do_catalogo(tools, query):
    r = tools["consultar_banco"](query)
    assert "Acesso negado" in r["erro"]


@pytest.mark.parametrize("query, trecho", [
    ("DELETE FROM products", "Só são permitidas"),
    ("UPDATE vw_catalogo SET preco_final = 1", "Só são permitidas"),
    ("PRAGMA table_info(customers)", "Só são permitidas"),
    ("ATTACH DATABASE 'x.db' AS x", "Só são permitidas"),
    ("SELECT 1; DROP TABLE products", "único comando"),
    ("SELECT load_extension('x')", "Acesso negado"),
])
def test_bloqueia_escrita_e_comandos_perigosos(tools, query, trecho):
    assert trecho in tools["consultar_banco"](query)["erro"]


def test_banco_continua_intacto(tools, db):
    tools["consultar_banco"]("DELETE FROM products")
    assert db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 65


def test_limita_linhas(tools):
    r = tools["consultar_banco"]("SELECT name FROM vw_catalogo")
    assert r["quantidade"] == sql_tools.MAX_LINHAS and r["truncado"] is True


def test_interrompe_consulta_demorada(tools):
    r = tools["consultar_banco"](
        "SELECT COUNT(*) FROM vw_catalogo a, vw_catalogo b, vw_catalogo c, vw_catalogo d")
    assert "demorar demais" in r["erro"]


def test_limite_de_consultas_por_turno(tools, ctx):
    for _ in range(sql_tools.MAX_CONSULTAS_POR_TURNO):
        tools["consultar_banco"]("SELECT 1")
    assert "Limite" in tools["consultar_banco"]("SELECT 1")["erro"]
    ctx.estado.novo_turno()
    assert "erro" not in tools["consultar_banco"]("SELECT 1")


def test_erro_de_sintaxe_volta_para_o_agente(tools):
    r = tools["consultar_banco"]("SELECT nome_inexistente FROM vw_catalogo")
    assert "no such column" in r["erro"] and "dica" in r


def test_autorizador_nega_por_padrao():
    assert sql_tools._autorizador(sqlite3.SQLITE_INSERT, "products", None, "main", None) == sqlite3.SQLITE_DENY
