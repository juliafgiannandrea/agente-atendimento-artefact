"""Regras de negócio (src/agente/regras.py), com os valores do manual e do eval set."""

from decimal import Decimal

import pytest

from agente import regras


# --- Disponibilidade (S04) ----------------------------------------------------

@pytest.mark.parametrize("status, estoque, esperado", [
    ("active", 5, "disponivel"),
    ("active", 0, "sem_estoque"),
    ("discontinued", 0, "descontinuado"),
    ("coming_soon", 2, "em_breve"),      # status prevalece sobre estoque
])
def test_disponibilidade(status, estoque, esperado):
    assert regras.disponibilidade(status, estoque) == esperado


def test_status_desconhecido_gera_erro():
    with pytest.raises(ValueError):
        regras.disponibilidade("esgotado", 0)


# --- Preços -------------------------------------------------------------------

def test_preco_promocional_arredonda_centavos():
    assert regras.preco_promocional(2399.0, 18) == Decimal("1967.18")
    assert regras.preco_promocional(359.0, None) == Decimal("359.00")


def test_pix_tem_5_por_cento_de_desconto():
    assert regras.preco_pix(2199.0, em_promocao=False) == Decimal("2089.05")


def test_pix_nao_acumula_com_promocao():
    assert regras.preco_pix(439.20, em_promocao=True) == Decimal("439.20")


# --- Conflito de promoções (S06) ----------------------------------------------

def test_uma_promocao_ativa_vale():
    promo = {"promotion_id": 1, "discount_percent": 10}
    assert regras.promocao_vigente([promo]) == promo


def test_duas_promocoes_ativas_nenhuma_vale():
    assert regras.promocao_vigente([{"promotion_id": 1}, {"promotion_id": 2}]) is None


def test_sem_promocao_ativa():
    assert regras.promocao_vigente([]) is None


# --- Parcelamento (S02: faixas da seção 3.1) ----------------------------------

@pytest.mark.parametrize("total, parcelas, permitido", [
    (1299.00, 12, True),    # 108,25 >= 100
    (323.10, 4, True),      # 80,78 >= 80
    (323.10, 5, False),     # 64,62 < 80
    (323.10, 6, False),
    (159.90, 3, True),      # até 3x não há mínimo de parcela
    (45.00, 2, False),      # abaixo de R$ 50 não parcela
    (45.00, 1, True),       # à vista sempre pode
    (1000.00, 13, False),   # máximo de 12x
])
def test_parcelamento_permitido(total, parcelas, permitido):
    assert regras.parcelamento_permitido(total, parcelas) is permitido


@pytest.mark.parametrize("total, maximo", [
    (1299.00, 12),
    (323.10, 4),     # caso parc-02 do eval set
    (799.90, 7),     # 8x daria 99,99 < 100
    (159.90, 3),
    (45.00, 1),
])
def test_max_parcelas(total, maximo):
    assert regras.max_parcelas(total) == maximo


# --- Forma de pagamento -------------------------------------------------------

@pytest.mark.parametrize("codigo, esperado", [
    ("pix", ("pix", 1)),
    ("boleto", ("boleto", 1)),
    ("debit", ("debit", 1)),
    ("credit_6x", ("credit", 6)),
    ("credit_12x", ("credit", 12)),
])
def test_interpreta_forma_pagamento(codigo, esperado):
    assert regras.interpreta_forma_pagamento(codigo) == esperado


def test_forma_pagamento_desconhecida():
    with pytest.raises(ValueError):
        regras.interpreta_forma_pagamento("cheque")
