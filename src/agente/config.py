"""Configuração do agente lida do .env e construção do modelo.

O restante do código usa apenas `build_model()` e `settings`, sem saber qual
provedor está por trás (ver docs/decisoes.md, D02).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

PROVIDERS = ("anthropic", "openrouter")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class ConfigError(RuntimeError):
    """Configuração ausente ou inválida no .env."""


@dataclass(frozen=True)
class Settings:
    provider: str
    model_id: str
    temperature: float
    max_tokens: int
    db_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        provider = os.getenv("PROVIDER", "").strip().lower()
        if provider not in PROVIDERS:
            raise ConfigError(
                f"PROVIDER inválido: '{provider}'. Use um destes: {', '.join(PROVIDERS)}."
            )

        model_id = os.getenv("MODEL_ID", "").strip()
        if not model_id:
            raise ConfigError("MODEL_ID não definido no .env.")

        db_path = Path(os.getenv("DB_PATH", "data/emporio.db"))
        if not db_path.is_absolute():
            db_path = ROOT_DIR / db_path

        return cls(
            provider=provider,
            model_id=model_id,
            temperature=float(os.getenv("TEMPERATURE", "0.2")),
            max_tokens=int(os.getenv("MAX_TOKENS", "1024")),
            db_path=db_path,
        )


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"{name} não definida no .env.")
    return value


def build_model(settings: Settings | None = None):
    """Devolve o modelo do Strands correspondente ao PROVIDER do .env."""
    settings = settings or Settings.from_env()

    if settings.provider == "anthropic":
        from strands.models.anthropic import AnthropicModel

        return AnthropicModel(
            client_args={"api_key": _require_env("ANTHROPIC_API_KEY")},
            model_id=settings.model_id,
            max_tokens=settings.max_tokens,
            params={"temperature": settings.temperature},
        )

    if settings.provider == "openrouter":
        # O OpenRouter expõe uma API compatível com a da OpenAI.
        from strands.models.openai import OpenAIModel

        return OpenAIModel(
            client_args={
                "api_key": _require_env("OPENROUTER_API_KEY"),
                "base_url": OPENROUTER_BASE_URL,
            },
            model_id=settings.model_id,
            params={
                "temperature": settings.temperature,
                "max_tokens": settings.max_tokens,
            },
        )

    raise ConfigError(f"Provedor não suportado: {settings.provider}")
