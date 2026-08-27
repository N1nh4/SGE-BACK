import json
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import catalogo, models, schemas
from ..database import get_db
from ..deps import require_role

router = APIRouter(prefix="/api/paginas", tags=["paginas"])


def _gerar_chave(nome: str) -> str:
    chave = nome.lower().strip()
    chave = re.sub(r"[^a-z0-9]+", "_", chave)
    chave = chave.strip("_")
    return chave[:20]


def obter_paginas_efetivas(usuario_id: int, db: Session) -> list[str]:
    """Retorna as chaves de páginas que um usuário pode acessar pelo seu perfil."""
    usuario = db.get(models.Usuario, usuario_id)
    if usuario is None:
        return []

    perfil = db.scalar(
        select(models.Perfil).where(models.Perfil.chave == usuario.papel)
    )
    if perfil is None:
        return []

    return sorted(
        db.scalars(
            select(models.Pagina.chave)
            .join(models.PerfilPagina, models.PerfilPagina.pagina_id == models.Pagina.id)
            .where(models.PerfilPagina.perfil_id == perfil.id)
        ).all()
    )


@router.get("", response_model=list[schemas.PaginaRead])
def listar_paginas(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master"),
):
    return db.scalars(select(models.Pagina).order_by(models.Pagina.id)).all()


@router.get("/catalogo", response_model=list[schemas.PaginaCatalogo])
def listar_catalogo_acoes(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master"),
):
    paginas = db.scalars(select(models.Pagina).order_by(models.Pagina.id)).all()
    resultado = []
    for pagina in paginas:
        acoes = [
            schemas.AcaoDisponivel(chave=a, nome=catalogo.ACAO_LABELS.get(a, a))
            for a in catalogo.acoes_ordenadas(pagina.chave)
        ]
        if not acoes:
            continue
        resultado.append(
            schemas.PaginaCatalogo(chave=pagina.chave, nome=pagina.nome, acoes=acoes)
        )
    return resultado


class PerfilComAcoes(BaseModel):
    id: int
    chave: str
    nome: str
    paginas: list[schemas.PaginaComAcoes]


@router.get("/perfis", response_model=list[PerfilComAcoes])
def listar_perfis(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master"),
):
    perfis = db.scalars(
        select(models.Perfil).order_by(models.Perfil.id)
    ).all()

    resultado = []
    for perfil in perfis:
        rows = db.execute(
            select(
                models.Pagina.chave,
                models.PerfilPagina.acoes,
            )
            .join(models.PerfilPagina, models.PerfilPagina.pagina_id == models.Pagina.id)
            .where(models.PerfilPagina.perfil_id == perfil.id)
            .order_by(models.Pagina.id)
        ).all()

        paginas = []
        for chave, acoes_raw in rows:
            if isinstance(acoes_raw, str):
                acoes = json.loads(acoes_raw)
            elif isinstance(acoes_raw, list):
                acoes = acoes_raw
            else:
                acoes = ["ver"]
            paginas.append(schemas.PaginaComAcoes(chave=chave, acoes=acoes))

        resultado.append(PerfilComAcoes(
            id=perfil.id,
            chave=perfil.chave,
            nome=perfil.nome,
            paginas=paginas,
        ))

    return resultado


@router.post(
    "/perfis",
    response_model=schemas.PerfilRead,
    status_code=status.HTTP_201_CREATED,
)
def criar_perfil(
    dados: schemas.PerfilCreate,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master"),
):
    chave = _gerar_chave(dados.nome)
    if not chave:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome inválido para gerar chave",
        )
    existing = db.scalar(
        select(models.Perfil).where(models.Perfil.chave == chave)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um perfil com esse nome",
        )
    perfil = models.Perfil(chave=chave, nome=dados.nome)
    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    return perfil


@router.put("/perfis/{perfil_id}", response_model=schemas.PerfilRead)
def atualizar_perfil(
    perfil_id: int,
    dados: schemas.PerfilUpdate,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master"),
):
    perfil = db.get(models.Perfil, perfil_id)
    if perfil is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil não encontrado",
        )
    campos = dados.model_dump(exclude_unset=True)
    for campo, valor in campos.items():
        setattr(perfil, campo, valor)
    db.commit()
    db.refresh(perfil)
    return perfil


@router.delete(
    "/perfis/{perfil_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def excluir_perfil(
    perfil_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master"),
):
    perfil = db.get(models.Perfil, perfil_id)
    if perfil is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil não encontrado",
        )
    db.delete(perfil)
    db.commit()


@router.put("/perfis/{perfil_id}/paginas")
def atualizar_paginas_perfil(
    perfil_id: int,
    dados: schemas.PerfilPaginaUpdate,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master"),
):
    perfil = db.get(models.Perfil, perfil_id)
    if perfil is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil não encontrado",
        )

    db.execute(
        delete(models.PerfilPagina).where(
            models.PerfilPagina.perfil_id == perfil_id
        )
    )

    for item in dados.paginas:
        pagina = db.get(models.Pagina, item.pagina_id)
        if pagina is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Página com id {item.pagina_id} não encontrada",
            )
        db.add(models.PerfilPagina(
            perfil_id=perfil_id,
            pagina_id=item.pagina_id,
            acoes=item.acoes,
        ))

    db.commit()
    return {"ok": True}


@router.put("/perfis/{perfil_id}/paginas/{pagina_id}/acoes")
def atualizar_acoes_perfil_pagina(
    perfil_id: int,
    pagina_id: int,
    dados: schemas.PerfilPaginaAcoesUpdate,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master"),
):
    perfil = db.get(models.Perfil, perfil_id)
    if perfil is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil não encontrado",
        )

    pp = db.scalar(
        select(models.PerfilPagina).where(
            models.PerfilPagina.perfil_id == perfil_id,
            models.PerfilPagina.pagina_id == pagina_id,
        )
    )
    if pp is None:
        pp = models.PerfilPagina(
            perfil_id=perfil_id,
            pagina_id=pagina_id,
            acoes=dados.acoes,
        )
        db.add(pp)
    else:
        pp.acoes = dados.acoes

    db.commit()
    return {"ok": True}
