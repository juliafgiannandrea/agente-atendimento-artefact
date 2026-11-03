"""Montagem do agente (Strands) e o atendente usado pelo CLI.

Memória da conversa:
    - durante a sessão: o histórico de mensagens do Strands, com janela
      deslizante (SlidingWindowConversationManager) para não estourar o contexto;
    - entre execuções (opcional): FileSessionManager grava o histórico em
      data/sessoes/, e `--sessao <id>` retoma a conversa.

Falhas do provedor (chave inválida, modelo indisponível, limite de requisições)
são classificadas para dar mensagens claras: ao cliente, sem detalhe técnico;
a quem opera o CLI, com o motivo e o que fazer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from strands import Agent, ModelRetryStrategy
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.session.file_session_manager import FileSessionManager
from strands.types.exceptions import ModelThrottledException

from agente.config import ROOT_DIR, build_model
from agente.contexto import Contexto
from agente.prompt import montar_prompt
from agente.tools import criar_ferramentas

SESSOES_DIR = ROOT_DIR / "data" / "sessoes"
JANELA_MENSAGENS = 40          # mensagens mantidas no contexto do modelo
MAX_CARACTERES_MENSAGEM = 2000  # guardrail de entrada

# Novas tentativas em caso de limite de requisições: 3 tentativas, esperas de 2 e 2 s.
# O padrão do Strands (6 tentativas, até ~1 min de espera) deixava o terminal parado.
TENTATIVAS_MODELO = 3
ESPERA_INICIAL_S = 2
ESPERA_MAXIMA_S = 8

MSG_LONGA = ("Sua mensagem ficou um pouco longa para eu processar de uma vez. "
             "Pode resumir em poucas frases?")
MSG_ERRO = ("Tive um problema técnico agora e não consegui responder. "
            "Pode tentar de novo em instantes? Se preferir, fale com a equipe pelo "
            "WhatsApp (67) 3321-4500.")
MSG_LIMITE = ("Estou com muitas conversas ao mesmo tempo agora. Pode tentar de novo "
              "em um minutinho? Se preferir, fale com a equipe pelo WhatsApp (67) 3321-4500.")

# Diagnóstico para quem opera o CLI, por código HTTP do provedor
DIAGNOSTICOS = {
    401: ("chave", "Chave de API inválida ou ausente. Confira ANTHROPIC_API_KEY ou OPENROUTER_API_KEY no .env."),
    402: ("creditos", "Sem créditos no provedor. Adicione créditos ou troque de provedor/modelo."),
    403: ("permissao", "O provedor recusou este modelo para a sua conta ou aplicação. Troque o MODEL_ID no .env."),
    404: ("modelo", "Modelo não encontrado. Confira o MODEL_ID no .env."),
}
DIAGNOSTICO_LIMITE = ("limite", "Limite de requisições atingido no provedor. Espere alguns minutos, "
                                "troque de modelo ou adicione créditos.")
DIAGNOSTICO_CONEXAO = ("conexao", "Não foi possível conectar ao provedor. Verifique a internet "
                                  "ou se o endereço do provedor está acessível.")
ERROS_DE_CONEXAO = {"APIConnectionError", "APITimeoutError", "ConnectError", "ConnectTimeout"}


def diagnostica(exc: BaseException) -> tuple[str, str]:
    """Classifica uma falha do modelo em (categoria, mensagem para quem opera o CLI)."""
    atual: BaseException | None = exc
    while atual is not None:
        if isinstance(atual, ModelThrottledException):
            return DIAGNOSTICO_LIMITE
        status = getattr(atual, "status_code", None)
        if status == 429:
            return DIAGNOSTICO_LIMITE
        if status in DIAGNOSTICOS:
            return DIAGNOSTICOS[status]
        if type(atual).__name__ in ERROS_DE_CONEXAO:
            return DIAGNOSTICO_CONEXAO
        atual = atual.__cause__ or atual.__context__
    return "outro", f"Erro inesperado do provedor: {type(exc).__name__}: {exc}"


def estrategia_de_tentativas() -> ModelRetryStrategy:
    return ModelRetryStrategy(max_attempts=TENTATIVAS_MODELO, initial_delay=ESPERA_INICIAL_S,
                              max_delay=ESPERA_MAXIMA_S)


def criar_agente(ctx: Contexto, model=None, session_id: str | None = None,
                 sessoes_dir: Path = SESSOES_DIR,
                 retry_strategy: ModelRetryStrategy | None = None) -> Agent:
    kwargs = {}
    if session_id:
        sessoes_dir.mkdir(parents=True, exist_ok=True)
        kwargs["session_manager"] = FileSessionManager(session_id=session_id, storage_dir=str(sessoes_dir))
    return Agent(
        model=model or build_model(),
        system_prompt=montar_prompt(ctx),
        tools=criar_ferramentas(ctx),
        conversation_manager=SlidingWindowConversationManager(window_size=JANELA_MENSAGENS),
        callback_handler=None,          # o CLI imprime só a resposta final
        agent_id="atendente",
        retry_strategy=retry_strategy or estrategia_de_tentativas(),
        **kwargs,
    )


def verificar_conexao(model, retry_strategy: ModelRetryStrategy | None = None) -> tuple[str, str] | None:
    """Faz uma chamada mínima ao modelo, sem tools. Devolve None se funcionou, ou o
    diagnóstico (categoria, mensagem) se falhou. Gasta uma requisição do provedor."""
    teste = Agent(model=model, callback_handler=None, system_prompt="Responda apenas: ok",
                  retry_strategy=retry_strategy or estrategia_de_tentativas())
    try:
        teste("ok")
    except Exception as exc:  # noqa: BLE001
        return diagnostica(exc)
    return None


@dataclass
class Resposta:
    texto: str
    ferramentas: list[str] = field(default_factory=list)
    erro: str | None = None


def _ferramentas_usadas(mensagens: list[dict]) -> list[str]:
    return [bloco["toolUse"]["name"]
            for m in mensagens if m.get("role") == "assistant"
            for bloco in m.get("content", []) if "toolUse" in bloco]


class Atendente:
    """Uma conversa com um cliente: agente + contexto + guardrails de entrada."""

    def __init__(self, ctx: Contexto | None = None, model=None, session_id: str | None = None,
                 sessoes_dir: Path = SESSOES_DIR, retry_strategy: ModelRetryStrategy | None = None):
        self.ctx = ctx or Contexto.padrao()
        self.agente = criar_agente(self.ctx, model=model, session_id=session_id,
                                   sessoes_dir=sessoes_dir, retry_strategy=retry_strategy)

    def responder(self, mensagem: str) -> Resposta:
        mensagem = mensagem.strip()
        if len(mensagem) > MAX_CARACTERES_MENSAGEM:
            return Resposta(MSG_LONGA)

        self.ctx.estado.novo_turno()
        inicio = len(self.agente.messages)
        try:
            resultado = self.agente(mensagem)
        except Exception as exc:  # noqa: BLE001 (o cliente nunca vê o stack trace)
            categoria, diagnostico = diagnostica(exc)
            texto = MSG_LIMITE if categoria == "limite" else MSG_ERRO
            return Resposta(texto, erro=diagnostico)
        return Resposta(str(resultado).strip(), _ferramentas_usadas(self.agente.messages[inicio:]))
