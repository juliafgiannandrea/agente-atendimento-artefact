"""Testes da base de conhecimento (kb/): estrutura, índice e fidelidade ao manual."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from agente.config import ROOT_DIR
from etl import extrair_politicas

KB_DIR = ROOT_DIR / "kb"
POLITICAS = sorted((KB_DIR / "politicas").glob("*.md"))
CAMPOS_OBRIGATORIOS = {"id", "titulo", "secao_manual", "paginas", "publico",
                       "quando_consultar", "versao_manual", "revisao_humana"}

# Valores verificáveis: dinheiro, percentuais, telefones, horários, prazos, leis, e-mails
PADROES_FATOS = [
    r"R\$ \d{1,3}(?:\.\d{3})*,\d{2}",
    r"\d+%",
    r"\(\d{2}\) \d{4}-\d{4}",
    r"\d{2}:\d{2}",
    r"\d+ \(\w+\) dias",
    r"\d+ a \d+ dias úteis",
    r"\d+ (?:dias|horas) úteis",
    r"\d+ meses a \d+ anos",
    r"\d{1,3}(?:\.\d{3})*/\d{2,4}",          # leis e CNPJ
    r"\d{5}-\d{3}",                          # CEP
    r"[\w.]+@[\w.]+",
]


def _frontmatter(caminho: Path) -> tuple[dict, str]:
    texto = caminho.read_text(encoding="utf-8")
    _, cabecalho, corpo = texto.split("---", 2)
    return yaml.safe_load(cabecalho), corpo


def _sem_notas_de_curadoria(corpo: str) -> str:
    """Remove os blocos '> Nota de curadoria', que não fazem parte do manual."""
    return "\n".join(l for l in corpo.splitlines() if not l.startswith(">"))


@pytest.fixture(scope="module")
def manual() -> str:
    """Texto do PDF extraído na hora, com espaços normalizados."""
    return re.sub(r"\s+", " ", extrair_politicas.extrai())


# --- Estrutura ----------------------------------------------------------------

def test_existem_as_nove_secoes():
    assert len(POLITICAS) == 9


@pytest.mark.parametrize("caminho", POLITICAS, ids=lambda p: p.name)
def test_frontmatter_completo(caminho):
    meta, corpo = _frontmatter(caminho)
    assert CAMPOS_OBRIGATORIOS <= set(meta)
    assert meta["publico"] in {"cliente", "interno"}
    assert meta["revisao_humana"] in {"pendente", "aprovada"}
    assert meta["quando_consultar"].startswith("Use quando ")
    assert corpo.strip().startswith("# ")


def test_ids_unicos():
    ids = [_frontmatter(p)[0]["id"] for p in POLITICAS]
    assert len(ids) == len(set(ids))


def test_indice_cobre_todas_as_secoes():
    indice = (KB_DIR / "index.md").read_text(encoding="utf-8")
    for caminho in POLITICAS:
        meta, _ = _frontmatter(caminho)
        assert f"`{meta['id']}`" in indice
        assert f"`politicas/{caminho.name}`" in indice


def test_arquivos_citados_no_indice_existem():
    indice = (KB_DIR / "index.md").read_text(encoding="utf-8")
    for citado in re.findall(r"`((?:politicas|_fonte)/[\w./-]+\.md)`", indice):
        assert (KB_DIR / citado).exists(), citado


def test_extracao_versionada_esta_atualizada():
    """kb/_fonte/manual_extraido.md precisa corresponder ao PDF atual."""
    versionado = (KB_DIR / "_fonte" / "manual_extraido.md").read_text(encoding="utf-8")
    assert versionado == extrair_politicas.extrai()


# --- Fidelidade ao manual -----------------------------------------------------

@pytest.mark.parametrize("caminho", POLITICAS, ids=lambda p: p.name)
def test_valores_citados_existem_no_manual(caminho, manual):
    """Todo valor citado numa seção (fora das notas de curadoria) está no PDF."""
    _, corpo = _frontmatter(caminho)
    texto = re.sub(r"\s+", " ", _sem_notas_de_curadoria(corpo)).replace("**", "")
    fatos = {f for padrao in PADROES_FATOS for f in re.findall(padrao, texto)}
    ausentes = sorted(f for f in fatos if f not in manual)
    assert not ausentes, f"Valores que não estão no manual: {ausentes}"


def test_contatos_seguem_as_decisoes():
    _, corpo = _frontmatter(KB_DIR / "politicas" / "01-sobre-a-loja.md")
    assert "| WhatsApp | (67) 3321-4500 |" in corpo                     # S03
    assert "| Telefone | (67) 3341-4444 |" in corpo                     # S03
    assert "| E-mail | contato@emporiodamusica.com.br |" in corpo       # S07


def test_parcelamento_segue_secao_3_1():
    _, corpo = _frontmatter(KB_DIR / "politicas" / "03-formas-de-pagamento.md")
    tabela = _sem_notas_de_curadoria(corpo)
    assert "| 4x a 6x | Sem juros | R$ 80,00 |" in tabela                # S02
    assert "Parcela mínima de R$ 100,00" not in tabela


# --- Persona e pendências -----------------------------------------------------

def test_soul_cobre_diretrizes_da_secao_7_1():
    soul = (KB_DIR / "soul.md").read_text(encoding="utf-8").lower()
    for trecho in ["informal, mas profissional", "amigo que entende de música",
                   "exclusivamente com instrumentos musicais", "propaganda enganosa",
                   "informe quando ela retorna"]:
        assert trecho in soul


def test_pendencias_registram_as_tres_contradicoes():
    pendencias = (KB_DIR / "pendencias_gerencia.md").read_text(encoding="utf-8")
    for item in ["(67) 3321-4500", "(67) 3341-4444", "contato@empóriodamusica.com.br",
                 "Parcela mínima de R$ 100,00"]:
        assert item in pendencias


# --- Leitura pelo agente (src/agente/kb.py) -----------------------------------

from agente import kb  # noqa: E402

REFERENCIAS_INTERNAS = [
    r"Nota de curadoria", r"docs/", r"kb/", r"\bS0\d\b", r"\bP\d\b", r"\bL\d{1,2}\b",
    r"\bA\d{2}\b", r"\bETL\b", r"data_quality", r"pendencias",
]


def test_agente_le_todas_as_secoes_do_indice():
    assert set(kb.secoes()) == {_frontmatter(p)[0]["id"] for p in POLITICAS}
    indice = kb.indice_para_agente()
    for secao in kb.secoes().values():
        assert f"`{secao.id}`" in indice
        assert secao.quando_consultar in indice


@pytest.mark.parametrize("secao_id", sorted(kb.secoes()))
def test_secao_entregue_ao_agente_nao_tem_referencias_internas(secao_id):
    texto = kb.ler_secao(secao_id)
    assert not texto.startswith("---")                      # sem cabeçalho YAML
    encontradas = [p for p in REFERENCIAS_INTERNAS if re.search(p, texto)]
    assert not encontradas, f"Referências internas no texto do agente: {encontradas}"


@pytest.mark.parametrize("secao_id", sorted(kb.secoes()))
def test_secao_mantem_orientacoes_ao_assistente(secao_id):
    bruto = kb.secoes()[secao_id].caminho.read_text(encoding="utf-8")
    texto = kb.ler_secao(secao_id)
    assert texto.count("Orientação ao assistente") == bruto.count("Orientação ao assistente")


def test_persona_entregue_ao_agente_nao_tem_referencias_internas():
    persona = kb.ler_persona()
    assert persona.startswith("# Persona")
    assert not [p for p in REFERENCIAS_INTERNAS if re.search(p, persona)]


def test_remove_notas_de_curadoria_preserva_o_resto():
    texto = ("# Título\n\nTexto do manual.\n\n"
             "> **Orientação ao assistente:** faça X.\n\n"
             "> **Nota de curadoria:** ver S03.\n> continuação.\n\n"
             "Mais texto.\n")
    assert kb.remove_notas_de_curadoria(texto) == (
        "# Título\n\nTexto do manual.\n\n> **Orientação ao assistente:** faça X.\n\nMais texto.\n")


def test_secao_inexistente():
    with pytest.raises(KeyError, match="Disponíveis"):
        kb.ler_secao("cupons")
