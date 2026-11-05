"""Gera os PDFs do projeto a partir do README e da documentação.

- docs/readme.pdf: só o README. É o arquivo de envio do Written Case.
- docs/documentacao.pdf: README, arquitetura, processo, decisões, uso de IA e anexos.

Os PDFs são sempre gerados a partir dos .md, para nunca divergirem do que está no
repositório.

Uso (a partir da raiz do repositório):
    pip install -r requirements-docs.txt
    playwright install chromium
    python docs/gerar_pdf.py

Links para arquivos que não estão no PDF (código, kb/, exemplos/) apontam para o
repositório no GitHub (--repo muda o endereço; --repo "" deixa como texto).
"""

from __future__ import annotations

import argparse
import html
import re
from datetime import date
from pathlib import Path

from markdown_it import MarkdownIt
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
REPO_PADRAO = "https://github.com/juliafgiannandrea/agente-atendimento-artefact"

# (arquivo, título no PDF). A ordem é a ordem de leitura sugerida.
CAPITULOS_COMPLETOS = [
    ("README.md", "Visão geral (README)"),
    ("docs/arquitetura.md", "Arquitetura"),
    ("docs/processo.md", "Processo: o que foi feito em cada etapa"),
    ("docs/decisoes.md", "Registro de decisões técnicas"),
    ("docs/uso-de-ia.md", "Uso de assistentes de IA"),
    ("docs/data_quality.md", "Anexo A — Relatório de qualidade de dados"),
    ("kb/pendencias_gerencia.md", "Anexo B — Pendências para a gerência"),
    ("kb/soul.md", "Anexo C — Persona do agente"),
]

# arquivo de saída -> (capítulos, descrição na capa)
VERSOES = {
    "docs/readme.pdf": ([("README.md", "README")], "README do projeto"),
    "docs/documentacao.pdf": (CAPITULOS_COMPLETOS, "Documentação completa: README, arquitetura, processo, decisões e uso de IA"),
}

CSS = """
@page { size: A4; margin: 20mm 18mm 20mm 18mm; }
:root { --navy: #0D1634; --magenta: #E0005A; --cinza: #5A6178; --linha: #DDE0E8; --fundo: #F5F6FA; }
* { box-sizing: border-box; }
body { font-family: "IBM Plex Sans", Inter, "Helvetica Neue", Arial, sans-serif; color: var(--navy);
       font-size: 10.5pt; line-height: 1.5; margin: 0; }
h1, h2, h3, h4 { line-height: 1.25; break-after: avoid; }
h1 { font-size: 21pt; font-weight: 600; margin: 0 0 14pt; padding-bottom: 6pt; border-bottom: 2.5pt solid var(--magenta); }
h2 { font-size: 14pt; font-weight: 600; margin: 20pt 0 6pt; }
h3 { font-size: 11.5pt; font-weight: 600; margin: 14pt 0 4pt; }
h4 { font-size: 10.5pt; font-weight: 600; margin: 10pt 0 4pt; }
p { margin: 0 0 7pt; }
ul, ol { margin: 0 0 7pt; padding-left: 16pt; }
li { margin: 1.5pt 0; }
li > ul, li > ol { margin: 2pt 0; }
a { color: var(--magenta); text-decoration: none; }
code { font-family: "DejaVu Sans Mono", Menlo, Consolas, monospace; font-size: 8.6pt;
       background: var(--fundo); padding: 0.5pt 3pt; border-radius: 3pt; }
pre { background: var(--fundo); border: 0.75pt solid var(--linha); border-radius: 4pt; padding: 7pt 9pt;
      font-size: 8.4pt; line-height: 1.4; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: inherit; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 10pt; font-size: 8.8pt; break-inside: auto; }
th, td { border: 0.75pt solid var(--linha); padding: 3.5pt 5pt; text-align: left; vertical-align: top; }
th { background: var(--fundo); font-weight: 600; }
tr { break-inside: avoid; }
blockquote { margin: 6pt 0 8pt; padding: 4pt 10pt; border-left: 3pt solid var(--linha); color: var(--cinza); }
img { max-width: 100%; display: block; margin: 8pt auto 12pt; }
hr { border: none; border-top: 0.75pt solid var(--linha); margin: 14pt 0; }
.capitulo { break-before: page; }
.capa { height: 245mm; display: flex; flex-direction: column; justify-content: center; }
.capa .faixa { width: 40mm; height: 3pt; background: var(--magenta); margin-bottom: 16pt; }
.capa h1 { border: none; font-size: 30pt; font-weight: 300; margin: 0 0 6pt; padding: 0; }
.capa .sub { font-size: 14pt; color: var(--cinza); margin-bottom: 40pt; }
.capa dl { display: grid; grid-template-columns: 34mm 1fr; row-gap: 5pt; font-size: 10.5pt; margin: 0; }
.capa dt { color: var(--cinza); }
.capa dd { margin: 0; }
.sumario { break-before: page; }
.sumario ol { list-style: none; padding: 0; }
.sumario > ol > li { margin: 7pt 0; font-weight: 600; }
.sumario li li { font-weight: 400; font-size: 9.5pt; margin: 1.5pt 0 1.5pt 14pt; color: var(--cinza); }
.sumario a { color: inherit; }
"""

RODAPE = """
<div style="font-family: Arial, sans-serif; font-size: 7.5pt; color: #5A6178; width: 100%;
            padding: 0 18mm; display: flex; justify-content: space-between;">
  <span>Agente de Atendimento — Empório da Música · Júlia Félix Giannandrea</span>
  <span><span class="pageNumber"></span> / <span class="totalPages"></span></span>
</div>
"""


def _slug(texto: str) -> str:
    texto = re.sub(r"<[^>]+>", "", texto).lower()
    texto = re.sub(r"[^\w\s-]", "", texto)
    return re.sub(r"[\s_]+", "-", texto).strip("-")


def _sem_frontmatter(texto: str) -> str:
    if texto.startswith("---\n"):
        fim = texto.find("\n---", 4)
        if fim != -1:
            return texto[fim + 4:].lstrip("\n")
    return texto


def _corrige_links(corpo: str, origem: Path, ancoras: dict[Path, str], repo: str | None) -> str:
    """Links para documentos que estão no PDF viram âncoras internas; imagens viram
    caminhos absolutos; os demais links relativos apontam para o GitHub (--repo) ou
    viram texto."""

    def imagem(m: re.Match) -> str:
        src = m.group(2)
        if re.match(r"^[a-z]+:", src):
            return m.group(0)
        return f'{m.group(1)}src="{(origem.parent / src).resolve().as_uri()}"'

    def link(m: re.Match) -> str:
        href, texto = m.group(1), m.group(2)
        if re.match(r"^(https?:|mailto:|#)", href):
            return m.group(0)
        alvo = (origem.parent / href.split("#")[0]).resolve()
        if alvo in ancoras:
            return f'<a href="#{ancoras[alvo]}">{texto}</a>'
        if repo:
            caminho = alvo.relative_to(RAIZ).as_posix()
            tipo = "tree" if alvo.is_dir() else "blob"
            return f'<a href="{repo.rstrip("/")}/{tipo}/main/{caminho}">{texto}</a>'
        return texto

    corpo = re.sub(r'(<img [^>]*?)src="([^"]+)"', imagem, corpo)
    return re.sub(r'<a href="([^"]+)">(.*?)</a>', link, corpo, flags=re.S)


def montar_html(repo: str | None, capitulos_md: list[tuple[str, str]], descricao: str) -> str:
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    ancoras = {(RAIZ / arquivo).resolve(): f"cap-{i}" for i, (arquivo, _) in enumerate(capitulos_md, 1)}

    capitulos, sumario = [], []
    for i, (arquivo, titulo) in enumerate(capitulos_md, 1):
        origem = RAIZ / arquivo
        texto = _sem_frontmatter(origem.read_text(encoding="utf-8"))
        texto = re.sub(r"^# .*\n", "", texto, count=1)          # o título vem da lista de capítulos
        corpo = md.render(texto)

        secoes = []

        def ancora_h2(m: re.Match, i=i, secoes=secoes) -> str:
            ident = f"cap-{i}-{_slug(m.group(1))}"
            secoes.append((ident, re.sub(r"<[^>]+>", "", m.group(1))))
            return f'<h2 id="{ident}">{m.group(1)}</h2>'

        corpo = re.sub(r"<h2>(.*?)</h2>", ancora_h2, corpo)
        corpo = _corrige_links(corpo, origem, ancoras, repo)
        capitulos.append(f'<section class="capitulo"><h1 id="cap-{i}">{html.escape(titulo)}</h1>{corpo}</section>')

        itens = "".join(f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in secoes)
        sub = f"<ol>{itens}</ol>" if itens and not titulo.startswith("Anexo") and arquivo != "docs/decisoes.md" else ""
        sumario.append(f'<li><a href="#cap-{i}">{html.escape(titulo)}</a>{sub}</li>')

    repo_html = f'<a href="{html.escape(repo)}">{html.escape(repo)}</a>' if repo else "—"
    capa = f"""
<section class="capa">
  <div class="faixa"></div>
  <h1>Agente de Atendimento<br>Empório da Música</h1>
  <div class="sub">Desafio técnico · AI Engineer · Artefact</div>
  <dl>
    <dt>Autora</dt><dd>Júlia Félix Giannandrea</dd>
    <dt>Repositório</dt><dd>{repo_html}</dd>
    <dt>Conteúdo</dt><dd>{html.escape(descricao)}</dd>
    <dt>Gerado em</dt><dd>{date.today():%d/%m/%Y}</dd>
  </dl>
</section>
<section class="sumario"><h1>Sumário</h1><ol>{''.join(sumario)}</ol></section>
"""
    return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            f"<style>{CSS}</style></head><body>{capa}{''.join(capitulos)}</body></html>")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", default=REPO_PADRAO, help="URL do repositório no GitHub, para links e capa")
    args = parser.parse_args()

    pagina_html = RAIZ / "docs" / ".documentacao.html"
    try:
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            for saida, (capitulos_md, descricao) in VERSOES.items():
                pagina_html.write_text(montar_html(args.repo or None, capitulos_md, descricao), encoding="utf-8")
                pagina = navegador.new_page()
                pagina.goto(pagina_html.as_uri(), wait_until="networkidle")
                pagina.pdf(path=str(RAIZ / saida), format="A4", print_background=True,
                           display_header_footer=True, header_template="<span></span>",
                           footer_template=RODAPE,
                           margin={"top": "18mm", "bottom": "20mm", "left": "18mm", "right": "18mm"})
                pagina.close()
                print(f"PDF gerado em {saida}")
            navegador.close()
    finally:
        pagina_html.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
