import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["comprovacoes"])

TAMANHO_MAXIMO = 10 * 1024 * 1024  # 10 MB


def _raiz() -> Path:
    return Path(__file__).resolve().parents[2]


def _pasta_uploads() -> Path:
    return _raiz() / "uploads" / "comprovacoes"


@router.get(
    "/api/indicadores/{indicador_id}/comprovacoes",
    response_model=list[schemas.ComprovacaoRead],
)
def listar_comprovacoes(
    indicador_id: int,
    db: Session = Depends(get_db),
):
    if db.get(models.Indicador, indicador_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Indicador não encontrado",
        )
    return db.scalars(
        select(models.Comprovacao)
        .where(models.Comprovacao.indicador_id == indicador_id)
        .order_by(
            models.Comprovacao.ano.desc(),
            models.Comprovacao.mes.desc(),
        )
    ).all()


@router.post(
    "/api/indicadores/{indicador_id}/comprovacoes",
    response_model=schemas.ComprovacaoRead,
    status_code=status.HTTP_201_CREATED,
)
async def criar_comprovacao(
    indicador_id: int,
    ano: int = Form(ge=2000, le=2100),
    mes: int = Form(ge=1, le=12),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if db.get(models.Indicador, indicador_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Indicador não encontrado",
        )

    nome_original = Path(arquivo.filename or "comprovacao.pdf").name
    if not nome_original.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A comprovação deve ser um arquivo PDF",
        )

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O arquivo enviado está vazio",
        )
    if len(conteudo) > TAMANHO_MAXIMO:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="O arquivo excede o tamanho máximo de 10 MB",
        )
    if not conteudo.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O arquivo enviado não é um PDF válido",
        )

    _pasta_uploads().mkdir(parents=True, exist_ok=True)
    nome_armazenado = f"{uuid.uuid4().hex}.pdf"
    caminho_relativo = Path("uploads") / "comprovacoes" / nome_armazenado

    comprovacao = db.scalar(
        select(models.Comprovacao).where(
            models.Comprovacao.indicador_id == indicador_id,
            models.Comprovacao.ano == ano,
            models.Comprovacao.mes == mes,
        )
    )
    if comprovacao is not None:
        (_raiz() / comprovacao.arquivo_caminho).unlink(missing_ok=True)
        comprovacao.arquivo_nome = nome_original
        comprovacao.arquivo_caminho = str(caminho_relativo)
    else:
        comprovacao = models.Comprovacao(
            indicador_id=indicador_id,
            ano=ano,
            mes=mes,
            arquivo_nome=nome_original,
            arquivo_caminho=str(caminho_relativo),
        )
        db.add(comprovacao)

    (_raiz() / caminho_relativo).write_bytes(conteudo)
    db.commit()
    db.refresh(comprovacao)
    return comprovacao


@router.get("/api/comprovacoes/{comprovacao_id}/arquivo")
def visualizar_comprovacao(
    comprovacao_id: int,
    db: Session = Depends(get_db),
):
    comprovacao = db.get(models.Comprovacao, comprovacao_id)
    if comprovacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comprovação não encontrada",
        )
    caminho = _raiz() / comprovacao.arquivo_caminho
    if not caminho.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo não encontrado",
        )
    return FileResponse(
        path=caminho,
        media_type="application/pdf",
        filename=comprovacao.arquivo_nome,
        content_disposition_type="inline",
    )


@router.delete(
    "/api/comprovacoes/{comprovacao_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def excluir_comprovacao(
    comprovacao_id: int,
    db: Session = Depends(get_db),
):
    comprovacao = db.get(models.Comprovacao, comprovacao_id)
    if comprovacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comprovação não encontrada",
        )
    (_raiz() / comprovacao.arquivo_caminho).unlink(missing_ok=True)
    db.delete(comprovacao)
    db.commit()


@router.put(
    "/api/comprovacoes/{comprovacao_id}",
    response_model=schemas.ComprovacaoRead,
)
def atualizar_status_comprovacao(
    comprovacao_id: int,
    dados: schemas.ComprovacaoUpdate,
    db: Session = Depends(get_db),
):
    comprovacao = db.get(models.Comprovacao, comprovacao_id)
    if comprovacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comprovação não encontrada",
        )
    if (
        dados.status == models.StatusComprovacao.RECUSADO
        and not dados.justificativa
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Justificativa é obrigatória para reprovar a comprovação",
        )
    comprovacao.status = dados.status
    comprovacao.justificativa = dados.justificativa
    comprovacao.prazo_reenvio = dados.prazo_reenvio
    db.commit()
    db.refresh(comprovacao)
    return comprovacao
