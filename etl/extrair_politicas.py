"""Extrai o texto do manual de políticas (PDF) para Markdown (ver docs/decisoes.md, D07).

Gera kb/_fonte/manual_extraido.md: o conteúdo bruto do PDF, página a página,
com as tabelas convertidas para Markdown. Esse arquivo é a fonte rastreável
da base de conhecimento:

    PDF  ->  kb/_fonte/manual_extraido.md  (automático, este script)
         ->  kb/politicas/*.md              (curadoria humana, por seção)

Os testes (tests/test_kb.py) conferem que os valores citados nas políticas
curadas (preços, prazos, percentuais, telefones) existem no texto extraído,
para que a curadoria não introduza informação que não está no manual.

Uso (a partir da raiz do repositório):
    python -m etl.extrair_politicas
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pdfplumber

from agente.config import ROOT_DIR

PDF_PATH = ROOT_DIR / "data" / "raw" / "políticas_da_loja.pdf"
SAIDA_PATH = ROOT_DIR / "kb" / "_fonte" / "manual_extraido.md"

RODAPE = re.compile(r"^Página \d+$")
CABECALHO = "Empório da Música Manual de Políticas e Procedimentos"


def _tabela_md(tabela: list[list[str | None]]) -> str:
    linhas = [[(c or "").replace("\n", " ").strip() for c in linha] for linha in tabela]
    cabecalho, *corpo = linhas
    md = ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho)]
    md += ["| " + " | ".join(linha) + " |" for linha in corpo]
    return "\n".join(md)


def _texto_sem_tabelas(pagina) -> str:
    """Texto da página sem as regiões ocupadas por tabelas (evita duplicar)."""
    caixas = [t.bbox for t in pagina.find_tables()]

    def fora_das_tabelas(obj) -> bool:
        x, y = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
        return not any(x0 <= x <= x1 and top <= y <= bottom for x0, top, x1, bottom in caixas)

    texto = pagina.filter(fora_das_tabelas).extract_text() or ""
    linhas = [l.strip() for l in texto.splitlines()]
    return "\n".join(l for l in linhas if l and l != CABECALHO and not RODAPE.match(l))


def extrai(pdf_path: Path = PDF_PATH) -> str:
    sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    partes = [
        "# Manual de políticas — extração bruta\n",
        "> Gerado automaticamente por `python -m etl.extrair_politicas`. Não edite à mão.",
        f"> Origem: `data/raw/{pdf_path.name}` (SHA-256 `{sha[:16]}…`).",
        "> Texto sem curadoria: a versão revisada e dividida por seção está em `kb/politicas/`.\n",
    ]
    with pdfplumber.open(pdf_path) as pdf:
        for numero, pagina in enumerate(pdf.pages, start=1):
            partes.append(f"\n<!-- página {numero} -->\n")
            partes.append(_texto_sem_tabelas(pagina))
            for tabela in pagina.extract_tables():
                partes.append("\n" + _tabela_md(tabela))
    return "\n".join(partes).rstrip() + "\n"


def main() -> int:
    SAIDA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAIDA_PATH.write_text(extrai(), encoding="utf-8")
    print(f"Extração gravada em {SAIDA_PATH.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
