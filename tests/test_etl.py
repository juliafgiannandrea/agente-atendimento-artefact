"""Testes do ETL: estrutura, idempotência, flags de qualidade e views gold."""

from __future__ import annotations

import json
import shutil
import sqlite3

import pytest

from etl import pipeline

from .conftest import REFERENCE_DATE


def _ids(db, sql):
    return [linha[0] for linha in db.execute(sql)]


# --- Estrutura e camadas ------------------------------------------------------

def test_contagens_da_camada_silver(etl_result):
    assert etl_result.contagens == {
        "categories": 9, "products": 65, "promotions": 25, "product_prices": 65,
        "customers": 50, "orders": 20, "order_items": 22,
    }


def test_bronze_e_copia_fiel_dos_csvs(db):
    raw = pipeline.extract()
    for tabela, df in raw.items():
        no_banco = [tuple(linha) for linha in db.execute(f"SELECT * FROM raw_{tabela}")]
        assert no_banco == list(df.itertuples(index=False, name=None))


def test_raw_nao_e_alterado(etl_result):
    assert pipeline.hashes_origem() == json.loads(
        sqlite3.connect(etl_result.db_path)
        .execute("SELECT valor FROM etl_metadata WHERE chave = 'hashes_origem'")
        .fetchone()[0]
    )


def test_restricoes_do_schema_estao_ativas(db):
    db.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO order_items (order_id, product_id, quantity, "
                   "dq_produto_fora_de_comercializacao) VALUES (999, 81, 1, 0)")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE products SET status = 'esgotado' WHERE product_id = 81")


# --- Idempotência -------------------------------------------------------------

def _conteudo(db_path):
    conn = sqlite3.connect(db_path)
    tabelas = _ids(conn, "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') "
                         "ORDER BY name")
    dados = {
        t: conn.execute(f"SELECT * FROM {t}").fetchall()
        for t in tabelas if t != "etl_metadata"   # executado_em muda a cada execução
    }
    conn.close()
    return dados


def test_etl_e_idempotente(tmp_path):
    kwargs = dict(reference_date=REFERENCE_DATE, report_path=tmp_path / "dq.md")
    pipeline.build(db_path=tmp_path / "a.db", **kwargs)
    relatorio_1 = (tmp_path / "dq.md").read_text()
    pipeline.build(db_path=tmp_path / "a.db", **kwargs)   # roda de novo por cima
    pipeline.build(db_path=tmp_path / "b.db", **kwargs)

    assert _conteudo(tmp_path / "a.db") == _conteudo(tmp_path / "b.db")
    assert (tmp_path / "dq.md").read_text() == relatorio_1   # relatório determinístico


def test_erro_bloqueia_e_preserva_banco_anterior(tmp_path):
    raw_dir = tmp_path / "raw"
    shutil.copytree(pipeline.RAW_DIR, raw_dir)
    db_path = tmp_path / "emporio.db"
    pipeline.build(db_path=db_path, raw_dir=raw_dir, reference_date=REFERENCE_DATE, report_path=None)
    antes = _conteudo(db_path)

    # Corrompe a origem: produto com categoria inexistente
    arquivo = raw_dir / pipeline.RAW_FILES["products"]
    texto = arquivo.read_text(encoding="utf-8")
    arquivo.write_text(texto.replace("81,599.9,Yamaha C40 Nylon Natural,5,",
                                     "81,599.9,Yamaha C40 Nylon Natural,99,"), encoding="utf-8")

    with pytest.raises(pipeline.EtlError) as exc:
        pipeline.build(db_path=db_path, raw_dir=raw_dir, reference_date=REFERENCE_DATE, report_path=None)
    assert [f.check_id for f in exc.value.falhas] == ["E03"]
    assert _conteudo(db_path) == antes


# --- Verificações de qualidade ------------------------------------------------

def test_nenhum_erro_na_base_original(etl_result):
    assert not [r for r in etl_result.resultados if r.severidade == "erro" and r.falhou]


def test_alertas_esperados(etl_result):
    com_ocorrencia = {r.check_id: r.quantidade for r in etl_result.alertas}
    assert com_ocorrencia == {
        "A01": 2,   # pedidos 3 e 20: total diferente da soma dos itens
        "A02": 3,   # pedidos 9, 16 e 18: parcela abaixo do mínimo
        "A03": 2,   # pedidos 3 e 14: produto em breve
        "A04": 3,   # produtos 93, 96 e 99: promoções duplicadas
        "A07": 1,   # produto 96: ativo sem estoque
        "A08": 3,   # sopro (madeiras e metais) e cordas orquestrais
        "A10": 1,   # pedido 8: enviado com previsão vencida
        "A13": 3,   # nomes de clientes contidos um no outro
    }


def test_flags_de_pedido(db):
    assert _ids(db, "SELECT order_id FROM orders WHERE dq_total_divergente = 1") == [3, 20]
    assert _ids(db, "SELECT order_id FROM orders WHERE dq_parcela_abaixo_minimo = 1") == [9, 16, 18]


def test_total_original_nao_e_alterado(db):
    pedido = db.execute("SELECT total_brl, itens_total FROM orders WHERE order_id = 3").fetchone()
    assert tuple(pedido) == (3450.0, 3498.0)


def test_atraso_depende_da_data_de_referencia(tmp_path):
    resultado = pipeline.build(db_path=tmp_path / "x.db", reference_date=REFERENCE_DATE.replace(month=2, day=1),
                               report_path=None)
    assert "A10" not in {r.check_id for r in resultado.alertas}


# --- Camada gold --------------------------------------------------------------

def _produto(db, product_id):
    return db.execute("SELECT * FROM vw_catalogo WHERE product_id = ?", (product_id,)).fetchone()


def test_catalogo_produto_sem_promocao(db):
    gd20 = _produto(db, 95)    # promoção de 12% inativa
    assert (gd20["preco_final"], gd20["preco_pix"], gd20["em_promocao"]) == (2199.0, 2089.05, 0)
    assert (gd20["max_parcelas"], gd20["valor_parcela_maxima"]) == (12, 183.25)


def test_catalogo_produto_em_promocao(db):
    kalani = _produto(db, 127)
    assert (kalani["preco_tabela"], kalani["desconto_percentual"], kalani["preco_final"]) == (359.0, 10, 323.1)
    assert kalani["preco_pix"] == 323.1          # PIX não acumula
    assert (kalani["max_parcelas"], kalani["valor_parcela_maxima"]) == (4, 80.78)


def test_catalogo_promocoes_ativas(db):
    assert _ids(db, "SELECT product_id FROM vw_catalogo WHERE em_promocao = 1 ORDER BY product_id") \
        == [90, 94, 121, 127]


@pytest.mark.parametrize("product_id, disponibilidade", [
    (96, "sem_estoque"), (113, "descontinuado"), (130, "em_breve"), (81, "disponivel"),
])
def test_catalogo_disponibilidade(db, product_id, disponibilidade):
    produto = _produto(db, product_id)
    assert produto["disponibilidade"] == disponibilidade
    assert produto["vendavel"] == (disponibilidade == "disponivel")


def test_violoes_ate_1000_vendaveis(db):
    """Caso enun-01 do eval set: 12 violões."""
    nomes = _ids(db, "SELECT name FROM vw_catalogo WHERE categoria = 'Violões' "
                     "AND vendavel = 1 AND preco_final <= 1000")
    assert len(nomes) == 12
    assert "Giannini GF-3D Dreadnought Sunburst" not in nomes


def test_busca_por_nome_normalizado(db):
    assert _ids(db, "SELECT product_id FROM vw_catalogo WHERE name_search LIKE '%takamine gd20%'") == [95]


def test_vw_pedidos_nao_expoe_dados_pessoais(db):
    colunas = [c[1] for c in db.execute("PRAGMA table_info(vw_pedidos)")]
    assert not {"name", "phone", "email"} & set(colunas)


def test_vw_pedidos_itens_e_rotulos(db):
    pedido = db.execute("SELECT * FROM vw_pedidos WHERE order_id = 15").fetchone()
    assert pedido["status_rotulo"] == "Pedido recebido, aguardando processamento"
    assert (pedido["forma_pagamento"], pedido["parcelas"]) == ("credit", 12)
    assert [i["product_id"] for i in json.loads(pedido["itens"])] == [82, 106]


def test_normalizacao_de_clientes(db):
    cliente = db.execute("SELECT name_norm, phone_digits, email_norm FROM customers "
                         "WHERE customer_id = 9").fetchone()
    assert tuple(cliente) == ("gabriel santos araujo", "67986543210", "gabriel.araujo@jmail.com")
