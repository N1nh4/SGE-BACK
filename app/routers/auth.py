from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import criar_token, verificar_senha
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=schemas.LoginResponse)
def login(dados: schemas.LoginRequest, db: Session = Depends(get_db)):
    usuario = db.scalar(
        select(models.Usuario).where(models.Usuario.email == dados.email)
    )
    if usuario is None or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos",
        )
    if usuario.status != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Conta desativada. Contate o administrador.",
        )
    token = criar_token(usuario.id)
    return schemas.LoginResponse(token=token, usuario=usuario)
