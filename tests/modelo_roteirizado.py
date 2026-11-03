"""Modelo falso para testar o loop do agente sem chamar nenhuma API.

Recebe um roteiro de respostas: ("tool", nome, argumentos) faz o "modelo"
chamar uma ferramenta; ("texto", "...") encerra o turno com uma resposta;
("erro", excecao) simula uma falha do provedor.
Guarda o que recebeu (prompt de sistema, ferramentas e resultados das tools)
para os testes conferirem.
"""

from __future__ import annotations

import json
from typing import Any

from strands.models.model import Model


class ModeloRoteirizado(Model):
    def __init__(self, roteiro: list[tuple]):
        self.roteiro = list(roteiro)
        self.system_prompt: str | None = None
        self.tool_specs: list[dict] = []
        self.chamadas = 0

    def update_config(self, **model_config: Any) -> None:
        pass

    def get_config(self) -> dict:
        return {"model_id": "roteirizado"}

    async def structured_output(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError
        yield

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.system_prompt = system_prompt
        self.tool_specs = tool_specs or []
        passo = self.roteiro.pop(0)
        self.chamadas += 1
        if passo[0] == "erro":
            raise passo[1]

        yield {"messageStart": {"role": "assistant"}}
        if passo[0] == "tool":
            _, nome, argumentos = passo
            yield {"contentBlockStart": {"start": {"toolUse": {
                "toolUseId": f"t{self.chamadas}", "name": nome}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(argumentos)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockDelta": {"delta": {"text": passo[1]}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}


def resultados_de_tools(mensagens: list[dict]) -> list[str]:
    """Textos dos resultados de ferramentas que voltaram para o modelo."""
    textos = []
    for m in mensagens:
        for bloco in m.get("content", []):
            if "toolResult" in bloco:
                textos += [c.get("text") or json.dumps(c.get("json"), ensure_ascii=False)
                           for c in bloco["toolResult"]["content"]]
    return textos
