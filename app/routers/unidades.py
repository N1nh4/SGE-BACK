from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/unidades", tags=["unidades"])


@router.get("", response_model=list[schemas.UnidadeRead])
def listar_unidades(db: Session = Depends(get_db)):
    return db.scalars(
        select(models.Unidade).order_by(models.Unidade.id)
    ).all()


@router.post(
    "",
    response_model=schemas.UnidadeRead,
    status_code=status.HTTP_201_CREATED,
)
def criar_unidade(dados: schemas.UnidadeCreate, db: Session = Depends(get_db)):
    unidade = models.Unidade(**dados.model_dump())
    db.add(unidade)
    db.commit()
    db.refresh(unidade)
    return unidade


@router.put("/{unidade_id}", response_model=schemas.UnidadeRead)
def atualizar_unidade(
    unidade_id: int,
    dados: schemas.UnidadeUpdate,
    db: Session = Depends(get_db),
):
    unidade = db.get(models.Unidade, unidade_id)
    if unidade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unidade não encontrada",
        )
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(unidade, campo, valor)
    db.commit()
    db.refresh(unidade)
    return unidade


@router.delete("/{unidade_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_unidade(unidade_id: int, db: Session = Depends(get_db)):
    unidade = db.get(models.Unidade, unidade_id)
    if unidade is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unidade não encontrada",
        )
    db.delete(unidade)
    db.commit()
