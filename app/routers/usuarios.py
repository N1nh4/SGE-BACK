from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import hash_senha
from ..database import get_db
from ..deps import require_permission, require_role

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])


def _obter_usuario(usuario_id: int, db: Session) -> models.Usuario:
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )
    return usuario


def _verificar_email(email: str, db: Session, ignorar_id: int | None = None) -> None:
    consulta = select(models.Usuario).where(models.Usuario.email == email)
    if ignorar_id is not None:
        consulta = consulta.where(models.Usuario.id != ignorar_id)
    if db.scalar(consulta) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já cadastrado",
        )


@router.get("", response_model=list[schemas.UsuarioRead])
def listar_usuarios(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm"),
):
    return db.scalars(
        select(models.Usuario).order_by(models.Usuario.id)
    ).all()


@router.post(
    "",
    response_model=schemas.UsuarioRead,
    status_code=status.HTTP_201_CREATED,
)
def criar_usuario(
    dados: schemas.UsuarioCreate,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_permission("/unidades", "criar"),
):
    _verificar_email(dados.email, db)
    dados_dict = dados.model_dump()
    senha = dados_dict.pop("senha")
    unidade_id = dados_dict.pop("unidade_id", None)
    papel = dados_dict.pop("papel", "default")
    usuario = models.Usuario(papel=papel, senha_hash=hash_senha(senha), **dados_dict)
    db.add(usuario)
    db.flush()

    if unidade_id is not None:
        db.execute(
            models.usuario_unidades.insert().values(
                usuario_id=usuario.id,
                unidade_id=unidade_id,
                papel=papel,
            )
        )

    db.commit()
    db.refresh(usuario)
    return usuario


@router.get("/{usuario_id}", response_model=schemas.UsuarioRead)
def obter_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm"),
):
    return _obter_usuario(usuario_id, db)


@router.put("/{usuario_id}", response_model=schemas.UsuarioRead)
def atualizar_usuario(
    usuario_id: int,
    dados: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_permission("/unidades", "editar"),
):
    usuario = _obter_usuario(usuario_id, db)
    campos = dados.model_dump(exclude_unset=True)
    if "email" in campos:
        _verificar_email(campos["email"], db, ignorar_id=usuario_id)
    senha = campos.pop("senha", None)
    unidade_id = campos.pop("unidade_id", None)
    if senha is not None:
        usuario.senha_hash = hash_senha(senha)
    for campo, valor in campos.items():
        setattr(usuario, campo, valor)

    if unidade_id is not None:
        exists = db.execute(
            select(models.usuario_unidades).where(
                models.usuario_unidades.c.usuario_id == usuario_id,
                models.usuario_unidades.c.unidade_id == unidade_id,
            )
        ).scalar_one_or_none()
        if exists is None:
            db.execute(
                models.usuario_unidades.insert().values(
                    usuario_id=usuario_id,
                    unidade_id=unidade_id,
                    papel=usuario.papel,
                )
            )

    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_permission("/unidades", "excluir"),
):
    usuario = _obter_usuario(usuario_id, db)
    db.delete(usuario)
    db.commit()
