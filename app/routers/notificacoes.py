import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import decodificar_token
from ..database import get_db
from ..deps import get_usuario_atual, require_role
from ..services import notificacoes_stream

router = APIRouter(prefix="/api/notificacoes", tags=["notificacoes"])


@router.get("", response_model=list[schemas.NotificacaoRead])
def listar_notificacoes(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm", "default"),
):
    usuario = _usuario
    return db.scalars(
        select(models.Notificacao)
        .where(models.Notificacao.usuario_id == usuario.id)
        .order_by(models.Notificacao.created_at.desc())
    ).all()


@router.get("/quantidade")
def quantidade_nao_lidas(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm", "default"),
):
    usuario = _usuario
    total = db.scalar(
        select(func.count(models.Notificacao.id))
        .where(
            models.Notificacao.usuario_id == usuario.id,
            models.Notificacao.lida.is_(False),
        )
    )
    return {"quantidade": total or 0}


@router.get("/stream")
async def stream_notificacoes(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Fluxo SSE de notificações em tempo real para o usuário autenticado.

    O front conecta via EventSource passando o token como query param.
    Cada evento `message` dispara a atualização da quantidade de não lidas.
    """
    usuario_id = decodificar_token(token)
    if usuario_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )
    if db.get(models.Usuario, usuario_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )

    assinatura_id = uuid.uuid4().hex
    fila, _ = notificacoes_stream.registrar_assinatura(usuario_id, assinatura_id)

    async def gerar():
        try:
            # Comentário inicial: alguns proxies descartam o header até
            # chegarem os primeiros bytes.
            yield "retry: 15000\n\n"
            while True:
                try:
                    mensagem = await asyncio.wait_for(fila.get(), timeout=25)
                    yield f"event: atualizar\ndata: {mensagem}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat mantém a conexão viva entre eventos.
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            notificacoes_stream.remover_assinatura(usuario_id, assinatura_id)
            raise

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{notificacao_id}/ler", response_model=schemas.NotificacaoRead)
def marcar_como_lida(
    notificacao_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm", "default"),
):
    usuario = _usuario
    notificacao = db.scalar(
        select(models.Notificacao).where(
            models.Notificacao.id == notificacao_id,
            models.Notificacao.usuario_id == usuario.id,
        )
    )
    if notificacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificação não encontrada",
        )
    notificacao.lida = True
    db.commit()
    db.refresh(notificacao)
    return notificacao


@router.post("/ler-todas")
def marcar_todas_como_lidas(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm", "default"),
):
    usuario = _usuario
    db.execute(
        models.Notificacao.__table__.update()
        .where(
            models.Notificacao.usuario_id == usuario.id,
            models.Notificacao.lida.is_(False),
        )
        .values(lida=True)
    )
    db.commit()
    return {"ok": True}


def criar_notificacoes_para_unidade(
    db: Session,
    unidade_ids: list[int],
    tipo: str,
    titulo: str,
    mensagem: str,
    ignorar_usuario_id: int | None = None,
) -> list[int]:
    """Cria uma notificação para cada usuário ativo vinculado às unidades.

    Retorna os `usuario_id` que receberam notificação (excluindo quem criou),
    para que o chamador possa notificar via SSE **após** o commit.
    """
    if not unidade_ids:
        return []

    usuarios = db.execute(
        select(models.Usuario.id)
        .join(
            models.usuario_unidades,
            models.usuario_unidades.c.usuario_id == models.Usuario.id,
        )
        .where(
            models.usuario_unidades.c.unidade_id.in_(unidade_ids),
            models.Usuario.status == 1,
        )
        .distinct()
    ).scalars().all()

    notificados: list[int] = []
    for usuario_id in usuarios:
        if usuario_id == ignorar_usuario_id:
            continue
        db.add(
            models.Notificacao(
                usuario_id=usuario_id,
                tipo=tipo,
                titulo=titulo,
                mensagem=mensagem,
            )
        )
        notificados.append(usuario_id)
    return notificados


def criar_notificacoes_para_papeis(
    db: Session,
    papeis: list[str],
    tipo: str,
    titulo: str,
    mensagem: str,
    ignorar_usuario_id: int | None = None,
) -> list[int]:
    """Cria uma notificação para cada usuário ativo com um dos papéis dados.

    Usado para avisar usuários não-default (master/adm/teste) sobre novas
    propostas de planejamento.
    """
    usuarios = db.execute(
        select(models.Usuario.id).where(
            models.Usuario.papel.in_(papeis),
            models.Usuario.status == 1,
        )
    ).scalars().all()

    notificados: list[int] = []
    for usuario_id in usuarios:
        if usuario_id == ignorar_usuario_id:
            continue
        db.add(
            models.Notificacao(
                usuario_id=usuario_id,
                tipo=tipo,
                titulo=titulo,
                mensagem=mensagem,
            )
        )
        notificados.append(usuario_id)
    return notificados
