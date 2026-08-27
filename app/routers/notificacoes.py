from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_usuario_atual, require_role

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
        select(models.Notificacao)
        .where(
            models.Notificacao.usuario_id == usuario.id,
            models.Notificacao.lida.is_(False),
        )
        .with_only_columns(models.Notificacao.id)
        .count()
    )
    return {"quantidade": total or 0}


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
) -> None:
    """Cria uma notificação para cada usuário ativo vinculado às unidades."""
    if not unidade_ids:
        return

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
