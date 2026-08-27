from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_escopo_unidade, require_permission, require_role

router = APIRouter(prefix="/api/objetivos", tags=["objetivos"])


def _obter_objetivo(
    objetivo_id: int,
    db: Session,
    unidade_id: int | None = None,
) -> models.Objetivo:
    objetivo = db.get(models.Objetivo, objetivo_id)
    if objetivo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objetivo não encontrado",
        )
    if unidade_id is not None:
        tem = db.scalar(
            select(1)
            .select_from(models.Iniciativa)
            .join(models.Iniciativa.indicadores)
            .join(
                models.indicador_unidades,
                models.indicador_unidades.c.indicador_id == models.Indicador.id,
            )
            .where(
                models.Iniciativa.objetivo_id == objetivo_id,
                models.indicador_unidades.c.unidade_id == unidade_id,
            )
        )
        if tem is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Objetivo não encontrado",
            )
    return objetivo


@router.get("", response_model=list[schemas.ObjetivoRead])
def listar_objetivos(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm", "default"),
    unidade_id: int | None = Depends(get_escopo_unidade),
):
    if unidade_id is None:
        return db.scalars(
            select(models.Objetivo).order_by(models.Objetivo.id)
        ).all()

    objetivo_ids = (
        select(models.Iniciativa.objetivo_id)
        .join(models.Iniciativa.indicadores)
        .join(
            models.indicador_unidades,
            models.indicador_unidades.c.indicador_id == models.Indicador.id,
        )
        .where(models.indicador_unidades.c.unidade_id == unidade_id)
    )
    return db.scalars(
        select(models.Objetivo)
        .where(models.Objetivo.id.in_(objetivo_ids))
        .order_by(models.Objetivo.id)
    ).all()


@router.post(
    "",
    response_model=schemas.ObjetivoRead,
    status_code=status.HTTP_201_CREATED,
)
def criar_objetivo(
    dados: schemas.ObjetivoCreate,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_permission("/objetivos", "criar"),
):
    objetivo = models.Objetivo(**dados.model_dump())
    db.add(objetivo)
    db.commit()
    db.refresh(objetivo)
    return objetivo


@router.get("/{objetivo_id}", response_model=schemas.ObjetivoRead)
def obter_objetivo(
    objetivo_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm", "default"),
    unidade_id: int | None = Depends(get_escopo_unidade),
):
    return _obter_objetivo(objetivo_id, db, unidade_id)


@router.put("/{objetivo_id}", response_model=schemas.ObjetivoRead)
def atualizar_objetivo(
    objetivo_id: int,
    dados: schemas.ObjetivoUpdate,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_permission("/objetivos", "editar"),
):
    objetivo = _obter_objetivo(objetivo_id, db)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(objetivo, campo, valor)
    db.commit()
    db.refresh(objetivo)
    return objetivo


@router.delete("/{objetivo_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_objetivo(
    objetivo_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_permission("/objetivos", "excluir"),
):
    objetivo = _obter_objetivo(objetivo_id, db)
    db.delete(objetivo)
    db.commit()
