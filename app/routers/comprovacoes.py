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
from ..deps import get_escopo_unidade, require_permission, require_role
from .notificacoes import criar_notificacoes_para_papeis
from ..services import notificacoes_stream

router = APIRouter(tags=["comprovacoes"])

TAMANHO_MAXIMO = 10 * 1024 * 1024  # 10 MB
PAPEIS_GESTOR = ["master", "adm", "teste"]


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
    _usuario: models.Usuario = require_role("master", "adm", "default"),
    unidade_id: int | None = Depends(get_escopo_unidade),
):
    if unidade_id is not None:
        pertence = db.scalar(
            select(1)
            .select_from(models.indicador_unidades)
            .where(
                models.indicador_unidades.c.indicador_id == indicador_id,
                models.indicador_unidades.c.unidade_id == unidade_id,
            )
        )
        if pertence is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Indicador não encontrado",
            )
    else:
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
            models.Comprovacao.versao.desc(),
        )
    ).all()


@router.post(
    "/api/indicadores/{indicador_id}/comprovacoes",
    response_model=schemas.ComprovacaoRead,
    status_code=status.HTTP_201_CREATED,
)
async def criar_comprovacao(
    indicador_id: int,
    etapa_id: int | None = Form(None),
    ano: int = Form(ge=2000, le=2100),
    mes: int = Form(ge=1, le=12),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_permission("/comprovacoes", "criar"),
    unidade_id: int | None = Depends(get_escopo_unidade),
):
    if unidade_id is not None:
        pertence = db.scalar(
            select(1)
            .select_from(models.indicador_unidades)
            .where(
                models.indicador_unidades.c.indicador_id == indicador_id,
                models.indicador_unidades.c.unidade_id == unidade_id,
            )
        )
        if pertence is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Indicador não pertence à sua unidade",
            )
    elif db.get(models.Indicador, indicador_id) is None:
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

    if etapa_id is not None:
        base_query = select(models.Comprovacao).where(
            models.Comprovacao.indicador_id == indicador_id,
            models.Comprovacao.etapa_id == etapa_id,
        )
    else:
        base_query = select(models.Comprovacao).where(
            models.Comprovacao.indicador_id == indicador_id,
            models.Comprovacao.ano == ano,
            models.Comprovacao.mes == mes,
        )
    versao_anterior = db.scalar(
        base_query.order_by(models.Comprovacao.versao.desc()).limit(1)
    )
    proxima_versao = (versao_anterior.versao if versao_anterior else 0) + 1

    comprovacao = models.Comprovacao(
        indicador_id=indicador_id,
        etapa_id=etapa_id,
        usuario_id=_usuario.id,
        versao=proxima_versao,
        ano=ano,
        mes=mes,
        arquivo_nome=nome_original,
        arquivo_caminho=str(caminho_relativo),
    )
    db.add(comprovacao)
    db.flush()

    (_raiz() / caminho_relativo).write_bytes(conteudo)
    db.commit()
    db.refresh(comprovacao)

    indicador = db.get(models.Indicador, indicador_id)
    nome_indicador = indicador.nome if indicador else f"indicador #{indicador_id}"
    nome_etapa = ""
    if etapa_id is not None:
        etapa = db.get(models.IndicadorEtapa, etapa_id)
        if etapa:
            nome_etapa = etapa.nome

    notificados = criar_notificacoes_para_papeis(
        db,
        PAPEIS_GESTOR,
        tipo="comprovacao",
        titulo="Nova comprovação enviada",
        mensagem=(
            f'{_usuario.nome} enviou uma comprovação para o indicador "{nome_indicador}"'
            + (f' — etapa "{nome_etapa}"' if nome_etapa else "")
            + ", aguardando análise."
        ),
        ignorar_usuario_id=_usuario.id,
        entidade_id=comprovacao.id,
    )
    db.commit()

    for usuario_id in notificados:
        notificacoes_stream.notificar_usuario(
            usuario_id,
            {
                "tipo": "comprovacao",
                "titulo": "Nova comprovação enviada",
                "mensagem": (
                    f'{_usuario.nome} enviou uma comprovação para o indicador "{nome_indicador}"'
                    + (f' — etapa "{nome_etapa}"' if nome_etapa else "")
                    + ", aguardando análise."
                ),
            },
        )

    return comprovacao


@router.get("/api/comprovacoes/{comprovacao_id}/arquivo")
def visualizar_comprovacao(
    comprovacao_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm", "default"),
    unidade_id: int | None = Depends(get_escopo_unidade),
):
    comprovacao = db.get(models.Comprovacao, comprovacao_id)
    if comprovacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comprovação não encontrada",
        )
    if unidade_id is not None:
        pertence = db.scalar(
            select(1)
            .select_from(models.indicador_unidades)
            .where(
                models.indicador_unidades.c.indicador_id == comprovacao.indicador_id,
                models.indicador_unidades.c.unidade_id == unidade_id,
            )
        )
        if pertence is None:
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
    _usuario: models.Usuario = require_permission("/comprovacoes", "excluir"),
    unidade_id: int | None = Depends(get_escopo_unidade),
):
    comprovacao = db.get(models.Comprovacao, comprovacao_id)
    if comprovacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comprovação não encontrada",
        )
    if unidade_id is not None:
        pertence = db.scalar(
            select(1)
            .select_from(models.indicador_unidades)
            .where(
                models.indicador_unidades.c.indicador_id == comprovacao.indicador_id,
                models.indicador_unidades.c.unidade_id == unidade_id,
            )
        )
        if pertence is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Comprovação não pertence à sua unidade",
            )
    (_raiz() / comprovacao.arquivo_caminho).unlink(missing_ok=True)

    if comprovacao.status == models.StatusComprovacao.APROVADO:
        indicador = db.get(models.Indicador, comprovacao.indicador_id)
        if indicador and indicador.valor_acumulado > 0:
            indicador.valor_acumulado -= 1

    db.delete(comprovacao)
    db.commit()


def _notificar_dono_status(comprovacao: models.Comprovacao, db: Session) -> None:
    """Notifica o usuário que enviou a comprovação sobre aprovação/rejeição."""
    if comprovacao.usuario_id is None:
        return
    if comprovacao.status not in (
        models.StatusComprovacao.APROVADO,
        models.StatusComprovacao.RECUSADO,
    ):
        return

    indicador = db.get(models.Indicador, comprovacao.indicador_id)
    nome_indicador = indicador.nome if indicador else f"indicador #{comprovacao.indicador_id}"
    nome_etapa = ""
    if comprovacao.etapa_id is not None:
        etapa = db.get(models.IndicadorEtapa, comprovacao.etapa_id)
        if etapa:
            nome_etapa = etapa.nome

    ref = f'"{nome_indicador} — etapa "{nome_etapa}"' if nome_etapa else f'"{nome_indicador}"'
    if comprovacao.status == models.StatusComprovacao.APROVADO:
        titulo = "Comprovação aprovada"
        tipo = "comprovacao_aprovada"
        mensagem = f"Sua comprovação para o indicador {ref} foi aprovada."
    else:
        titulo = "Comprovação rejeitada"
        tipo = "comprovacao_rejeitada"
        just = comprovacao.justificativa or "Justificativa não informada."
        mensagem = f"Sua comprovação para o indicador {ref} foi rejeitada. Justificativa: {just}"

    db.add(
        models.Notificacao(
            usuario_id=comprovacao.usuario_id,
            tipo=tipo,
            titulo=titulo,
            mensagem=mensagem,
            entidade_id=comprovacao.id,
        )
    )
    db.commit()
    notificacoes_stream.notificar_usuario(
        comprovacao.usuario_id,
        {"tipo": tipo, "titulo": titulo, "mensagem": mensagem},
    )


@router.put(
    "/api/comprovacoes/{comprovacao_id}",
    response_model=schemas.ComprovacaoRead,
)
def atualizar_status_comprovacao(
    comprovacao_id: int,
    dados: schemas.ComprovacaoUpdate,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_permission("/validacao", "aprovar"),
    unidade_id: int | None = Depends(get_escopo_unidade),
):
    comprovacao = db.get(models.Comprovacao, comprovacao_id)
    if comprovacao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comprovação não encontrada",
        )
    if unidade_id is not None:
        pertence = db.scalar(
            select(1)
            .select_from(models.indicador_unidades)
            .where(
                models.indicador_unidades.c.indicador_id == comprovacao.indicador_id,
                models.indicador_unidades.c.unidade_id == unidade_id,
            )
        )
        if pertence is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Comprovação não pertence à sua unidade",
            )
    if (
        dados.status == models.StatusComprovacao.RECUSADO
        and not dados.justificativa
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Justificativa é obrigatória para reprovar a comprovação",
        )
    status_aprovado = models.StatusComprovacao.APROVADO
    antigo_aprovado = comprovacao.status == status_aprovado
    novo_aprovado = dados.status == status_aprovado

    comprovacao.status = dados.status
    comprovacao.justificativa = dados.justificativa
    comprovacao.prazo_reenvio = dados.prazo_reenvio

    if novo_aprovado and not antigo_aprovado:
        indicador = db.get(models.Indicador, comprovacao.indicador_id)
        if indicador:
            indicador.valor_acumulado += 1
    elif antigo_aprovado and not novo_aprovado:
        indicador = db.get(models.Indicador, comprovacao.indicador_id)
        if indicador and indicador.valor_acumulado > 0:
            indicador.valor_acumulado -= 1

    db.commit()
    db.refresh(comprovacao)

    _notificar_dono_status(comprovacao, db)

    return comprovacao
