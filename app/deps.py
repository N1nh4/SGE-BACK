import json

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import decodificar_token
from .database import get_db
from .models import (
    Pagina,
    Perfil,
    PerfilPagina,
    Usuario,
    usuario_unidades,
    Unidade,
)


def get_usuario_atual(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> Usuario:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de token inválido",
        )

    token = authorization.removeprefix("Bearer ")
    usuario_id = decodificar_token(token)

    if usuario_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )

    usuario = db.get(Usuario, usuario_id)

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
        )

    return usuario


def _obter_papel_unidade(
    usuario: Usuario, unidade_id: int | None, db: Session
) -> str:
    if unidade_id is None:
        return usuario.papel

    if usuario.papel == "master":
        return "master"

    row = db.execute(
        select(usuario_unidades.c.papel)
        .where(
            usuario_unidades.c.usuario_id == usuario.id,
            usuario_unidades.c.unidade_id == unidade_id,
        )
    ).scalar_one_or_none()

    if row is None:
        return ""
    return row


def require_role(
    *papeis: str,
    unidade_id: int | None = None,
):
    def _verificar(
        usuario: Usuario = Depends(get_usuario_atual),
        x_unidade_id: int | None = Header(default=None, convert_underscores=False),
        db: Session = Depends(get_db),
    ):
        eff_unidade = unidade_id if unidade_id is not None else x_unidade_id
        papel = _obter_papel_unidade(usuario, eff_unidade, db)

        if papel not in papeis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sem permissão para acessar este recurso",
            )
        return usuario

    return Depends(_verificar)


def _usuario_tem_acao(
    usuario: Usuario,
    pagina_chave: str,
    acao: str,
    unidade_id: int | None,
    db: Session,
) -> bool:
    papel = _obter_papel_unidade(usuario, unidade_id, db)

    perfil = db.scalar(
        select(Perfil).where(Perfil.chave == papel)
    )
    if perfil is None:
        return False

    pagina = db.scalar(
        select(Pagina).where(Pagina.chave == pagina_chave)
    )
    if pagina is None:
        return False

    pp = db.scalar(
        select(PerfilPagina).where(
            PerfilPagina.perfil_id == perfil.id,
            PerfilPagina.pagina_id == pagina.id,
        )
    )
    if pp is None:
        return False

    acoes_raw = pp.acoes
    if isinstance(acoes_raw, str):
        acoes = json.loads(acoes_raw)
    elif isinstance(acoes_raw, list):
        acoes = acoes_raw
    else:
        acoes = []

    return acao in acoes


def require_permission(pagina_chave: str, acao: str):
    def _verificar(
        usuario: Usuario = Depends(get_usuario_atual),
        x_unidade_id: int | None = Header(default=None, convert_underscores=False),
        db: Session = Depends(get_db),
    ):
        if usuario.papel == "master":
            return usuario

        if not _usuario_tem_acao(usuario, pagina_chave, acao, x_unidade_id, db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sem permissão para '{acao}' em '{pagina_chave}'",
            )
        return usuario

    return Depends(_verificar)
