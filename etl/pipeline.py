"""ETL da Empório da Música: CSVs -> SQLite em camadas (ver docs/decisoes.md, D09).

Fluxo:
    extract     lê data/raw/*.csv como texto, sem tratamento (bronze)
    tipagem     converte tipos e padroniza valores; valores inválidos viram nulos
    erros       verificações bloqueantes; se alguma falha, o ETL para e o banco
                anterior é preservado
    enriquece   colunas calculadas e flags de qualidade (silver), usando as
                regras de src/agente/regras.py
    load        grava bronze, silver e views gold num banco temporário e o
                troca pelo definitivo só no fim (full refresh atômico)
    alertas     verificações não bloqueantes, gravadas em dq_results
    relatório   docs/data_quality.md gerado a partir de dq_results

Uso (a partir da raiz do repositório):
    python -m etl.pipeline
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from agente import regras
from agente.config import ROOT_DIR, get_db_path, get_reference_date
from agente.normalizacao import normaliza_email, normaliza_texto, so_digitos
from etl import quality, report

RAW_DIR = ROOT_DIR / "data" / "raw"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")
REPORT_PATH = ROOT_DIR / "docs" / "data_quality.md"

# Nome lógico da tabela -> arquivo de origem
RAW_FILES = {
    "categories": "desafio_tecnico_ai_eng - categories.csv",
    "products": "desafio_tecnico_ai_eng - products.csv",
    "promotions": "desafio_tecnico_ai_eng - promotions.csv",
    "customers": "desafio_tecnico_ai_eng - customers.csv",
    "orders": "desafio_tecnico_ai_eng - orders.csv",
    "order_items": "desafio_tecnico_ai_eng - order_items.csv",
}

# Ordem de carga respeitando as chaves estrangeiras
LOAD_ORDER = ("categories", "products", "promotions", "product_prices",
              "customers", "orders", "order_items")

TOLERANCIA_CENTAVOS = 0.01


class EtlError(RuntimeError):
    """Verificação bloqueante falhou; o banco anterior foi preservado."""

    def __init__(self, falhas: list[quality.Resultado]):
        self.falhas = falhas
        linhas = [f"  - [{r.check_id}] {r.descricao}: {r.quantidade} registro(s)" for r in falhas]
        super().__init__("ETL interrompido por erros de qualidade:\n" + "\n".join(linhas))


@dataclass
class ResultadoEtl:
    db_path: Path
    report_path: Path | None
    contagens: dict[str, int]
    resultados: list[quality.Resultado]

    @property
    def alertas(self) -> list[quality.Resultado]:
        return [r for r in self.resultados if r.severidade == "alerta" and r.falhou]


# ============================================================================
# EXTRACT (bronze)
# ============================================================================

def extract(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    """Lê os CSVs exatamente como estão: tudo texto, vazio continua vazio."""
    return {
        tabela: pd.read_csv(raw_dir / arquivo, dtype=str, keep_default_na=False)
        for tabela, arquivo in RAW_FILES.items()
    }


def hashes_origem(raw_dir: Path = RAW_DIR) -> dict[str, str]:
    return {
        arquivo: hashlib.sha256((raw_dir / arquivo).read_bytes()).hexdigest()
        for arquivo in RAW_FILES.values()
    }


# ============================================================================
# TIPAGEM
# ============================================================================

def _texto(serie: pd.Series) -> pd.Series:
    """Remove espaços nas pontas; string vazia vira nulo."""
    serie = serie.str.strip()
    return serie.mask(serie == "")


def _inteiro(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(_texto(serie), errors="coerce").astype("Int64")


def _decimal(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(_texto(serie), errors="coerce")


def _data(serie: pd.Series) -> pd.Series:
    """Datas ISO (AAAA-MM-DD); inválidas viram nulo."""
    convertida = pd.to_datetime(_texto(serie), format="%Y-%m-%d", errors="coerce")
    return convertida.dt.strftime("%Y-%m-%d").where(convertida.notna())


def _forma_pagamento(codigo) -> tuple[str | None, int | None]:
    try:
        return regras.interpreta_forma_pagamento(codigo)
    except (ValueError, AttributeError):
        return None, None


def tipagem(raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Converte tipos e padroniza valores, sem descartar nenhuma linha.

    Valores que não puderem ser convertidos viram nulos e são apontados pelas
    verificações de erro, em vez de quebrar o pipeline sem explicação.
    """
    cat = raw["categories"]
    categories = pd.DataFrame({
        "category_id": _inteiro(cat["category_id"]),
        "name": _texto(cat["name"]),
        "description": _texto(cat["description"]),
    })

    prd = raw["products"]
    products = pd.DataFrame({
        "product_id": _inteiro(prd["product_id"]),
        "name": _texto(prd["name"]),
        "category_id": _inteiro(prd["category_id"]),
        "description": _texto(prd["description"]),
        "price_brl": _decimal(prd["price_brl"]),
        "stock_quantity": _inteiro(prd["stock_quantity"]),
        "status": _texto(prd["status"]).str.lower(),
        "specs": _texto(prd["specs"]),
        "created_at": _data(prd["created_at"]),
    })
    products["name_search"] = products["name"].map(normaliza_texto, na_action="ignore")

    prm = raw["promotions"]
    promotions = pd.DataFrame({
        "promotion_id": _inteiro(prm["promotion_id"]),
        "product_id": _inteiro(prm["product_id"]),
        "discount_percent": _decimal(prm["discount_percent"]),
        "description": _texto(prm["description"]),
        "is_active": _inteiro(prm["is_active"]),
    })

    cst = raw["customers"]
    customers = pd.DataFrame({
        "customer_id": _inteiro(cst["customer_id"]),
        "name": _texto(cst["name"]),
        "phone": _texto(cst["phone"]),
        "email": _texto(cst["email"]),
        "city": _texto(cst["city"]),
    })
    customers["name_norm"] = customers["name"].map(normaliza_texto, na_action="ignore")
    customers["phone_digits"] = customers["phone"].map(so_digitos, na_action="ignore")
    customers["email_norm"] = customers["email"].map(normaliza_email, na_action="ignore")

    ordr = raw["orders"]
    orders = pd.DataFrame({
        "order_id": _inteiro(ordr["order_id"]),
        "customer_id": _inteiro(ordr["customer_id"]),
        "order_date": _data(ordr["order_date"]),
        "status": _texto(ordr["status"]).str.lower(),
        "total_brl": _decimal(ordr["total_brl"]),
        "payment_method_raw": _texto(ordr["payment_method"]),
        "tracking_code": _texto(ordr["tracking_code"]),
        "estimated_delivery": _data(ordr["estimated_delivery"]),
        "estimated_delivery_raw": _texto(ordr["estimated_delivery"]),
        "notes": _texto(ordr["notes"]),
    })
    formas = orders["payment_method_raw"].map(_forma_pagamento)
    orders["forma_pagamento"] = formas.str[0]
    orders["parcelas"] = formas.str[1].astype("Int64")

    itm = raw["order_items"]
    order_items = pd.DataFrame({
        "order_item_id": pd.RangeIndex(1, len(itm) + 1),   # o CSV não tem chave própria
        "order_id": _inteiro(itm["order_id"]),
        "product_id": _inteiro(itm["product_id"]),
        "quantity": _inteiro(itm["quantity"]),
    })

    return {
        "categories": categories,
        "products": products,
        "promotions": promotions,
        "customers": customers,
        "orders": orders,
        "order_items": order_items,
    }


# ============================================================================
# ENRIQUECIMENTO (silver): colunas calculadas e flags de qualidade
# ============================================================================

def _calcula_precos(products: pd.DataFrame, promotions: pd.DataFrame) -> pd.DataFrame:
    """Preço vigente de cada produto, aplicando S06 (conflito de promoções)."""
    ativas = promotions[promotions["is_active"] == 1]
    linhas = []
    for prod in products.itertuples(index=False):
        candidatas = ativas[ativas["product_id"] == prod.product_id].to_dict("records")
        promo = regras.promocao_vigente(candidatas)
        desconto = promo["discount_percent"] if promo else None
        preco_final = regras.preco_promocional(prod.price_brl, desconto)
        parcelas = regras.max_parcelas(preco_final)
        linhas.append({
            "product_id": prod.product_id,
            "preco_tabela": float(regras.arredonda(prod.price_brl)),
            "promotion_id": promo["promotion_id"] if promo else None,
            "promocao_descricao": promo["description"] if promo else None,
            "desconto_percentual": desconto,
            "preco_final": float(preco_final),
            "preco_pix": float(regras.preco_pix(float(preco_final), em_promocao=promo is not None)),
            "em_promocao": int(promo is not None),
            "max_parcelas": parcelas,
            "valor_parcela_maxima": float(regras.valor_parcela(preco_final, parcelas)),
        })
    precos = pd.DataFrame(linhas)
    precos["promotion_id"] = precos["promotion_id"].astype("Int64")
    return precos


def enriquece(silver: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    products = silver["products"].copy()
    promotions = silver["promotions"].copy()
    orders = silver["orders"].copy()
    order_items = silver["order_items"].copy()

    # Produtos: disponibilidade e vendável (S04)
    products["disponibilidade"] = [
        regras.disponibilidade(s, int(e))
        for s, e in zip(products["status"], products["stock_quantity"])
    ]
    products["vendavel"] = (products["disponibilidade"] == "disponivel").astype(int)

    # Promoções: duplicadas e conflito entre ativas (S06)
    por_produto = promotions.groupby("product_id")["promotion_id"].transform("count")
    ativas_por_produto = promotions.groupby("product_id")["is_active"].transform("sum")
    promotions["dq_duplicada"] = (por_produto > 1).astype(int)
    promotions["dq_conflito_ativo"] = (
        (promotions["is_active"] == 1) & (ativas_por_produto > 1)
    ).astype(int)

    # Preço vigente por produto
    product_prices = _calcula_precos(products, promotions)

    # Itens: produto que hoje está fora de comercialização (em breve ou
    # descontinuado). Estoque zero não entra: um item vendido pode ter esgotado
    # depois, o que é normal e não indica inconsistência.
    order_items = order_items.merge(
        products[["product_id", "status", "price_brl"]], on="product_id", how="left"
    )
    order_items["dq_produto_fora_de_comercializacao"] = (
        order_items["status"] != "active"
    ).astype(int)

    # Pedidos: total x soma dos itens (preço de tabela atual) e parcela mínima (S02)
    order_items["subtotal"] = order_items["quantity"] * order_items["price_brl"]
    itens_total = order_items.groupby("order_id")["subtotal"].sum().round(2)
    orders["itens_total"] = orders["order_id"].map(itens_total).fillna(0.0)
    orders["dq_total_divergente"] = (
        (orders["total_brl"] - orders["itens_total"]).abs() > TOLERANCIA_CENTAVOS
    ).astype(int)
    orders["dq_parcela_abaixo_minimo"] = [
        int(not regras.parcelamento_permitido(total, int(parc)))
        for total, parc in zip(orders["total_brl"], orders["parcelas"])
    ]

    order_items = order_items.drop(columns=["status", "price_brl", "subtotal"])
    orders = orders.drop(columns=["estimated_delivery_raw"])

    return {
        **silver,
        "products": products,
        "promotions": promotions,
        "product_prices": product_prices,
        "orders": orders,
        "order_items": order_items,
    }


# ============================================================================
# LOAD
# ============================================================================

def _tabelas_referencia() -> dict[str, pd.DataFrame]:
    return {
        "ref_status_pedido": pd.DataFrame(
            list(regras.STATUS_PEDIDO.items()), columns=["status", "rotulo"]),
        "ref_forma_pagamento": pd.DataFrame(
            list(regras.FORMAS_PAGAMENTO.items()), columns=["forma", "rotulo"]),
        "ref_disponibilidade": pd.DataFrame(
            list(regras.ROTULO_DISPONIBILIDADE.items()), columns=["disponibilidade", "rotulo"]),
    }


def _insere(conn: sqlite3.Connection, tabela: str, df: pd.DataFrame) -> None:
    """Insere respeitando as colunas e restrições declaradas no schema."""
    colunas = [linha[1] for linha in conn.execute(f"PRAGMA table_info({tabela})")]
    df = df[colunas].astype(object).where(df[colunas].notna(), None)
    marcadores = ", ".join("?" for _ in colunas)
    conn.executemany(
        f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({marcadores})",
        df.itertuples(index=False, name=None),
    )


def load(conn: sqlite3.Connection, raw: dict[str, pd.DataFrame],
         silver: dict[str, pd.DataFrame]) -> None:
    # Bronze: cópia fiel, sem restrições
    for tabela, df in raw.items():
        df.to_sql(f"raw_{tabela}", conn, index=False, dtype={c: "TEXT" for c in df.columns})

    # Silver + gold (DDL com PK/FK/CHECK e views)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    for tabela, df in _tabelas_referencia().items():
        _insere(conn, tabela, df)
    for tabela in LOAD_ORDER:
        _insere(conn, tabela, silver[tabela])


def _grava_metadados(conn: sqlite3.Connection, reference_date: date,
                     hashes: dict[str, str], contagens: dict[str, int]) -> None:
    metadados = {
        "executado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reference_date": reference_date.isoformat(),
        "hashes_origem": json.dumps(hashes, ensure_ascii=False),
        "contagens": json.dumps(contagens, ensure_ascii=False),
    }
    conn.executemany("INSERT INTO etl_metadata (chave, valor) VALUES (?, ?)", metadados.items())


def _grava_resultados(conn: sqlite3.Connection, resultados: list[quality.Resultado]) -> None:
    conn.executemany(
        "INSERT INTO dq_results (check_id, severidade, resultado, tabela, descricao,"
        " quantidade, registros, tratamento) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (r.check_id, r.severidade, "falhou" if r.falhou else "ok", r.tabela, r.descricao,
             r.quantidade, json.dumps(r.registros, ensure_ascii=False, default=str), r.tratamento)
            for r in resultados
        ],
    )


# ============================================================================
# ORQUESTRAÇÃO
# ============================================================================

def build(db_path: Path | None = None, raw_dir: Path = RAW_DIR,
          reference_date: date | None = None,
          report_path: Path | None = REPORT_PATH) -> ResultadoEtl:
    """Executa o ETL completo. Idempotente: a mesma entrada gera o mesmo banco."""
    db_path = Path(db_path or get_db_path())
    reference_date = reference_date or get_reference_date()

    raw = extract(raw_dir)
    tipado = tipagem(raw)

    erros = quality.verifica_erros(tipado)
    falhas = [r for r in erros if r.falhou]
    if falhas:
        raise EtlError(falhas)

    silver = enriquece(tipado)

    # Constrói num arquivo temporário e só troca no fim: se algo falhar,
    # o banco anterior continua intacto.
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_suffix(db_path.suffix + ".tmp")
    tmp_path.unlink(missing_ok=True)

    conn = sqlite3.connect(tmp_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            load(conn, raw, silver)
            alertas = quality.verifica_alertas(conn, reference_date)
            resultados = erros + alertas
            contagens = {t: len(silver[t]) for t in LOAD_ORDER}
            _grava_resultados(conn, resultados)
            _grava_metadados(conn, reference_date, hashes_origem(raw_dir), contagens)
    finally:
        conn.close()
    os.replace(tmp_path, db_path)

    if report_path is not None:
        report.gera(db_path, report_path)

    return ResultadoEtl(db_path, report_path, contagens, resultados)


def main() -> int:
    try:
        resultado = build()
    except EtlError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Banco gerado: {resultado.db_path.relative_to(ROOT_DIR)}")
    for tabela, n in resultado.contagens.items():
        print(f"  {tabela:<16} {n:>4} linhas")
    print(f"Verificações: {len(resultado.resultados)} executadas, "
          f"{len(resultado.alertas)} alerta(s), 0 erro(s)")
    for r in resultado.alertas:
        print(f"  ! [{r.check_id}] {r.descricao}: {r.quantidade}")
    if resultado.report_path:
        print(f"Relatório: {resultado.report_path.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
