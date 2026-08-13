from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/responsaveis", tags=["responsaveis"])


@router.get("", response_model=list[schemas.ResponsavelRead])
def listar_responsaveis(db: Session = Depends(get_db)):
    return db.scalars(
        select(models.Responsavel).order_by(models.Responsavel.id)
    ).all()


@router.post(
    "",
    response_model=schemas.ResponsavelRead,
    status_code=status.HTTP_201_CREATED,
)
def criar_responsavel(
    dados: schemas.ResponsavelCreate,
    db: Session = Depends(get_db),
):
    responsavel = models.Responsavel(**dados.model_dump())
    db.add(responsavel)
    db.commit()
    db.refresh(responsavel)
    return responsavel
