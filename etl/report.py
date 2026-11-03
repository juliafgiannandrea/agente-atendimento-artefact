"""Gera docs/data_quality.md a partir das tabelas dq_results e etl_metadata.

O relatório não contém horário de execução: a mesma entrada gera exatamente
o mesmo arquivo, então o diff no Git só muda quando os dados ou as regras
mudam. O horário fica em etl_metadata, no banco.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

CABECALHO = """# Relatório de qualidade de dados

> Gerado automaticamente por `python -m etl.pipeline` (`etl/report.py`). Não edite à mão:
> as alterações são sobrescritas na próxima execução.

Inconsistências são **sinalizadas, não corrigidas em silêncio** (ver `docs/decisoes.md`, D09):
o valor original é mantido, e a flag e o tratamento adotado ficam registrados abaixo.
"""


def _celula(valor) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, (list, dict)):
        valor = json.dumps(valor, ensure_ascii=False)
    return str(valor).replace("|", "\\|")


def _tabela_md(registros: list[dict]) -> str:
    colunas = list(dict.fromkeys(k for r in registros for k in r))
    linhas = ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    linhas += ["| " + " | ".join(_celula(r.get(c)) for c in colunas) + " |" for r in registros]
    return "\n".join(linhas)


def gera(db_path: Path, report_path: Path) -> str:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        meta = {r["chave"]: r["valor"] for r in conn.execute("SELECT chave, valor FROM etl_metadata")}
        resultados = [dict(r) for r in conn.execute(
            "SELECT * FROM dq_results ORDER BY severidade DESC, check_id")]
    finally:
        conn.close()

    contagens = json.loads(meta["contagens"])
    hashes = json.loads(meta["hashes_origem"])
    erros = [r for r in resultados if r["severidade"] == "erro"]
    alertas = [r for r in resultados if r["severidade"] == "alerta"]
    alertas_falhos = [r for r in alertas if r["resultado"] == "falhou"]

    partes = [CABECALHO]

    partes.append("## Execução\n")
    partes.append(f"- **Data de referência (S01):** {meta['reference_date']}")
    partes.append(f"- **Verificações de erro:** {len(erros)} executadas, "
                  f"{sum(r['resultado'] == 'falhou' for r in erros)} com falha")
    partes.append(f"- **Verificações de alerta:** {len(alertas)} executadas, "
                  f"{len(alertas_falhos)} com ocorrências\n")

    partes.append("### Linhas carregadas na camada silver\n")
    partes.append(_tabela_md([{"tabela": t, "linhas": n} for t, n in contagens.items()]) + "\n")

    partes.append("### Arquivos de origem (SHA-256)\n")
    partes.append(_tabela_md([{"arquivo": a, "sha256": f"`{h[:16]}…`"} for a, h in hashes.items()]) + "\n")

    partes.append("## Resumo das verificações\n")
    partes.append(_tabela_md([
        {"id": r["check_id"], "severidade": r["severidade"],
         "resultado": "⚠️ ocorrências" if r["resultado"] == "falhou" and r["severidade"] == "alerta"
                      else "❌ falhou" if r["resultado"] == "falhou" else "✅ ok",
         "tabela": r["tabela"], "verificação": r["descricao"], "qtd": r["quantidade"]}
        for r in resultados
    ]) + "\n")

    partes.append("## Detalhe dos alertas\n")
    if not alertas_falhos:
        partes.append("Nenhum alerta com ocorrências.\n")
    for r in alertas_falhos:
        partes.append(f"### {r['check_id']} — {r['descricao']}\n")
        partes.append(f"**Tratamento:** {r['tratamento']}\n")
        partes.append(_tabela_md(json.loads(r["registros"])) + "\n")

    conteudo = "\n".join(partes).rstrip() + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(conteudo, encoding="utf-8")
    return conteudo
