import json

from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import criar_token, decodificar_token, verificar_senha
from ..database import get_db
from ..deps import get_usuario_atual

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _obter_paginas_por_papel(papel: str, db: Session) -> list[schemas.PaginaComAcoes]:
    perfil = db.scalar(
        select(models.Perfil).where(models.Perfil.chave == papel)
    )
    if perfil is None:
        return []

    rows = db.execute(
        select(
            models.Pagina.chave,
            models.PerfilPagina.acoes,
        )
        .join(models.PerfilPagina, models.PerfilPagina.pagina_id == models.Pagina.id)
        .where(models.PerfilPagina.perfil_id == perfil.id)
        .order_by(models.Pagina.id)
    ).all()

    resultado = []
    for chave, acoes_raw in rows:
        if isinstance(acoes_raw, str):
            acoes = json.loads(acoes_raw)
        elif isinstance(acoes_raw, list):
            acoes = acoes_raw
        else:
            acoes = ["ver"]
        if "ver" in acoes:
            resultado.append(schemas.PaginaComAcoes(chave=chave, acoes=acoes))

    return resultado


def _obter_unidades_usuario(usuario: models.Usuario, db: Session) -> list[schemas.UnidadeLogin]:
    if usuario.papel == "master":
        unidades_db = db.scalars(select(models.Unidade).order_by(models.Unidade.id)).all()
        return [
            schemas.UnidadeLogin(id=u.id, nome=u.nome, papel="master")
            for u in unidades_db
        ]

    resultado = db.execute(
        select(
            models.Unidade.id,
            models.Unidade.nome,
            models.usuario_unidades.c.papel,
        )
        .join(models.usuario_unidades, models.usuario_unidades.c.unidade_id == models.Unidade.id)
        .where(models.usuario_unidades.c.usuario_id == usuario.id)
        .order_by(models.Unidade.id)
    ).all()

    return [
        schemas.UnidadeLogin(id=row[0], nome=row[1], papel=row[2])
        for row in resultado
    ]


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
    unidades = _obter_unidades_usuario(usuario, db)

    if not unidades:
        paginas = _obter_paginas_por_papel(usuario.papel, db)
    else:
        paginas = _obter_paginas_por_papel(unidades[0].papel, db)

    return schemas.LoginResponse(
        token=token, usuario=usuario, unidades=unidades, paginas=paginas,
    )


@router.post("/selecionar-unidade", response_model=schemas.SelecionarUnidadeResponse)
def selecionar_unidade(
    dados: schemas.SelecionarUnidadeRequest,
    authorization: str = Header(...),
    db: Session = Depends(get_db),
):
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

    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
        )

    if usuario.papel == "master":
        unidade = db.get(models.Unidade, dados.unidade_id)
        if unidade is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unidade não encontrada",
            )
        papel = "master"
    else:
        row = db.execute(
            select(models.usuario_unidades.c.papel)
            .where(
                models.usuario_unidades.c.usuario_id == usuario.id,
                models.usuario_unidades.c.unidade_id == dados.unidade_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário não possui acesso a esta unidade",
            )
        papel = row

    paginas = _obter_paginas_por_papel(papel, db)

    return schemas.SelecionarUnidadeResponse(
        token=token,
        usuario=usuario,
        unidade_id=dados.unidade_id,
        papel=papel,
        paginas=paginas,
    )


def _papel_efetivo(usuario: models.Usuario, unidade_id: int | None, db: Session) -> str:
    if usuario.papel == "master":
        return "master"
    if unidade_id is None:
        return usuario.papel
    papel = db.execute(
        select(models.usuario_unidades.c.papel)
        .where(
            models.usuario_unidades.c.usuario_id == usuario.id,
            models.usuario_unidades.c.unidade_id == unidade_id,
        )
    ).scalar_one_or_none()
    return papel or usuario.papel


@router.get("/me", response_model=schemas.MeResponse)
def obter_perfil_atual(
    usuario: models.Usuario = Depends(get_usuario_atual),
    x_unidade_id: int | None = Header(default=None, convert_underscores=False),
    db: Session = Depends(get_db),
):
    papel = _papel_efetivo(usuario, x_unidade_id, db)
    paginas = _obter_paginas_por_papel(papel, db)
    unidades = _obter_unidades_usuario(usuario, db)
    return schemas.MeResponse(
        usuario=usuario,
        unidades=unidades,
        unidade_id=x_unidade_id,
        papel=papel,
        paginas=paginas,
    )
