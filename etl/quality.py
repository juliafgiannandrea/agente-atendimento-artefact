"""Verificações de qualidade de dados (ver docs/decisoes.md, D10).

Duas severidades:
    erro    bloqueia o ETL. Roda sobre os DataFrames tipados, antes da carga,
            para dar uma mensagem clara em vez de uma violação de restrição.
    alerta  não bloqueia. Roda em SQL sobre a camada silver já carregada e
            fica registrado em dq_results e no relatório.

Toda verificação é registrada, inclusive as que passaram, para que o
relatório mostre o que foi conferido e não só o que deu errado.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations

import pandas as pd

from agente import regras

PADRAO_RASTREIO = re.compile(r"^BR[A-Z0-9]{9}BR$")   # manual 5.3
PADRAO_TELEFONE = re.compile(r"^\(\d{2}\) \d{4,5}-\d{4}$")


@dataclass
class Resultado:
    check_id: str
    severidade: str           # "erro" | "alerta"
    tabela: str
    descricao: str
    tratamento: str
    registros: list[dict] = field(default_factory=list)

    @property
    def quantidade(self) -> int:
        return len(self.registros)

    @property
    def falhou(self) -> bool:
        return bool(self.registros)


# ============================================================================
# ERROS (bloqueantes) — sobre os DataFrames tipados
# ============================================================================

CHAVES_PRIMARIAS = {
    "categories": "category_id",
    "products": "product_id",
    "promotions": "promotion_id",
    "customers": "customer_id",
    "orders": "order_id",
}

OBRIGATORIOS = {
    "categories": ["category_id", "name"],
    "products": ["product_id", "name", "category_id", "price_brl", "stock_quantity",
                 "status", "specs", "created_at"],
    "promotions": ["promotion_id", "product_id", "discount_percent", "is_active"],
    "customers": ["customer_id", "name", "phone", "email"],
    "orders": ["order_id", "customer_id", "order_date", "status", "total_brl",
               "payment_method_raw", "forma_pagamento", "parcelas"],
    "order_items": ["order_id", "product_id", "quantity"],
}

CHAVES_ESTRANGEIRAS = [
    ("products", "category_id", "categories", "category_id"),
    ("promotions", "product_id", "products", "product_id"),
    ("orders", "customer_id", "customers", "customer_id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "product_id", "products", "product_id"),
]


def _id_registro(tabela: str, linha: pd.Series) -> dict:
    if tabela == "order_items":
        return {"order_id": linha.get("order_id"), "product_id": linha.get("product_id")}
    pk = CHAVES_PRIMARIAS[tabela]
    return {pk: linha.get(pk)}


def _pk_duplicada(t: dict[str, pd.DataFrame]) -> list[dict]:
    registros = []
    for tabela, pk in CHAVES_PRIMARIAS.items():
        dup = t[tabela][t[tabela][pk].duplicated(keep=False) & t[tabela][pk].notna()]
        registros += [{"tabela": tabela, pk: v} for v in sorted(dup[pk].unique())]
    return registros


def _obrigatorio_invalido(t: dict[str, pd.DataFrame]) -> list[dict]:
    registros = []
    for tabela, colunas in OBRIGATORIOS.items():
        df = t[tabela]
        for coluna in colunas:
            for _, linha in df[df[coluna].isna()].iterrows():
                registros.append({"tabela": tabela, "coluna": coluna, **_id_registro(tabela, linha)})
    # Coluna opcional: se preenchida, precisa ser uma data válida
    pedidos = t["orders"]
    invalida = pedidos["estimated_delivery_raw"].notna() & pedidos["estimated_delivery"].isna()
    registros += [{"tabela": "orders", "coluna": "estimated_delivery", "order_id": i}
                  for i in pedidos.loc[invalida, "order_id"]]
    return registros


def _fk_orfa(t: dict[str, pd.DataFrame]) -> list[dict]:
    registros = []
    for origem, coluna, destino, coluna_destino in CHAVES_ESTRANGEIRAS:
        df = t[origem]
        orfaos = df[df[coluna].notna() & ~df[coluna].isin(t[destino][coluna_destino])]
        for _, linha in orfaos.iterrows():
            registros.append({"tabela": origem, "coluna": coluna, "valor": linha[coluna],
                              **_id_registro(origem, linha)})
    return registros


def _fora_do_dominio(t: dict[str, pd.DataFrame]) -> list[dict]:
    registros = []
    p = t["products"]
    for _, linha in p[p["status"].notna() & ~p["status"].isin(regras.STATUS_PRODUTO)].iterrows():
        registros.append({"tabela": "products", "coluna": "status", "valor": linha["status"],
                          "product_id": linha["product_id"]})
    o = t["orders"]
    for _, linha in o[o["status"].notna() & ~o["status"].isin(regras.STATUS_PEDIDO)].iterrows():
        registros.append({"tabela": "orders", "coluna": "status", "valor": linha["status"],
                          "order_id": linha["order_id"]})
    pr = t["promotions"]
    for _, linha in pr[pr["is_active"].notna() & ~pr["is_active"].isin([0, 1])].iterrows():
        registros.append({"tabela": "promotions", "coluna": "is_active", "valor": linha["is_active"],
                          "promotion_id": linha["promotion_id"]})
    return registros


def _specs_invalido(t: dict[str, pd.DataFrame]) -> list[dict]:
    registros = []
    for _, linha in t["products"].dropna(subset=["specs"]).iterrows():
        try:
            valido = isinstance(json.loads(linha["specs"]), dict)
        except json.JSONDecodeError:
            valido = False
        if not valido:
            registros.append({"product_id": linha["product_id"]})
    return registros


def _fora_da_faixa(t: dict[str, pd.DataFrame]) -> list[dict]:
    regras_faixa = [
        ("products", "price_brl", lambda s: s > 0, "> 0"),
        ("products", "stock_quantity", lambda s: s >= 0, ">= 0"),
        ("promotions", "discount_percent", lambda s: (s > 0) & (s < 100), "entre 0 e 100"),
        ("orders", "total_brl", lambda s: s > 0, "> 0"),
        ("orders", "parcelas", lambda s: s.between(1, regras.MAX_PARCELAS), "entre 1 e 12"),
        ("order_items", "quantity", lambda s: s > 0, "> 0"),
    ]
    registros = []
    for tabela, coluna, condicao, esperado in regras_faixa:
        df = t[tabela]
        valores = df[coluna]
        fora = valores.notna() & ~condicao(valores).fillna(False).astype(bool)
        for _, linha in df[fora].iterrows():
            registros.append({"tabela": tabela, "coluna": coluna, "valor": linha[coluna],
                              "esperado": esperado, **_id_registro(tabela, linha)})
    return registros


VERIFICACOES_ERRO = [
    ("E01", "todas", "Chave primária duplicada", _pk_duplicada),
    ("E02", "todas", "Campo obrigatório ausente ou com tipo inválido", _obrigatorio_invalido),
    ("E03", "todas", "Chave estrangeira sem registro correspondente", _fk_orfa),
    ("E04", "todas", "Valor fora do domínio permitido (status, forma de pagamento, flags)", _fora_do_dominio),
    ("E05", "products", "Coluna specs não é um objeto JSON válido", _specs_invalido),
    ("E06", "todas", "Valor numérico fora da faixa válida", _fora_da_faixa),
]


def verifica_erros(tipado: dict[str, pd.DataFrame]) -> list[Resultado]:
    resultados = []
    for check_id, tabela, descricao, funcao in VERIFICACOES_ERRO:
        resultados.append(Resultado(
            check_id=check_id, severidade="erro", tabela=tabela, descricao=descricao,
            tratamento="Bloqueia o ETL: corrigir a origem antes de carregar.",
            registros=_limpa(funcao(tipado)),
        ))
    return resultados


# ============================================================================
# ALERTAS (não bloqueantes) — em SQL sobre a camada silver
# ============================================================================

def _consulta(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    cursor = conn.execute(sql, params)
    colunas = [c[0] for c in cursor.description]
    return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def _clientes_parecidos(conn: sqlite3.Connection) -> list[dict]:
    """Pares em que os nomes de um cliente estão contidos no nome do outro
    (ex.: "Bruno Carvalho" e "Bruno Carvalho Martins")."""
    clientes = _consulta(conn, "SELECT customer_id, name, name_norm FROM customers ORDER BY customer_id")
    pares = []
    for a, b in combinations(clientes, 2):
        ta, tb = set(a["name_norm"].split()), set(b["name_norm"].split())
        if len(ta) >= 2 and len(tb) >= 2 and (ta <= tb or tb <= ta):
            pares.append({"cliente_a": a["customer_id"], "nome_a": a["name"],
                          "cliente_b": b["customer_id"], "nome_b": b["name"]})
    return pares


def _specs_heterogeneas(conn: sqlite3.Connection) -> list[dict]:
    produtos = _consulta(conn, """
        SELECT c.name AS categoria, p.product_id, p.specs
        FROM products p JOIN categories c ON c.category_id = p.category_id
    """)
    por_categoria: dict[str, set[tuple]] = {}
    for p in produtos:
        por_categoria.setdefault(p["categoria"], set()).add(tuple(sorted(json.loads(p["specs"]))))
    return [
        {"categoria": cat, "variacoes_de_chaves": len(conj),
         "chaves": sorted({k for chaves in conj for k in chaves})}
        for cat, conj in sorted(por_categoria.items()) if len(conj) > 1
    ]


def verifica_alertas(conn: sqlite3.Connection, reference_date: date) -> list[Resultado]:
    ref = reference_date.isoformat()

    alertas = [
        Resultado(
            "A01", "alerta", "orders",
            "Total do pedido diferente da soma dos itens a preço de tabela atual",
            "Mantido o total_brl original (valor cobrado). A base não tem preço unitário "
            "por item: a diferença pode ser desconto ou mudança de preço, não necessariamente erro.",
            _consulta(conn, """
                SELECT order_id, total_brl, itens_total,
                       ROUND(total_brl - itens_total, 2) AS diferenca
                FROM orders WHERE dq_total_divergente = 1 ORDER BY order_id
            """),
        ),
        Resultado(
            "A02", "alerta", "orders",
            "Parcelamento abaixo da parcela mínima da seção 3.1 do manual (S02)",
            "Histórico mantido como está. O agente aplica a regra vigente ao simular "
            "parcelamentos novos; o pedido antigo não é contestado com o cliente.",
            [
                {**r,
                 "valor_parcela": float(regras.valor_parcela(r["total_brl"], r["parcelas"])),
                 "parcela_minima": float(regras.parcela_minima(r["parcelas"]))}
                for r in _consulta(conn, """
                    SELECT order_id, total_brl, parcelas
                    FROM orders WHERE dq_parcela_abaixo_minimo = 1 ORDER BY order_id
                """)
            ],
        ),
        Resultado(
            "A03", "alerta", "order_items",
            "Pedido contém produto que hoje está fora de comercialização (em breve ou descontinuado)",
            "Pedido mantido. O status atual pode ter mudado depois da venda; o agente "
            "segue o status atual para novas ofertas (S04).",
            _consulta(conn, """
                SELECT oi.order_id, o.status AS status_pedido, oi.product_id,
                       p.name, p.status AS status_produto
                FROM order_items oi
                JOIN orders o   ON o.order_id = oi.order_id
                JOIN products p ON p.product_id = oi.product_id
                WHERE oi.dq_produto_fora_de_comercializacao = 1 ORDER BY oi.order_id
            """),
        ),
        Resultado(
            "A04", "alerta", "promotions",
            "Produto com mais de uma promoção cadastrada",
            "Informativo enquanto no máximo uma estiver ativa; o conflito entre ativas é o A05.",
            _consulta(conn, """
                SELECT product_id,
                       json_group_array(promotion_id) AS promocoes,
                       SUM(is_active) AS ativas
                FROM promotions WHERE dq_duplicada = 1
                GROUP BY product_id ORDER BY product_id
            """),
        ),
        Resultado(
            "A05", "alerta", "promotions",
            "Produto com mais de uma promoção ativa ao mesmo tempo (S06)",
            "Nenhuma das promoções é aplicada: o produto sai pelo preço de tabela até a "
            "equipe resolver o conflito.",
            _consulta(conn, """
                SELECT product_id, json_group_array(promotion_id) AS promocoes_ativas
                FROM promotions WHERE dq_conflito_ativo = 1
                GROUP BY product_id ORDER BY product_id
            """),
        ),
        Resultado(
            "A06", "alerta", "promotions",
            "Promoção ativa em produto que não está disponível para venda",
            "A promoção não é oferecida, porque o produto não é vendável (S04).",
            _consulta(conn, """
                SELECT pr.promotion_id, pr.product_id, p.name, p.disponibilidade
                FROM promotions pr JOIN products p ON p.product_id = pr.product_id
                WHERE pr.is_active = 1 AND p.vendavel = 0 ORDER BY pr.promotion_id
            """),
        ),
        Resultado(
            "A07", "alerta", "products",
            "Produto ativo sem estoque",
            "Informado como temporariamente indisponível, com sugestão de alternativas "
            "(manual 7.3).",
            _consulta(conn, """
                SELECT product_id, name FROM products
                WHERE status = 'active' AND stock_quantity = 0 ORDER BY product_id
            """),
        ),
        Resultado(
            "A08", "alerta", "categories",
            "Categoria sem nenhum produto cadastrado",
            "O agente informa que não há itens dessa categoria no momento, sem inventar "
            "produtos, mesmo que o manual cite a categoria.",
            _consulta(conn, """
                SELECT c.category_id, c.name FROM categories c
                LEFT JOIN products p ON p.category_id = c.category_id
                WHERE p.product_id IS NULL ORDER BY c.category_id
            """),
        ),
        Resultado(
            "A09", "alerta", "products",
            "Chaves de specs diferentes entre produtos da mesma categoria",
            "Specs mantidas como JSON; o agente lê as chaves presentes em cada produto, "
            "sem supor um formato fixo por categoria.",
            _specs_heterogeneas(conn),
        ),
        Resultado(
            "A10", "alerta", "orders",
            "Pedido enviado com previsão de entrega vencida na data de referência",
            "O agente reconhece o atraso e encaminha à equipe (retorno em até 24 horas úteis).",
            _consulta(conn, """
                SELECT order_id, estimated_delivery,
                       CAST(julianday(?) - julianday(estimated_delivery) AS INTEGER) AS dias_atraso
                FROM orders
                WHERE status = 'shipped' AND estimated_delivery < ? ORDER BY order_id
            """, (ref, ref)),
        ),
        Resultado(
            "A11", "alerta", "orders",
            "Pedido com data posterior à data de referência",
            "Indica data de referência mal configurada (S01) ou dado futuro na origem.",
            _consulta(conn, "SELECT order_id, order_date FROM orders WHERE order_date > ? "
                            "ORDER BY order_id", (ref,)),
        ),
        Resultado(
            "A12", "alerta", "orders",
            "Código de rastreio ausente, fora do padrão ou incoerente com o status",
            "O agente só informa rastreio de pedidos enviados ou entregues.",
            _rastreio_incoerente(conn),
        ),
        Resultado(
            "A13", "alerta", "customers",
            "Clientes com nomes contidos um no outro",
            "Risco na verificação de identidade: a tool exige nome completo + telefone ou "
            "e-mail (S05), nunca só o nome.",
            _clientes_parecidos(conn),
        ),
        Resultado(
            "A14", "alerta", "customers",
            "Telefone fora do formato (DD) NNNNN-NNNN",
            "Verificação de identidade compara só os dígitos (phone_digits).",
            [r for r in _consulta(conn, "SELECT customer_id, phone FROM customers ORDER BY customer_id")
             if not PADRAO_TELEFONE.match(r["phone"])],
        ),
        Resultado(
            "A15", "alerta", "orders",
            "Pedido cancelado sem motivo registrado",
            "O agente informa o cancelamento e encaminha à equipe para detalhes.",
            _consulta(conn, "SELECT order_id FROM orders WHERE status = 'cancelled' "
                            "AND notes IS NULL ORDER BY order_id"),
        ),
    ]
    for a in alertas:
        a.registros = _limpa(a.registros)
    return alertas


def _rastreio_incoerente(conn: sqlite3.Connection) -> list[dict]:
    registros = []
    for r in _consulta(conn, "SELECT order_id, status, tracking_code FROM orders ORDER BY order_id"):
        codigo, status = r["tracking_code"], r["status"]
        if status in ("shipped", "delivered"):
            if codigo is None:
                registros.append({**r, "problema": "enviado/entregue sem rastreio"})
            elif not PADRAO_RASTREIO.match(codigo):
                registros.append({**r, "problema": "fora do padrão BR + 9 caracteres + BR"})
        elif codigo is not None:
            registros.append({**r, "problema": "rastreio em pedido não enviado"})
    return registros


def _limpa(registros: list[dict]) -> list[dict]:
    """Converte tipos do pandas/numpy para tipos nativos (serialização JSON)."""
    def nativo(v):
        if hasattr(v, "item"):
            return v.item()
        if v is pd.NA:
            return None
        if isinstance(v, str) and v.startswith("["):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v
    return [{k: nativo(v) for k, v in r.items()} for r in registros]
