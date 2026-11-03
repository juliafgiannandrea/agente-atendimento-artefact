"""Regras de negócio da Empório da Música, escritas uma única vez.

São usadas pelo ETL (verificações de qualidade e colunas calculadas) e pelas
tools do agente, para que a mesma regra nunca tenha duas implementações.
As referências entre parênteses apontam para o manual de políticas e para
docs/decisoes.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# --- Status de produto -------------------------------------------------------

STATUS_PRODUTO = ("active", "discontinued", "coming_soon")

ROTULO_DISPONIBILIDADE = {
    "disponivel": "Disponível",
    "sem_estoque": "Temporariamente indisponível",
    "descontinuado": "Descontinuado",
    "em_breve": "Em breve",
}


def disponibilidade(status: str, estoque: int) -> str:
    """Classifica o produto para atendimento.

    O status prevalece sobre o estoque (S04): um produto `coming_soon` ou
    `discontinued` não é oferecido mesmo que `stock_quantity` > 0.
    """
    if status == "discontinued":
        return "descontinuado"
    if status == "coming_soon":
        return "em_breve"
    if status == "active":
        return "disponivel" if estoque > 0 else "sem_estoque"
    raise ValueError(f"Status de produto desconhecido: {status!r}")


def vendavel(status: str, estoque: int) -> bool:
    """Produto pode ser oferecido para compra agora (S04)."""
    return disponibilidade(status, estoque) == "disponivel"


# --- Preços ------------------------------------------------------------------

DESCONTO_PIX = Decimal("0.05")  # manual 3: 5% sobre o preço de tabela


def arredonda(valor: Decimal | float | int) -> Decimal:
    """Arredonda para centavos, meio para cima (padrão comercial)."""
    return Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def preco_promocional(preco: float, desconto_percentual: float | None) -> Decimal:
    """Preço com a promoção aplicada; sem promoção, devolve o preço de tabela."""
    if not desconto_percentual:
        return arredonda(preco)
    fator = 1 - Decimal(str(desconto_percentual)) / 100
    return arredonda(Decimal(str(preco)) * fator)


def preco_pix(preco: float, em_promocao: bool) -> Decimal:
    """Preço no PIX. O desconto de PIX não se aplica sobre preço promocional
    (manual 6.2: promoções não são cumulativas)."""
    if em_promocao:
        return arredonda(preco)
    return arredonda(Decimal(str(preco)) * (1 - DESCONTO_PIX))


def promocao_vigente(promocoes_ativas: list[dict]) -> dict | None:
    """Escolhe a promoção que vale para um produto (S06).

    Exatamente uma promoção ativa: ela vale. Duas ou mais: nenhuma vale (o
    produto fica com o preço de tabela) e o conflito é sinalizado pelo ETL.
    """
    if len(promocoes_ativas) == 1:
        return promocoes_ativas[0]
    return None


# --- Parcelamento (S02: faixas da seção 3.1 do manual) -----------------------

MAX_PARCELAS = 12
VALOR_MINIMO_PARCELAMENTO = Decimal("50.00")  # abaixo disso, só à vista


@dataclass(frozen=True)
class FaixaParcelamento:
    de: int
    ate: int
    parcela_minima: Decimal


FAIXAS_PARCELAMENTO = (
    FaixaParcelamento(1, 3, Decimal("0.00")),
    FaixaParcelamento(4, 6, Decimal("80.00")),
    FaixaParcelamento(7, 12, Decimal("100.00")),
)


def parcela_minima(parcelas: int) -> Decimal:
    """Valor mínimo de cada parcela para o número de parcelas informado."""
    for faixa in FAIXAS_PARCELAMENTO:
        if faixa.de <= parcelas <= faixa.ate:
            return faixa.parcela_minima
    raise ValueError(f"Número de parcelas fora do permitido (1 a {MAX_PARCELAS}): {parcelas}")


def valor_parcela(total: float | Decimal, parcelas: int) -> Decimal:
    return arredonda(Decimal(str(total)) / parcelas)


def parcelamento_permitido(total: float | Decimal, parcelas: int) -> bool:
    """Indica se o total pode ser dividido nesse número de parcelas sem juros."""
    total = Decimal(str(total))
    if parcelas == 1:
        return True
    if not 1 <= parcelas <= MAX_PARCELAS:
        return False
    if total < VALOR_MINIMO_PARCELAMENTO:
        return False
    return valor_parcela(total, parcelas) >= parcela_minima(parcelas)


def max_parcelas(total: float | Decimal) -> int:
    """Maior número de parcelas sem juros permitido para o total."""
    return max(n for n in range(1, MAX_PARCELAS + 1) if parcelamento_permitido(total, n))


# --- Formas de pagamento -----------------------------------------------------

LIMITE_COMBINACAO_PAGAMENTO = Decimal("2000.00")  # manual 3.1: PIX + cartão acima disso

FORMAS_PAGAMENTO = {
    "pix": "PIX",
    "debit": "Cartão de débito",
    "credit": "Cartão de crédito",
    "boleto": "Boleto bancário",
}


def interpreta_forma_pagamento(codigo: str) -> tuple[str, int]:
    """Converte o código da base em (forma, parcelas).

    Exemplos: 'pix' -> ('pix', 1); 'credit_6x' -> ('credit', 6).
    """
    codigo = codigo.strip().lower()
    if codigo.startswith("credit_") and codigo.endswith("x"):
        return "credit", int(codigo.removeprefix("credit_").removesuffix("x"))
    if codigo in FORMAS_PAGAMENTO:
        return codigo, 1
    raise ValueError(f"Forma de pagamento desconhecida: {codigo!r}")


# --- Status de pedido --------------------------------------------------------

STATUS_PEDIDO = {
    # A base não define os status; os rótulos abaixo são uma interpretação
    # neutra, sem prometer prazos (ver docs/decisoes.md).
    "pending": "Pedido recebido, aguardando processamento",
    "confirmed": "Pedido confirmado, em preparação para envio",
    "shipped": "Enviado",
    "delivered": "Entregue",
    "cancelled": "Cancelado",
}
