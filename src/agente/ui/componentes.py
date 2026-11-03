"""Cartões da UI montados a partir dos resultados das tools (ver docs/decisoes.md, D21).

O texto da resposta vem do modelo; os dados (preços, pedidos, prazos, trecho de
política) vêm do resultado das tools. Assim os cartões mostram exatamente o que
saiu do banco ou da base de políticas, e não há como o modelo "inventar" um.

As funções `html_*` são puras (recebem o resultado e devolvem HTML), para poderem
ser testadas sem Streamlit. Todo valor vindo dos dados passa por `escape`.
"""

from __future__ import annotations

import re
from datetime import date
from html import escape

import streamlit as st

from agente import kb
from agente.agente import ChamadaTool, Resposta

# Como cada tool aparece para o cliente no progresso (nada de nomes técnicos)
ROTULOS = {
    "planejar": "Planejando o atendimento",
    "buscar_produtos": "Buscando no catálogo",
    "consultar_produto": "Consultando o produto",
    "consultar_pedido": "Consultando o pedido",
    "ler_politica": "Lendo a política da loja",
    "hora_atual_loja": "Verificando o horário da loja",
    "registrar_reclamacao": "Registrando a reclamação",
    "entender_esquema": "Consultando o catálogo",
    "consultar_banco": "Consultando o catálogo",
}

ROTULOS_SPECS = {
    "top": "Tampo", "back_sides": "Fundo e laterais", "neck": "Braço", "strings": "Cordas",
    "scale": "Escala", "electronics": "Captação", "color": "Cor", "body": "Corpo",
    "shells": "Cascos", "pieces": "Peças", "hardware": "Ferragens", "keys": "Teclas",
    "type": "Tipo", "polyphony": "Polifonia",
}
VALORES_SPECS = {"yes": "sim", "no": "não", "steel": "aço", "included": "incluídas"}

ESTILO_STATUS = {
    "Entregue": "em-ok", "Enviado": "em-roxo", "Cancelado": "em-cinza",
}
ESTILO_DISPONIBILIDADE = {"Disponível": "em-ok"}


def _e(valor) -> str:
    return escape("" if valor is None else str(valor))


def _data_br(iso: str | None) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "—"


# ============================================================================
# Plano (checklist) e progresso
# ============================================================================

def estado_dos_passos(n_passos: int, concluidas: int, rodando: bool, finalizado: bool,
                      tem_faltantes: bool = False) -> list[str]:
    """Estado de cada passo do plano: "feito", "rodando" ou "pendente".

    O plano é texto livre do modelo, então não há vínculo exato entre tool e passo:
    cada tool concluída depois do plano marca o próximo passo. Ao final da resposta,
    tudo fica concluído, exceto quando o agente parou para pedir informações ao
    cliente: aí a própria resposta conclui só mais um passo (o de perguntar).
    """
    if finalizado:
        feitos = min(n_passos, concluidas + 1) if tem_faltantes else n_passos
    else:
        feitos = min(concluidas, max(n_passos - 1, 0))
    estados = []
    for i in range(n_passos):
        if i < feitos:
            estados.append("feito")
        elif i == feitos and rodando and not finalizado:
            estados.append("rodando")
        else:
            estados.append("pendente")
    return estados


def html_plano(plano: dict, concluidas: int, rodando: bool, finalizado: bool) -> str:
    passos = plano.get("passos") or []
    faltantes = plano.get("informacoes_faltantes") or []
    estados = estado_dos_passos(len(passos), concluidas, rodando, finalizado, bool(faltantes))
    feitos = estados.count("feito")
    progresso = "concluído" if feitos == len(passos) else f"{feitos} de {len(passos)}"
    largura = int(feitos / len(passos) * 100) if passos else 100

    linhas = []
    for texto, estado in zip(passos, estados):
        marca = "✓" if estado == "feito" else ""
        andamento = '<span class="em-andamento">em andamento…</span>' if estado == "rodando" else ""
        classe = "pendente" if estado == "pendente" else ""
        linhas.append(f'<div class="em-passo {classe}"><span class="em-marca {estado}">{marca}</span>'
                      f'<span>{_e(texto)}</span>{andamento}</div>')

    aguardando = ""
    if finalizado and faltantes and feitos < len(passos):
        pilulas = "".join(f'<span class="em-pilula em-roxo">{_e(f)}</span>' for f in faltantes)
        aguardando = f'<div class="em-faltando">Aguardando do cliente: {pilulas}</div>'

    return (f'<div class="em-plano"><div class="em-plano-topo">Plano · {progresso}</div>'
            f'<div class="em-plano-objetivo">{_e(plano.get("objetivo"))}</div>'
            f'<div class="em-barra"><div style="width: {largura}%"></div></div>'
            f'{"".join(linhas)}{aguardando}</div>')


def html_status(rotulo: str) -> str:
    return f'<div class="em-status"><span class="em-marca rodando"></span>{_e(rotulo)}…</div>'


# ============================================================================
# Cartões por tool
# ============================================================================

def _pilula_disponibilidade(rotulo: str) -> str:
    return f'<span class="em-pilula {ESTILO_DISPONIBILIDADE.get(rotulo, "em-cinza")}">{_e(rotulo)}</span>'


def _mini_produto(p: dict) -> str:
    return f'<div class="em-alt">{_e(p["nome"])}<br><b>{_e(p["preco"])}</b></div>'


def html_produto(resultado: dict) -> str | None:
    if not isinstance(resultado, dict):
        return None
    if not resultado.get("encontrado"):
        opcoes = resultado.get("candidatos") or resultado.get("sugestoes") or []
        if not opcoes:
            return None
        titulo = "Qual destes?" if resultado.get("candidatos") else "Você quis dizer?"
        return (f'<div class="em-card"><div class="em-sub">{titulo}</div>'
                f'<div class="em-alts">{"".join(_mini_produto(p) for p in opcoes[:3])}</div></div>')

    p = resultado["produto"]
    promo = p.get("promocao")
    if promo:
        preco = (f'<span class="em-riscado">{_e(promo["preco_original"])}</span>'
                 f'<span class="em-preco">{_e(promo["preco_promocional"])}</span> '
                 f'<span class="em-pilula em-promo">−{_e(int(promo["desconto_percentual"]))}% · '
                 f'{_e(promo["nome"])}</span>')
    else:
        preco = f'<div class="em-preco">{_e(p["preco"])}</div>'

    specs = " · ".join(
        f"{ROTULOS_SPECS.get(k, k)}: {VALORES_SPECS.get(v, v)}"
        for k, v in (p.get("especificacoes") or {}).items())
    info = (f'<span class="em-pilula em-info">PIX: {_e(p["preco_no_pix"])}</span>'
            f'<span class="em-pilula em-info">{_e(p["parcelamento_maximo"])}</span>') if p["pode_ser_vendido"] else ""

    alternativas = resultado.get("alternativas_disponiveis") or []
    bloco_alt = (f'<div class="em-sub" style="margin-top: 12px; font-weight: 600">Alternativas disponíveis</div>'
                 f'<div class="em-alts">{"".join(_mini_produto(a) for a in alternativas)}</div>'
                 if alternativas else "")

    return (f'<div class="em-card"><div class="em-linha"><div><div class="em-titulo">{_e(p["nome"])}</div>'
            f'<div class="em-sub">{_e(p["categoria"])}</div></div>{_pilula_disponibilidade(p["disponibilidade"])}</div>'
            f'{preco}<div>{info}</div>'
            f'{f"<div class=em-sub style=margin-top:10px>{_e(specs)}</div>" if specs else ""}'
            f'{bloco_alt}</div>')


def html_busca(resultado: dict) -> str | None:
    if not isinstance(resultado, dict) or not resultado.get("produtos"):
        return None
    selo_promo = ' <span class="em-pilula em-promo">promoção</span>'
    linhas = "".join(
        f'<tr><td style="padding:8px;border-bottom:1px solid #EEF0F6">{_e(p["nome"])}'
        f'{selo_promo if p.get("promocao") else ""}</td>'
        f'<td style="padding:8px;border-bottom:1px solid #EEF0F6;color:#5A6380">{_e(p["categoria"])}</td>'
        f'<td style="padding:8px;border-bottom:1px solid #EEF0F6;text-align:right;white-space:nowrap">{_e(p["preco"])}</td></tr>'
        for p in resultado["produtos"])
    total, exibidos = resultado["total_encontrado"], resultado["exibidos"]
    rodape = f" · exibindo {exibidos}" if exibidos < total else ""
    return (f'<div class="em-card"><div class="em-sub">{total} encontrado(s){rodape}</div>'
            f'<div style="overflow-x:auto;margin-top:8px"><table style="width:100%;border-collapse:collapse;font-size:14px">'
            f'<thead><tr><th style="text-align:left;padding:8px;color:#5A6380">Produto</th>'
            f'<th style="text-align:left;padding:8px;color:#5A6380">Categoria</th>'
            f'<th style="text-align:right;padding:8px;color:#5A6380">Preço</th></tr></thead>'
            f'<tbody>{linhas}</tbody></table></div></div>')


def _html_prazos(prazos: dict) -> str:
    itens = [("arrependimento_compra_online", "Arrependimento (compra online)"),
             ("troca_por_defeito", "Troca por defeito"), ("garantia_legal", "Garantia legal")]
    linhas = [
        f'<div><span>{rotulo} · até {_data_br(prazos[chave]["valido_ate"])}</span>'
        f'{"<span class=em-vigente>Vigente</span>" if prazos[chave]["dentro_do_prazo"] else "<span class=em-encerrado>Encerrado</span>"}</div>'
        for chave, rotulo in itens if chave in prazos]
    if not linhas:
        return ""
    return (f'<div class="em-prazos"><b>Prazos na data de referência ({_data_br(prazos["data_referencia"])})</b>'
            f'{"".join(linhas)}<div class="em-sub">{_e(prazos.get("aviso", ""))}</div></div>')


def html_pedido(resultado: dict) -> str | None:
    if not isinstance(resultado, dict):
        return None
    if not resultado.get("verificado"):
        restantes = resultado.get("tentativas_restantes")
        detalhe = (f"Tentativas restantes nesta conversa: {restantes}" if restantes is not None
                   else "Por segurança, novas consultas foram bloqueadas nesta conversa.")
        return ('<div class="em-card"><b>Não foi possível confirmar a identidade</b>'
                f'<div class="em-sub">Nenhum dado do pedido é exibido. {_e(detalhe)}</div></div>')

    cartoes = []
    for p in resultado.get("pedidos", []):
        prazos = p.get("prazos") or {}
        entrega = prazos.get("entrega") or {}
        alerta = (f'<div class="em-alerta">Entrega atrasada há {entrega["dias_de_atraso"]} dia(s)</div>'
                  if entrega.get("atrasado") else "")
        rastreio = (f'<span class="em-mono">{_e(p["codigo_rastreamento"])}</span>'
                    if p.get("codigo_rastreamento") else "—")
        observacao = (f'<div class="em-sub" style="margin-top:10px">Observação: {_e(p["observacao_do_pedido"])}</div>'
                      if p.get("observacao_do_pedido") else "")
        cartoes.append(
            f'<div class="em-card"><div class="em-linha"><div class="em-titulo">Pedido {_e(p["pedido_id"])}</div>'
            f'<span class="em-pilula {ESTILO_STATUS.get(p["status"], "em-roxo")}">{_e(p["status"])}</span></div>'
            f'<div class="em-grade">'
            f'<div><span class="em-sub">Itens</span>{"<br>".join(_e(i) for i in p["itens"])}</div>'
            f'<div><span class="em-sub">Valor</span>{_e(p["valor_total"])} · {_e(p["forma_de_pagamento"])}</div>'
            f'<div><span class="em-sub">Pedido em</span>{_data_br(p["data_do_pedido"])}</div>'
            f'<div><span class="em-sub">Rastreio</span>{rastreio}</div>'
            f'<div><span class="em-sub">Previsão de entrega</span>{_data_br(p.get("previsao_entrega"))}</div>'
            f'</div>{alerta}{observacao}{_html_prazos(prazos)}</div>')
    return "".join(cartoes) or None


def html_horario(resultado: dict) -> str | None:
    if not isinstance(resultado, dict):
        return None
    if resultado.get("loja_aberta_agora"):
        texto = f'<b>Aberta agora</b> <span class="em-sub">{_e(resultado["dia_da_semana"])} · {_e(resultado["horario_de_hoje"])}</span>'
        cor = "#1F7A3A"
    else:
        texto = f'<b>Fechada</b> <span class="em-sub">a equipe volta {_e(resultado.get("equipe_retorna_em", ""))}</span>'
        cor = "#B42318"
    return (f'<div class="em-card" style="display:flex;align-items:center;gap:10px">'
            f'<span style="width:10px;height:10px;border-radius:50%;background:{cor};flex:0 0 10px"></span>{texto}</div>')


def html_reclamacao(resultado: dict) -> str | None:
    if not isinstance(resultado, dict) or not resultado.get("registrada"):
        return None
    return (f'<div class="em-card em-card-escuro"><div style="color:#B9C0D6;font-size:14px">Protocolo</div>'
            f'<div class="em-mono" style="font-size:22px;font-weight:500">{_e(resultado["protocolo"])}</div>'
            f'<div>Retorno da equipe em até <b>{_e(resultado["prazo_de_retorno"])}</b></div></div>')


RENDERIZADORES_HTML = {
    "consultar_produto": html_produto,
    "buscar_produtos": html_busca,
    "consultar_pedido": html_pedido,
    "hora_atual_loja": html_horario,
    "registrar_reclamacao": html_reclamacao,
}


def politica_para_cliente(chamada: ChamadaTool) -> tuple[str, str] | None:
    """(título, texto) da política consultada, sem as orientações internas ao
    assistente. Seções de uso interno não são exibidas."""
    secao = (chamada.entrada or {}).get("secao", "")
    info = kb.secoes().get(secao)
    if info is None or info.publico == "interno" or not isinstance(chamada.resultado, str):
        return None
    sem_citacoes = "\n".join(l for l in chamada.resultado.splitlines() if not l.lstrip().startswith(">"))
    corpo = re.sub(r"^# .*\n", "", sem_citacoes, count=1).strip()
    corpo = re.sub(r"^## ", "#### ", corpo, flags=re.M)
    return info.titulo, re.sub(r"\n{3,}", "\n\n", corpo)


# ============================================================================
# Resposta completa
# ============================================================================

def ultimo_plano(chamadas: list[ChamadaTool]) -> tuple[dict | None, int]:
    """O último plano registrado e quantas tools foram concluídas depois dele."""
    plano, depois = None, 0
    for c in chamadas:
        if c.nome == "planejar" and isinstance(c.resultado, dict):
            plano, depois = c.resultado, 0
        elif plano is not None:
            depois += 1
    return plano, depois


def renderizar_resposta(resposta: Resposta) -> None:
    """Ordem: plano (se houver), cartões com os dados consultados e, por último,
    o texto do atendente, que comenta o que está nos cartões."""
    plano, concluidas = ultimo_plano(resposta.chamadas)
    if plano:
        st.markdown(html_plano(plano, concluidas, rodando=False, finalizado=True), unsafe_allow_html=True)

    cartoes, politicas, vistos = [], [], set()
    for chamada in resposta.chamadas:
        if chamada.nome == "ler_politica":
            politica = politica_para_cliente(chamada)
            if politica and politica[0] not in vistos:
                vistos.add(politica[0])
                politicas.append(politica)
            continue
        funcao = RENDERIZADORES_HTML.get(chamada.nome)
        html = funcao(chamada.resultado) if funcao else None
        if html:
            cartoes.append(html)

    if cartoes or politicas:
        st.markdown('<div class="em-rotulo-fontes">Fontes desta resposta</div>', unsafe_allow_html=True)
    for html in cartoes:
        st.markdown(html, unsafe_allow_html=True)
    for titulo, texto in politicas:
        with st.expander(f"Política consultada · {titulo}"):
            st.markdown(texto)

    st.markdown(resposta.texto)
