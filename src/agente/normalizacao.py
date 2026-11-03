"""Normalização de texto usada no ETL e nas tools.

O mesmo tratamento é aplicado aos dados (no ETL) e à entrada do cliente (nas
tools), para que "Takamine gd20" encontre "Takamine GD20 Dreadnought Natural"
e "(67) 99812-3456" confira com "67998123456".
"""

from __future__ import annotations

import re
import unicodedata


def normaliza_texto(texto: str) -> str:
    """Minúsculas, sem acento e com espaços simples."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def normaliza_email(email: str) -> str:
    return email.strip().lower()
