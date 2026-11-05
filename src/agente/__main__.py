"""CLI do atendente da Empório da Música.

Uso (a partir da raiz do repositório, depois de `python -m etl.pipeline`):
    python -m agente                     conversa nova
    python -m agente --sessao maria      cria ou retoma a conversa "maria" (memória entre execuções)
    python -m agente --debug             mostra as ferramentas usadas e os avisos do Strands
    python -m agente --sem-verificacao   não testa a conexão com o modelo ao iniciar

Comandos durante a conversa:
    /exportar [arquivo.md]   salva a conversa em Markdown (padrão: exemplos/conversa_<data>.md)
    /sair                    encerra
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

from agente.config import ROOT_DIR, ConfigError, Settings
from agente.contexto import Contexto

EXEMPLOS_DIR = ROOT_DIR / "exemplos"


def limpa_markdown(texto: str) -> str:
    """Remove negrito/itálico e títulos que o modelo às vezes usa mesmo instruído a não usar:
    no terminal (e no WhatsApp) eles apareceriam como asteriscos."""
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto, flags=re.S)
    texto = re.sub(r"__(.+?)__", r"\1", texto, flags=re.S)
    texto = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", texto)
    return re.sub(r"^#{1,6}\s+", "", texto, flags=re.M)


def _exporta(historico: list[tuple[str, str, list[str]]], destino: Path, settings: Settings) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    linhas = [
        "# Conversa com o atendente da Empório da Música\n",
        f"- Modelo: `{settings.provider}` / `{settings.model_id}`",
        f"- Data de referência dos pedidos: {settings.reference_date:%d/%m/%Y}",
        f"- Exportada em: {datetime.now():%d/%m/%Y %H:%M}\n",
        "---\n",
    ]
    for cliente, resposta, ferramentas in historico:
        linhas.append(f"**Cliente:** {cliente}\n")
        if ferramentas:
            linhas.append(f"> Ferramentas usadas: {', '.join(f'`{f}`' for f in ferramentas)}\n")
        linhas.append(f"**Atendente:** {resposta}\n")
    destino.write_text("\n".join(linhas), encoding="utf-8")
    return destino


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atendente virtual da Empório da Música")
    parser.add_argument("--sessao", help="id da sessão para guardar e retomar a conversa")
    parser.add_argument("--debug", action="store_true", help="mostra as ferramentas usadas e os avisos")
    parser.add_argument("--sem-verificacao", action="store_true",
                        help="não testa a conexão com o modelo ao iniciar (economiza uma requisição)")
    args = parser.parse_args(argv)

    # Avisos internos do Strands (novas tentativas, conteúdo de raciocínio descartado)
    # só aparecem no modo debug; os erros relevantes são tratados abaixo.
    logging.getLogger("strands").setLevel(logging.WARNING if args.debug else logging.CRITICAL)

    try:
        settings = Settings.from_env()
        from agente.agente import Atendente, verificar_conexao   # importa o Strands só depois de validar o .env
        atendente = Atendente(Contexto.padrao(), session_id=args.sessao)
    except (ConfigError, FileNotFoundError) as exc:
        print(f"Erro de configuração: {exc}", file=sys.stderr)
        return 1

    print("Empório da Música — atendimento virtual")
    print(f"(modelo: {settings.provider}/{settings.model_id}; /exportar salva a conversa; /sair encerra)")

    if not args.sem_verificacao:
        print("Verificando a conexão com o modelo...", end=" ", flush=True)
        falha = verificar_conexao(atendente.agente.model)
        if falha is None:
            print("ok")
        else:
            categoria, mensagem = falha
            print("falhou")
            print(f"  {mensagem}", file=sys.stderr)
            if categoria != "limite":     # limite pode passar em instantes; o resto não
                return 1
    print()

    historico: list[tuple[str, str, list[str]]] = []
    while True:
        try:
            mensagem = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not mensagem:
            continue
        if mensagem == "/sair":
            break
        if mensagem.startswith("/exportar"):
            partes = mensagem.split(maxsplit=1)
            destino = (Path(partes[1]) if len(partes) > 1
                       else EXEMPLOS_DIR / f"conversa_{datetime.now():%Y%m%d_%H%M%S}.md")
            print(f"Conversa salva em {_exporta(historico, destino, settings)}\n")
            continue

        resposta = atendente.responder(mensagem)
        resposta.texto = limpa_markdown(resposta.texto)
        if args.debug and resposta.ferramentas:
            print(f"  [ferramentas: {', '.join(resposta.ferramentas)}]")
        if resposta.erro:
            print(f"  [aviso: {resposta.erro}]", file=sys.stderr)
        print(f"Empório: {resposta.texto}\n")
        historico.append((mensagem, resposta.texto, resposta.ferramentas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
