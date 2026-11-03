"""Tools de SQL livre: entender_esquema e consultar_banco.

Usadas só quando a pergunta não se encaixa nas tools fechadas (ex.: "qual o
violão elétrico com tampo sólido mais barato?", "quantos ukuleles tenor vocês
têm?"). O agente primeiro lê a documentação do esquema (kb/esquema/), monta a
query e então a executa; pode repetir se o resultado não bastar.

Guardrails, todos em código:
    - conexão somente leitura (mode=ro);
    - um único SELECT (ou WITH ... SELECT) por chamada;
    - autorizador do SQLite: só lê o catálogo (vw_catalogo e categories). Dados de
      clientes e pedidos ficam fora, para não contornar a verificação de identidade;
    - limite de linhas, de tamanho da query, de tempo de execução e de consultas
      por mensagem do cliente.
"""

from __future__ import annotations

import re
import sqlite3

from strands import tool

from agente.config import ROOT_DIR
from agente.contexto import Contexto
from agente.kb import remove_notas_de_curadoria

ESQUEMA_DIR = ROOT_DIR / "kb" / "esquema"

OBJETOS_PERMITIDOS = {"vw_catalogo", "categories"}
# Tabelas lidas internamente pela view vw_catalogo (nenhuma tem dado pessoal)
DEPENDENCIAS_DA_VIEW = {"products", "categories", "product_prices", "ref_disponibilidade"}
FUNCOES_BLOQUEADAS = {"load_extension"}

MAX_LINHAS = 50
MAX_CARACTERES_SQL = 2000
MAX_CONSULTAS_POR_TURNO = 4
MAX_PASSOS_VM = 2_000_000          # passos da máquina virtual do SQLite (~ tempo de execução)
INTERVALO_PROGRESSO = 1_000

INICIO_VALIDO = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def _autorizador(acao, arg1, arg2, _banco, origem):
    if acao in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    if acao == sqlite3.SQLITE_READ:
        tabela, coluna = arg1, arg2
        if tabela in OBJETOS_PERMITIDOS:
            return sqlite3.SQLITE_OK
        if tabela in DEPENDENCIAS_DA_VIEW and (origem == "vw_catalogo" or coluna == ""):
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    if acao == sqlite3.SQLITE_FUNCTION:
        return sqlite3.SQLITE_DENY if (arg2 or "").lower() in FUNCOES_BLOQUEADAS else sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY   # INSERT, UPDATE, DELETE, PRAGMA, ATTACH, CREATE...


def _valida(sql: str) -> str | None:
    """Devolve a mensagem de erro, ou None se a query pode ser executada."""
    if len(sql) > MAX_CARACTERES_SQL:
        return f"Query muito longa (máximo {MAX_CARACTERES_SQL} caracteres)."
    if ";" in sql.strip().rstrip(";"):
        return "Envie um único comando por vez, sem ';' no meio."
    if not INICIO_VALIDO.match(sql):
        return "Só são permitidas consultas de leitura (SELECT ou WITH ... SELECT)."
    return None


def _documento(nome: str) -> str:
    return remove_notas_de_curadoria((ESQUEMA_DIR / f"{nome}.md").read_text(encoding="utf-8"))


def documentos_disponiveis() -> list[str]:
    return sorted(p.stem for p in ESQUEMA_DIR.glob("*.md") if p.stem != "index")


def criar(ctx: Contexto) -> list:

    @tool
    def entender_esquema(tabelas: list[str] | None = None) -> str:
        """Lê a documentação do banco de dados do catálogo, para montar uma query SQL.
        Use ANTES de consultar_banco, e só quando nenhuma outra ferramenta resolver a
        pergunta. Sem argumentos, retorna a visão geral e as regras; com nomes, retorna
        as colunas e exemplos das tabelas pedidas.

        Args:
            tabelas: Nomes das tabelas a detalhar (ex.: ["vw_catalogo"]). Vazio para a visão geral.
        """
        if not tabelas:
            return _documento("index")
        disponiveis = documentos_disponiveis()
        desconhecidas = [t for t in tabelas if t not in disponiveis]
        if desconhecidas:
            return f"Tabelas não documentadas: {desconhecidas}. Disponíveis: {disponiveis}."
        return "\n\n".join(_documento(t) for t in tabelas)

    @tool
    def consultar_banco(sql: str) -> dict:
        """Executa uma consulta SQL (SQLite, somente leitura) no catálogo da loja e retorna
        as linhas. Use só depois de entender_esquema, e só para perguntas que as outras
        ferramentas não respondem. Se o resultado não bastar, ajuste a query e chame de novo.

        Args:
            sql: Um único comando SELECT (ou WITH ... SELECT).
        """
        estado = ctx.estado
        if estado.consultas_sql_no_turno >= MAX_CONSULTAS_POR_TURNO:
            return {"erro": (f"Limite de {MAX_CONSULTAS_POR_TURNO} consultas SQL por mensagem atingido. "
                             "Responda com o que já tem ou diga que vai verificar com a equipe.")}
        estado.consultas_sql_no_turno += 1

        erro = _valida(sql)
        if erro:
            return {"erro": erro}

        passos = {"n": 0}

        def progresso() -> int:
            passos["n"] += INTERVALO_PROGRESSO
            return 1 if passos["n"] > MAX_PASSOS_VM else 0

        with ctx.conexao_leitura() as conn:
            conn.set_authorizer(_autorizador)
            conn.set_progress_handler(progresso, INTERVALO_PROGRESSO)
            try:
                cursor = conn.execute(sql.strip().rstrip(";"))
                linhas = cursor.fetchmany(MAX_LINHAS + 1)
            except sqlite3.DatabaseError as exc:
                mensagem = str(exc)
                if "not authorized" in mensagem or "prohibited" in mensagem:
                    mensagem = (f"Acesso negado. Só é possível consultar: "
                                f"{', '.join(sorted(OBJETOS_PERMITIDOS))}.")
                elif "interrupted" in mensagem:
                    mensagem = "Consulta interrompida por demorar demais. Simplifique a query."
                return {"erro": mensagem, "dica": "Revise a query com base em entender_esquema."}
            colunas = [c[0] for c in cursor.description]

        truncado = len(linhas) > MAX_LINHAS
        return {
            "colunas": colunas,
            "linhas": [list(l) for l in linhas[:MAX_LINHAS]],
            "quantidade": min(len(linhas), MAX_LINHAS),
            "truncado": truncado,
            "observacao": (f"Resultado limitado a {MAX_LINHAS} linhas; refine a query." if truncado
                           else "Nenhuma linha encontrada." if not linhas else None),
        }

    return [entender_esquema, consultar_banco]
