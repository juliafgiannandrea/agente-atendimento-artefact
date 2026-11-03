"""Tools buscar_produtos e consultar_produto (casos do eval set)."""


def _nomes(resultado, chave="produtos"):
    return [p["nome"] for p in resultado[chave]]


def test_violoes_ate_1000(tools):
    """enun-01: 12 violões disponíveis até R$ 1.000, sem o sem estoque e o descontinuado."""
    r = tools["buscar_produtos"](categoria="Violões", preco_max=1000)
    assert r["total_encontrado"] == r["exibidos"] == 12
    assert "Giannini GF-3D Dreadnought Sunburst" not in _nomes(r)
    assert "Shelby SN-7C 7 Cordas Nylon Natural" not in _nomes(r)
    assert r["produtos"][0] == {
        "product_id": 83, "nome": "Tagima Memphis AC-39 Nylon Natural", "categoria": "Violões",
        "disponibilidade": "Disponível", "pode_ser_vendido": True, "preco": "R$ 429,90"}


def test_categoria_sem_acento_e_texto(tools):
    r = tools["buscar_produtos"](categoria="violoes", texto="7 cordas nylon")
    assert _nomes(r) == ["Giannini GWNE-7 7 Cordas Nylon Natural", "Rozini RV-174 7 Cordas Nylon Natural"]


def test_promocoes_ativas_com_preco_original(tools):
    """promo-03: as 4 promoções ativas, com preço original e percentual."""
    r = tools["buscar_produtos"](apenas_promocao=True)
    assert r["total_encontrado"] == 4
    kalani = next(p for p in r["produtos"] if p["product_id"] == 127)
    assert kalani["promocao"] == {"nome": "Oferta Especial", "preco_original": "R$ 359,00",
                                  "desconto_percentual": 10, "preco_promocional": "R$ 323,10"}


def test_categoria_sem_produtos(tools):
    """estq-04: sopro existe como categoria, mas não tem produtos."""
    r = tools["buscar_produtos"](categoria="sopro", apenas_disponiveis=False)
    assert r["total_encontrado"] == 0
    assert "Não invente" in r["observacao"]


def test_limite_maximo(tools):
    r = tools["buscar_produtos"](apenas_disponiveis=False, limite=500)
    assert r["total_encontrado"] == 65 and r["exibidos"] == 30


def test_consultar_produto_nome_parcial(tools):
    """enun-03: "Takamine GD20" encontra o produto; promoção de 12% está inativa."""
    p = tools["consultar_produto"]("Takamine GD20")["produto"]
    assert (p["nome"], p["preco"], p["preco_no_pix"]) == (
        "Takamine GD20 Dreadnought Natural", "R$ 2.199,00", "R$ 2.089,05")
    assert "promocao" not in p
    assert p["parcelamento_maximo"] == "12x de R$ 183,25 sem juros"


def test_consultar_produto_em_promocao_sem_pix(tools):
    """promo-04 e parc-02: PIX não acumula; KAL-700T vai até 4x de R$ 80,78."""
    p = tools["consultar_produto"]("Kalani KAL-700T")["produto"]
    assert p["preco_no_pix"] == "R$ 323,10"
    assert p["parcelamento_maximo"] == "4x de R$ 80,78 sem juros"


def test_sem_estoque_sugere_dreadnoughts(tools):
    """estq-01."""
    r = tools["consultar_produto"]("Giannini GF-3D")
    assert r["produto"]["disponibilidade"] == "Temporariamente indisponível"
    assert _nomes(r, "alternativas_disponiveis")[:2] == [
        "Tagima Woodstock Dreadnought Natural", "Yamaha FG800 Dreadnought Natural"]


def test_descontinuado_sugere_7_cordas_nylon(tools):
    """estq-02."""
    r = tools["consultar_produto"]("Shelby SN-7C")
    assert r["produto"]["disponibilidade"] == "Descontinuado"
    assert _nomes(r, "alternativas_disponiveis")[:2] == [
        "Giannini GWNE-7 7 Cordas Nylon Natural", "Rozini RV-174 7 Cordas Nylon Natural"]


def test_em_breve_nao_e_vendavel_mesmo_com_estoque(tools):
    """estq-03."""
    r = tools["consultar_produto"]("Kala KA-ABP-CTG")
    assert r["produto"]["pode_ser_vendido"] is False
    assert r["produto"]["disponibilidade"] == "Em breve"
    assert "Kala KA-B Barítono Mogno" in _nomes(r, "alternativas_disponiveis")


def test_nome_ambiguo_lista_candidatos(tools):
    r = tools["consultar_produto"]("Kala barítono")
    assert r["encontrado"] is False
    assert len(r["candidatos"]) == 2


def test_nome_com_erro_de_digitacao_sugere(tools):
    r = tools["consultar_produto"]("takamini gd 20")
    assert r["encontrado"] is False
    assert r["sugestoes"][0]["nome"] == "Takamine GD20 Dreadnought Natural"
