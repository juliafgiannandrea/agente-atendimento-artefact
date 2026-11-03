"""Tools de catálogo: buscar_produtos e consultar_produto.

Leem a view gold `vw_catalogo`, que já traz preço vigente, PIX, parcelamento
e disponibilidade calculados pelo ETL com as regras de src/agente/regras.py.
"""

from __future__ import annotations

import difflib
import json
import sqlite3

from strands import tool

from agente import regras
from agente.contexto import Contexto
from agente.normalizacao import normaliza_texto

LIMITE_PADRAO = 20
LIMITE_MAXIMO = 30
MAX_CANDIDATOS = 5
MAX_ALTERNATIVAS = 3

ORDENACOES = {
    "preco_asc": "preco_final ASC, name",
    "preco_desc": "preco_final DESC, name",
    "nome": "name",
}

# Palavras dos nomes do catálogo que indicam o tipo do instrumento, usadas para
# sugerir alternativas semelhantes (marca, código do modelo e cor não contam).
TERMOS_DE_TIPO = {
    "nylon", "aco", "folk", "dreadnought", "eletrico", "7", "cordas", "estudante",
    "soprano", "concert", "tenor", "baritono", "solido",
    "stratocaster", "telecaster", "bass", "acustica", "sintetizador",
}

# Palavras que não ajudam a distinguir produtos na busca por nome
PALAVRAS_IGNORADAS = {"o", "a", "os", "as", "de", "do", "da", "um", "uma", "e", "com", "para"}


def _resumo(linha: sqlite3.Row) -> dict:
    """Campos que o agente precisa para apresentar um produto ao cliente."""
    produto = {
        "product_id": linha["product_id"],
        "nome": linha["name"],
        "categoria": linha["categoria"],
        "disponibilidade": linha["disponibilidade_rotulo"],
        "pode_ser_vendido": bool(linha["vendavel"]),
        "preco": regras.formata_brl(linha["preco_final"]),
    }
    if linha["em_promocao"]:
        produto["promocao"] = {
            "nome": linha["promocao_descricao"],
            "preco_original": regras.formata_brl(linha["preco_tabela"]),
            "desconto_percentual": linha["desconto_percentual"],
            "preco_promocional": regras.formata_brl(linha["preco_final"]),
        }
    return produto


def _detalhe(linha: sqlite3.Row) -> dict:
    produto = _resumo(linha)
    produto.update({
        "descricao": linha["description"],
        "especificacoes": json.loads(linha["specs"]),
        "preco_no_pix": regras.formata_brl(linha["preco_pix"]),
        "pix_observacao": ("Preço promocional: o desconto do PIX não se aplica."
                           if linha["em_promocao"] else "5% de desconto no PIX."),
        "parcelamento_maximo": (
            f"{linha['max_parcelas']}x de {regras.formata_brl(linha['valor_parcela_maxima'])} sem juros"
            if linha["max_parcelas"] > 1 else "Somente à vista"),
    })
    return produto


def _tokens(texto: str) -> set[str]:
    return {t for t in normaliza_texto(texto).replace("-", " ").split() if t not in PALAVRAS_IGNORADAS}


def _tipo(nome: str) -> set[str]:
    """Palavras do nome que descrevem o tipo do instrumento (ignora marca, modelo e cor)."""
    return _tokens(nome) & TERMOS_DE_TIPO


def _alternativas(conn: sqlite3.Connection, produto: sqlite3.Row) -> list[dict]:
    """Produtos vendáveis da mesma categoria, dos de tipo mais parecido (ex.:
    dreadnought, 7 cordas, nylon, barítono) aos de preço mais próximo.
    Manual 7.3: sugerir alternativas semelhantes."""
    candidatos = conn.execute(
        "SELECT * FROM vw_catalogo WHERE categoria = ? AND vendavel = 1 AND product_id <> ?",
        (produto["categoria"], produto["product_id"]),
    ).fetchall()
    base = _tipo(produto["name"])
    candidatos.sort(key=lambda c: (-len(base & _tipo(c["name"])),
                                   abs(c["preco_final"] - produto["preco_final"])))
    return [_resumo(c) for c in candidatos[:MAX_ALTERNATIVAS]]


def criar(ctx: Contexto) -> list:

    @tool
    def buscar_produtos(
        texto: str | None = None,
        categoria: str | None = None,
        preco_min: float | None = None,
        preco_max: float | None = None,
        apenas_disponiveis: bool = True,
        apenas_promocao: bool = False,
        ordenar_por: str = "preco_asc",
        limite: int = LIMITE_PADRAO,
    ) -> dict:
        """Busca produtos no catálogo da loja com filtros. Use para listar opções
        (ex.: "violões até R$ 1.000", "ukuleles em promoção", "guitarras Fender").

        Os preços já consideram promoções ativas. Por padrão traz só produtos
        disponíveis para venda.

        Args:
            texto: Palavras do nome ou da descrição (ex.: "nylon", "elétrico", "Yamaha").
            categoria: Nome da categoria (ex.: "Violões", "Ukuleles", "Guitarras", "Baixos",
                "Baterias", "Teclados", "Sopro", "Cordas Orquestrais").
            preco_min: Preço mínimo em reais, considerando o preço vigente.
            preco_max: Preço máximo em reais, considerando o preço vigente.
            apenas_disponiveis: Se True (padrão), exclui produtos sem estoque, descontinuados e em breve.
            apenas_promocao: Se True, traz só produtos com promoção ativa.
            ordenar_por: "preco_asc" (padrão), "preco_desc" ou "nome".
            limite: Máximo de produtos retornados (padrão 20, máximo 30).
        """
        condicoes, params = [], []
        if categoria:
            condicoes.append("categoria_norm LIKE ?")
            params.append(f"%{normaliza_texto(categoria)}%")
        if texto:
            for palavra in _tokens(texto):
                condicoes.append("(name_search LIKE ? OR descricao_norm LIKE ?)")
                params += [f"%{palavra}%", f"%{palavra}%"]
        if preco_min is not None:
            condicoes.append("preco_final >= ?")
            params.append(preco_min)
        if preco_max is not None:
            condicoes.append("preco_final <= ?")
            params.append(preco_max)
        if apenas_disponiveis:
            condicoes.append("vendavel = 1")
        if apenas_promocao:
            condicoes.append("em_promocao = 1")

        ordem = ORDENACOES.get(ordenar_por, ORDENACOES["preco_asc"])
        limite = max(1, min(int(limite), LIMITE_MAXIMO))
        where = " AND ".join(condicoes) or "1 = 1"

        with ctx.conexao_leitura() as conn:
            conn.create_function("normaliza", 1, lambda t: normaliza_texto(t or ""))
            sql = f"""
                SELECT * FROM (
                    SELECT *, normaliza(categoria) AS categoria_norm,
                              normaliza(description) AS descricao_norm
                    FROM vw_catalogo
                ) WHERE {where} ORDER BY {ordem}
            """
            linhas = conn.execute(sql, params).fetchall()

        return {
            "total_encontrado": len(linhas),
            "exibidos": min(len(linhas), limite),
            "produtos": [_resumo(l) for l in linhas[:limite]],
            "observacao": ("Nenhum produto encontrado com esses filtros. Não invente produtos; "
                           "ofereça ampliar a busca." if not linhas else None),
        }

    @tool
    def consultar_produto(nome: str) -> dict:
        """Consulta um produto específico pelo nome (pode ser parcial, ex.: "Takamine GD20").
        Retorna preço vigente, promoção, preço no PIX, parcelamento, disponibilidade e
        especificações. Se o produto não estiver disponível, sugere alternativas parecidas.
        Se o nome corresponder a vários produtos, retorna a lista para o cliente escolher.

        Args:
            nome: Nome ou parte do nome do produto.
        """
        busca = _tokens(nome)
        if not busca:
            return {"encontrado": False, "mensagem": "Informe o nome do produto."}

        with ctx.conexao_leitura() as conn:
            todos = conn.execute("SELECT * FROM vw_catalogo").fetchall()
            exatos = [p for p in todos if busca <= _tokens(p["name"])]

            if len(exatos) == 1:
                produto = exatos[0]
                resposta = {"encontrado": True, "produto": _detalhe(produto)}
                if not produto["vendavel"]:
                    resposta["alternativas_disponiveis"] = _alternativas(conn, produto)
                return resposta

            if len(exatos) > 1:
                return {
                    "encontrado": False,
                    "mensagem": "Mais de um produto corresponde ao nome. Pergunte qual deles.",
                    "candidatos": [_resumo(p) for p in exatos[:MAX_CANDIDATOS]],
                }

        # Nada exato: sugere nomes parecidos (erros de digitação, nome incompleto)
        nomes = {normaliza_texto(p["name"]): p for p in todos}
        parecidos = difflib.get_close_matches(normaliza_texto(nome), list(nomes), n=MAX_CANDIDATOS, cutoff=0.4)
        if not parecidos:
            parecidos = [n for n, p in nomes.items() if busca & _tokens(p["name"])][:MAX_CANDIDATOS]
        return {
            "encontrado": False,
            "mensagem": ("Produto não encontrado no catálogo. Não invente informações; "
                         "confirme com o cliente se é um destes ou ofereça uma busca."),
            "sugestoes": [_resumo(nomes[n]) for n in parecidos],
        }

    return [buscar_produtos, consultar_produto]
