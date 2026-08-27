from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..database import get_db
from ..deps import get_escopo_unidade, require_permission, require_role
from .notificacoes import criar_notificacoes_para_unidade

router = APIRouter(prefix="/api/planejamento", tags=["planejamento"])


def _unidades_atribuidas(dados) -> list[int]:
    unidade_ids: set[int] = set()
    for ind in dados.indicadores:
        unidade_ids.update(ind.unidade_ids or [])
    return sorted(unidade_ids)


def _opcoes():
    return (
        selectinload(models.Iniciativa.objetivo),
        selectinload(models.Iniciativa.indicadores),
        selectinload(models.Iniciativa.indicadores).selectinload(
            models.Indicador.unidades
        ),
        selectinload(models.Iniciativa.indicadores).selectinload(
            models.Indicador.etapas
        ),
    )


@router.get("", response_model=list[schemas.IniciativaRead])
def listar_planejamento(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm", "default"),
    unidade_id: int | None = Depends(get_escopo_unidade),
):
    if unidade_id is None:
        return db.scalars(
            select(models.Iniciativa)
            .options(*_opcoes())
            .order_by(models.Iniciativa.id)
        ).all()

    iniciativa_ids = (
        select(models.Indicador.iniciativa_id)
        .join(
            models.indicador_unidades,
            models.indicador_unidades.c.indicador_id == models.Indicador.id,
        )
        .where(models.indicador_unidades.c.unidade_id == unidade_id)
    )
    return db.scalars(
        select(models.Iniciativa)
        .where(models.Iniciativa.id.in_(iniciativa_ids))
        .options(*_opcoes())
        .order_by(models.Iniciativa.id)
    ).all()


@router.get("/{iniciativa_id}", response_model=schemas.IniciativaRead)
def obter_planejamento(
    iniciativa_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_role("master", "adm", "default"),
    unidade_id: int | None = Depends(get_escopo_unidade),
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
    if unidade_id is not None:
        pertence = db.scalar(
            select(1)
            .select_from(models.Indicador)
            .join(
                models.indicador_unidades,
                models.indicador_unidades.c.indicador_id == models.Indicador.id,
            )
            .where(
                models.Indicador.iniciativa_id == iniciativa_id,
                models.indicador_unidades.c.unidade_id == unidade_id,
            )
        )
        if pertence is None:
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
    _usuario: models.Usuario = require_permission("/planejamento", "criar"),
    unidade_id: int | None = Depends(get_escopo_unidade),
):
    if db.get(models.Objetivo, dados.objetivo_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objetivo estratégico não encontrado",
        )

    if unidade_id is not None:
        for ind_dados in dados.indicadores:
            if ind_dados.unidade_ids and set(ind_dados.unidade_ids) != {unidade_id}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Você só pode definir sua unidade como responsável",
                )

    indicadores = []
    for ind_dados in dados.indicadores:
        dump = ind_dados.model_dump()
        unidade_ids = dump.pop("unidade_ids", [])
        etapas_nomes = dump.pop("etapas", [])
        indicador = models.Indicador(**dump)
        if unidade_ids:
            indicador.unidades = list(
                db.scalars(
                    select(models.Unidade).where(
                        models.Unidade.id.in_(unidade_ids)
                    )
                ).all()
            )
        for nome_etapa in etapas_nomes:
            indicador.etapas.append(models.IndicadorEtapa(nome=nome_etapa))
        indicadores.append(indicador)

    iniciativa = models.Iniciativa(
        nome=dados.nome,
        objetivo_id=dados.objetivo_id,
        indicadores=indicadores,
    )
    db.add(iniciativa)
    db.flush()

    criar_notificacoes_para_unidade(
        db,
        _unidades_atribuidas(dados),
        tipo="planejamento",
        titulo="Novo planejamento",
        mensagem=f'Você foi definido(a) como responsável pela iniciativa "{dados.nome}".',
        ignorar_usuario_id=_usuario.id,
    )

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
    _usuario: models.Usuario = require_permission("/planejamento", "editar"),
    unidade_id: int | None = Depends(get_escopo_unidade),
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

    if unidade_id is not None:
        pertence = db.scalar(
            select(1)
            .select_from(models.Indicador)
            .join(
                models.indicador_unidades,
                models.indicador_unidades.c.indicador_id == models.Indicador.id,
            )
            .where(
                models.Indicador.iniciativa_id == iniciativa_id,
                models.indicador_unidades.c.unidade_id == unidade_id,
            )
        )
        if pertence is None:
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

    if unidade_id is not None and "indicadores" in campos:
        for ind_dados in campos["indicadores"]:
            if ind_dados.unidade_ids and set(ind_dados.unidade_ids) != {unidade_id}:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Você só pode definir sua unidade como responsável",
                )

    if "nome" in campos:
        iniciativa.nome = campos["nome"]
    if "objetivo_id" in campos:
        iniciativa.objetivo_id = campos["objetivo_id"]
    if "indicadores" in campos:
        novos_indicadores = []
        for ind_dados in campos["indicadores"]:
            unidade_ids = ind_dados.pop("unidade_ids", [])
            etapas_nomes = ind_dados.pop("etapas", [])
            indicador = models.Indicador(**ind_dados)
            if unidade_ids:
                indicador.unidades = list(
                    db.scalars(
                        select(models.Unidade).where(
                            models.Unidade.id.in_(unidade_ids)
                        )
                    ).all()
                )
            for nome_etapa in etapas_nomes:
                indicador.etapas.append(models.IndicadorEtapa(nome=nome_etapa))
            novos_indicadores.append(indicador)
        iniciativa.indicadores = novos_indicadores

    if "indicadores" in campos:
        criar_notificacoes_para_unidade(
            db,
            _unidades_atribuidas(dados),
            tipo="planejamento",
            titulo="Planejamento atualizado",
            mensagem=f'Você foi definido(a) como responsável pela iniciativa "{iniciativa.nome}".',
            ignorar_usuario_id=_usuario.id,
        )

    db.commit()
    return db.scalar(
        select(models.Iniciativa)
        .where(models.Iniciativa.id == iniciativa.id)
        .options(*_opcoes())
    )


@router.delete("/{iniciativa_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_planejamento(
    iniciativa_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_permission("/planejamento", "excluir"),
):
    iniciativa = db.get(models.Iniciativa, iniciativa_id)
    if iniciativa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Planejamento não encontrado",
        )
    db.delete(iniciativa)
    db.commit()
