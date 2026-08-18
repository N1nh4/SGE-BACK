from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import hash_senha
from ..database import get_db
from ..deps import require_role

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
    _usuario: models.Usuario = require_role("master", "adm"),
):
    _verificar_email(dados.email, db)
    dados_dict = dados.model_dump()
    senha = dados_dict.pop("senha")
    usuario = models.Usuario(senha_hash=hash_senha(senha), **dados_dict)
    db.add(usuario)
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
    _usuario: models.Usuario = require_role("master", "adm"),
):
    usuario = _obter_usuario(usuario_id, db)
    campos = dados.model_dump(exclude_unset=True)
    if "email" in campos:
        _verificar_email(campos["email"], db, ignorar_id=usuario_id)
    senha = campos.pop("senha", None)
    if senha is not None:
        usuario.senha_hash = hash_senha(senha)
    for campo, valor in campos.items():
        setattr(usuario, campo, valor)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm"),
):
    usuario = _obter_usuario(usuario_id, db)
    db.delete(usuario)
    db.commit()
