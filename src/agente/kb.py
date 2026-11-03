"""Leitura da base de conhecimento (kb/) para o agente.

Os arquivos da base têm dois tipos de bloco de citação além do texto do manual:

    > **Orientação ao assistente:** ...   instrução de como agir; o agente LÊ
    > **Nota de curadoria:** ...          rastreabilidade para humanos (decisões,
                                           alertas, pendências); o agente NÃO lê

Este módulo remove as notas de curadoria e o cabeçalho YAML antes de entregar
o texto ao agente, para que referências internas (como "S03" ou
"docs/decisoes.md") nunca cheguem à conversa com o cliente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from agente.config import ROOT_DIR

KB_DIR = ROOT_DIR / "kb"
POLITICAS_DIR = KB_DIR / "politicas"
MARCADOR_CURADORIA = "Nota de curadoria"


@dataclass(frozen=True)
class Secao:
    id: str
    titulo: str
    publico: str
    quando_consultar: str
    caminho: Path


def _separa_frontmatter(texto: str) -> tuple[dict, str]:
    if not texto.startswith("---"):
        return {}, texto
    _, cabecalho, corpo = texto.split("---", 2)
    return yaml.safe_load(cabecalho) or {}, corpo


def remove_notas_de_curadoria(texto: str) -> str:
    """Remove os blocos de citação marcados como nota de curadoria.

    Um bloco é uma sequência de linhas iniciadas por '>'. Se a primeira linha
    do bloco contém o marcador, o bloco inteiro sai.
    """
    saida: list[str] = []
    bloco: list[str] = []

    def fecha_bloco() -> None:
        if bloco and MARCADOR_CURADORIA not in bloco[0]:
            saida.extend(bloco)
        bloco.clear()

    for linha in texto.splitlines():
        if linha.lstrip().startswith(">"):
            bloco.append(linha)
        else:
            fecha_bloco()
            saida.append(linha)
    fecha_bloco()

    limpo = "\n".join(saida)
    return re.sub(r"\n{3,}", "\n\n", limpo).strip() + "\n"


@lru_cache(maxsize=1)
def secoes() -> dict[str, Secao]:
    """Seções disponíveis, a partir do cabeçalho de cada arquivo."""
    resultado = {}
    for caminho in sorted(POLITICAS_DIR.glob("*.md")):
        meta, _ = _separa_frontmatter(caminho.read_text(encoding="utf-8"))
        resultado[meta["id"]] = Secao(
            id=meta["id"],
            titulo=meta["titulo"],
            publico=meta["publico"],
            quando_consultar=meta["quando_consultar"],
            caminho=caminho,
        )
    return resultado


def indice_para_agente() -> str:
    """Lista curta das seções (id, título e quando usar), para o agente escolher
    qual carregar. É gerada dos cabeçalhos, então não fica desatualizada."""
    linhas = ["Seções da base de políticas da loja (carregue só a que precisar):", ""]
    for s in secoes().values():
        interno = " [uso interno, não citar ao cliente]" if s.publico == "interno" else ""
        linhas.append(f"- `{s.id}` — {s.titulo}{interno}. {s.quando_consultar}")
    return "\n".join(linhas) + "\n"


def ler_secao(secao_id: str) -> str:
    """Conteúdo de uma seção, sem cabeçalho YAML e sem notas de curadoria."""
    try:
        secao = secoes()[secao_id]
    except KeyError:
        disponiveis = ", ".join(secoes())
        raise KeyError(f"Seção '{secao_id}' não existe. Disponíveis: {disponiveis}") from None
    _, corpo = _separa_frontmatter(secao.caminho.read_text(encoding="utf-8"))
    return remove_notas_de_curadoria(corpo)


def ler_persona() -> str:
    """Persona (kb/soul.md), sem notas de curadoria."""
    return remove_notas_de_curadoria((KB_DIR / "soul.md").read_text(encoding="utf-8"))
