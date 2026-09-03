"""Gerenciador de conexões SSE para notificações em tempo real.

Cada usuário autenticado pode abrir uma conexão Server-Sent Events.
Quando notificações são criadas (ou alteradas) para um usuário, o backend
empurra um evento que faz o frontend recarregar a quantidade de não lidas
sem depender do polling de fallback.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import Any, DefaultDict

# {usuario_id: {assinatura_id: {"fila": Queue, "loop": AbstractEventLoop}}}
_assins: DefaultDict[int, dict[str, dict[str, Any]]] = defaultdict(dict)


def notificar_usuario(usuario_id: int, payload: dict) -> None:
    """Acorda todas as conexões SSE abertas para `usuario_id`.

    O push pode vir de um thread síncrono (endpoints `def` do FastAPI), então
    usamos `loop.call_soon_threadsafe` para colocar o evento na fila do event
    loop de forma segura entre threads.
    """
    mensagem = json.dumps(payload, ensure_ascii=False)
    for assinatura in list(_assins.get(usuario_id, {}).values()):
        fila: asyncio.Queue = assinatura["fila"]
        loop: asyncio.AbstractEventLoop = assinatura["loop"]
        try:
            loop.call_soon_threadsafe(fila.put_nowait, mensagem)
        except RuntimeError:
            # Loop fechado; ignora (o polling cobre o caso).
            pass


def registrar_assinatura(
    usuario_id: int, assinatura_id: str
) -> tuple[asyncio.Queue, asyncio.AbstractEventLoop]:
    fila: asyncio.Queue = asyncio.Queue(maxsize=16)
    loop = asyncio.get_running_loop()
    _assins[usuario_id][assinatura_id] = {"fila": fila, "loop": loop}
    return fila, loop


def remover_assinatura(usuario_id: int, assinatura_id: str) -> None:
    filas = _assins.get(usuario_id)
    if filas is None:
        return
    filas.pop(assinatura_id, None)
    if not filas:
        _assins.pop(usuario_id, None)