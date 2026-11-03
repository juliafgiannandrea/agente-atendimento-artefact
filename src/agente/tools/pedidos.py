"""Tool consultar_pedido, com verificação de identidade em código (decisão S05).

A verificação não depende do modelo: sem nome + telefone ou e-mail que
confiram com o titular, a tool não devolve nenhum dado do pedido, nem diz se
ele existe ou de quem é. Depois de MAX_FALHAS tentativas na mesma conversa, a
tool para de consultar (proteção contra tentativa e erro).
"""

from __future__ import annotations

import json
from datetime import date

from strands import tool

from agente import regras
from agente.contexto import Contexto
from agente.normalizacao import normaliza_email, normaliza_texto, so_digitos

MAX_FALHAS = 3

MSG_NAO_CONFERE = (
    "Não foi possível confirmar a identidade com os dados informados. Não revele se o "
    "pedido existe nem a quem pertence. Peça ao cliente para conferir o nome completo, "
    "o telefone ou e-mail do cadastro e o número do pedido."
)
MSG_BLOQUEIO = (
    "Limite de tentativas de identificação atingido nesta conversa. Não tente de novo: "
    "oriente o cliente a falar com a equipe pelo WhatsApp (67) 3321-4500 ou pelo "
    "e-mail contato@emporiodamusica.com.br."
)


def _nome_confere(informado: str, cadastrado_norm: str) -> bool:
    """Nome informado precisa ter ao menos nome e sobrenome, todos presentes no cadastro."""
    tokens = set(normaliza_texto(informado).split())
    return len(tokens) >= 2 and tokens <= set(cadastrado_norm.split())


def _contato_confere(informado: str, cliente) -> bool:
    if "@" in informado:
        return normaliza_email(informado) == cliente["email_norm"]
    digitos = so_digitos(informado)
    # Aceita com ou sem DDD, mas exige o número completo
    return len(digitos) >= 8 and cliente["phone_digits"].endswith(digitos) and len(digitos) in (8, 9, 10, 11)


def _data(valor: str | None) -> date | None:
    return date.fromisoformat(valor) if valor else None


def _formata_pedido(pedido, referencia: date) -> dict:
    itens = json.loads(pedido["itens"])
    return {
        "pedido_id": pedido["order_id"],
        "data_do_pedido": pedido["order_date"],
        "status": pedido["status_rotulo"],
        "valor_total": regras.formata_brl(pedido["total_brl"]),
        "forma_de_pagamento": (f"{pedido['forma_pagamento_rotulo']} em {pedido['parcelas']}x"
                               if pedido["parcelas"] > 1 else pedido["forma_pagamento_rotulo"]),
        "itens": [f"{i['quantidade']}x {i['nome']}" for i in itens],
        "codigo_rastreamento": pedido["tracking_code"],
        "previsao_entrega": pedido["estimated_delivery"],
        "observacao_do_pedido": pedido["notes"],
        "prazos": regras.prazos_pedido(
            pedido["status"], _data(pedido["order_date"]),
            _data(pedido["estimated_delivery"]), referencia),
    }


def criar(ctx: Contexto) -> list:

    @tool
    def consultar_pedido(nome_completo: str, telefone_ou_email: str, pedido_id: int | None = None) -> dict:
        """Consulta pedidos de um cliente: status, itens, valor, rastreio, previsão de entrega
        e prazos de devolução, troca e garantia já calculados.

        SEMPRE exige identificação: peça ao cliente o nome completo E o telefone ou e-mail
        do cadastro antes de chamar. Nunca chame com dados que o cliente não informou.
        Sem pedido_id, retorna todos os pedidos do cliente identificado.

        Args:
            nome_completo: Nome completo do cliente, como informado por ele.
            telefone_ou_email: Telefone (com DDD) ou e-mail do cadastro, como informado pelo cliente.
            pedido_id: Número do pedido, se o cliente informou.
        """
        estado = ctx.estado
        if estado.falhas_verificacao >= MAX_FALHAS:
            return {"verificado": False, "mensagem": MSG_BLOQUEIO}

        with ctx.conexao_leitura() as conn:
            if pedido_id is not None:
                dono = conn.execute(
                    "SELECT c.* FROM orders o JOIN customers c ON c.customer_id = o.customer_id "
                    "WHERE o.order_id = ?", (int(pedido_id),)).fetchone()
                candidatos = [dono] if dono else []
            else:
                candidatos = conn.execute("SELECT * FROM customers").fetchall()

            cliente = next((c for c in candidatos
                            if _nome_confere(nome_completo, c["name_norm"])
                            and _contato_confere(telefone_ou_email, c)), None)

            if cliente is None:
                estado.falhas_verificacao += 1
                restantes = MAX_FALHAS - estado.falhas_verificacao
                return {"verificado": False,
                        "mensagem": MSG_NAO_CONFERE if restantes > 0 else MSG_BLOQUEIO,
                        "tentativas_restantes": restantes}

            filtro, params = "customer_id = ?", [cliente["customer_id"]]
            if pedido_id is not None:
                filtro += " AND order_id = ?"
                params.append(int(pedido_id))
            pedidos = conn.execute(
                f"SELECT * FROM vw_pedidos WHERE {filtro} ORDER BY order_date DESC", params).fetchall()

        return {
            "verificado": True,
            "primeiro_nome_do_cliente": cliente["name"].split()[0],
            "pedidos": [_formata_pedido(p, ctx.reference_date) for p in pedidos],
            "observacao": None if pedidos else "Cliente identificado, mas sem pedidos cadastrados.",
        }

    return [consultar_pedido]
