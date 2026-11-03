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


# --- Formatação ----------------------------------------------------------------

def formata_brl(valor: float | Decimal | None) -> str | None:
    """1299.0 -> 'R$ 1.299,00' (formato brasileiro, para o agente não reformatar)."""
    if valor is None:
        return None
    inteiro, centavos = f"{arredonda(valor):.2f}".split(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    return f"R$ {inteiro},{centavos}"


# --- Horário de funcionamento (manual, seção 2) --------------------------------

# weekday(): 0 = segunda ... 6 = domingo. None = fechado.
HORARIO_FUNCIONAMENTO: dict[int, tuple[str, str] | None] = {
    0: ("09:00", "18:00"),
    1: ("09:00", "18:00"),
    2: ("09:00", "18:00"),
    3: ("09:00", "18:00"),
    4: ("09:00", "18:00"),
    5: ("09:00", "13:00"),
    6: None,
}

DIAS_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
               "sexta-feira", "sábado", "domingo")


# --- Prazos de pós-venda (manual, seções 4 e 8) -------------------------------

PRAZO_ARREPENDIMENTO_DIAS = 7       # 4.1: corridos, após o recebimento
PRAZO_TROCA_DEFEITO_DIAS = 30       # 4.2: corridos, após a compra
PRAZO_GARANTIA_LEGAL_DIAS = 90      # 8.1: a partir do recebimento


def _prazo(inicio, dias: int, referencia) -> dict:
    from datetime import timedelta
    limite = inicio + timedelta(days=dias)
    return {
        "conta_a_partir_de": inicio.isoformat(),
        "valido_ate": limite.isoformat(),
        "dentro_do_prazo": referencia <= limite,
        "dias_restantes": max((limite - referencia).days, 0),
    }


def prazos_pedido(status: str, data_pedido, previsao_entrega, referencia) -> dict:
    """Prazos de pós-venda de um pedido na data de referência.

    O sistema só registra a previsão de entrega; para pedidos entregues ela é
    usada como data de recebimento estimada (o agente avisa o cliente).
    Datas como `datetime.date`.
    """
    resultado: dict = {"data_referencia": referencia.isoformat()}

    if status == "shipped" and previsao_entrega is not None:
        atraso = (referencia - previsao_entrega).days
        resultado["entrega"] = {
            "previsao": previsao_entrega.isoformat(),
            "atrasado": atraso > 0,
            "dias_de_atraso": max(atraso, 0),
        }

    if status != "delivered":
        resultado["observacao"] = (
            "Prazos de devolução, troca e garantia só começam a contar após a entrega."
            if status != "cancelled" else "Pedido cancelado: não há prazos de pós-venda."
        )
        return resultado

    recebimento = previsao_entrega or data_pedido
    resultado["recebimento_estimado"] = recebimento.isoformat()
    resultado["aviso"] = ("A data de recebimento é estimada pela previsão de entrega; "
                          "o sistema não registra a data real.")
    resultado["arrependimento_compra_online"] = _prazo(recebimento, PRAZO_ARREPENDIMENTO_DIAS, referencia)
    resultado["troca_por_defeito"] = _prazo(data_pedido, PRAZO_TROCA_DEFEITO_DIAS, referencia)
    resultado["garantia_legal"] = _prazo(recebimento, PRAZO_GARANTIA_LEGAL_DIAS, referencia)
    return resultado
