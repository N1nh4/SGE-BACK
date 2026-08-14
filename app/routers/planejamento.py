from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/planejamento", tags=["planejamento"])


def _opcoes():
    return (
        selectinload(models.Iniciativa.objetivo),
        selectinload(models.Iniciativa.indicadores),
        selectinload(models.Iniciativa.indicadores).selectinload(
            models.Indicador.unidade
        ),
    )


@router.get("", response_model=list[schemas.IniciativaRead])
def listar_planejamento(db: Session = Depends(get_db)):
    return db.scalars(
        select(models.Iniciativa)
        .options(*_opcoes())
        .order_by(models.Iniciativa.id)
    ).all()


@router.get("/{iniciativa_id}", response_model=schemas.IniciativaRead)
def obter_planejamento(
    iniciativa_id: int,
    db: Session = Depends(get_db),
):
    iniciativa = db.scalar(
        select(models.Iniciativa)
        .where(models.Iniciativa.id == iniciativa_id)
        .options(*_opcoes())
    )
    if iniciativa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planejamento não encontrado",
        )
    return iniciativa


@router.post(
    "",
    response_model=schemas.IniciativaRead,
    status_code=status.HTTP_201_CREATED,
)
def criar_planejamento(
    dados: schemas.IniciativaCreate,
    db: Session = Depends(get_db),
):
    if db.get(models.Objetivo, dados.objetivo_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objetivo estratégico não encontrado",
        )

    iniciativa = models.Iniciativa(
        nome=dados.nome,
        objetivo_id=dados.objetivo_id,
        indicadores=[
            models.Indicador(**indicador.model_dump())
            for indicador in dados.indicadores
        ],
    )
    db.add(iniciativa)
    db.commit()

    return db.scalar(
        select(models.Iniciativa)
        .where(models.Iniciativa.id == iniciativa.id)
        .options(*_opcoes())
    )


@router.put("/{iniciativa_id}", response_model=schemas.IniciativaRead)
def atualizar_planejamento(
    iniciativa_id: int,
    dados: schemas.IniciativaUpdate,
    db: Session = Depends(get_db),
):
    iniciativa = db.scalar(
        select(models.Iniciativa)
        .where(models.Iniciativa.id == iniciativa_id)
        .options(selectinload(models.Iniciativa.indicadores))
    )
    if iniciativa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planejamento não encontrado",
        )

    campos = dados.model_dump(exclude_unset=True)
    if "objetivo_id" in campos and campos["objetivo_id"] is not None:
        if db.get(models.Objetivo, campos["objetivo_id"]) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Objetivo estratégico não encontrado",
            )

    if "nome" in campos:
        iniciativa.nome = campos["nome"]
    if "objetivo_id" in campos:
        iniciativa.objetivo_id = campos["objetivo_id"]
    if "indicadores" in campos:
        iniciativa.indicadores = [
            models.Indicador(**indicador) for indicador in campos["indicadores"]
        ]

    db.commit()
    return db.scalar(
        select(models.Iniciativa)
        .where(models.Iniciativa.id == iniciativa.id)
        .options(*_opcoes())
    )


@router.delete("/{iniciativa_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_planejamento(iniciativa_id: int, db: Session = Depends(get_db)):
    iniciativa = db.get(models.Iniciativa, iniciativa_id)
    if iniciativa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planejamento não encontrado",
        )
    db.delete(iniciativa)
    db.commit()
