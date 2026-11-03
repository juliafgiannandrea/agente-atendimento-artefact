"""Tool ler_politica."""


def test_le_secao_sem_notas_de_curadoria(tools):
    texto = tools["ler_politica"]("trocas-e-devolucoes")
    assert texto.startswith("# Trocas e devoluções")
    assert "7 (sete) dias corridos" in texto
    assert "Orientação ao assistente" in texto
    assert "Nota de curadoria" not in texto


def test_secao_inexistente_lista_disponiveis(tools):
    assert "Disponíveis" in tools["ler_politica"]("cupons")
