import math

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_permission

router = APIRouter(prefix="/api/indicadores", tags=["planejamento"])


def _colaboradores_por_unidade(
    db: Session, unidade_ids: list[int]
) -> dict[int, list[models.Usuario]]:
    """Colaboradores de cada unidade, na ordem do cadastro.

    A mesma pessoa pode estar em mais de uma unidade (usuario_unidades é
    N:N), e nessa situação ela gera uma etapa em cada: são públicos distintos,
    já que a meta é medida por unidade.
    """
    if not unidade_ids:
        return {}

    linhas = db.execute(
        select(
            models.usuario_unidades.c.unidade_id,
            models.Usuario.id,
            models.Usuario.nome,
        )
        .join(models.Usuario, models.Usuario.id == models.usuario_unidades.c.usuario_id)
        .where(models.usuario_unidades.c.unidade_id.in_(unidade_ids))
        .order_by(
            models.usuario_unidades.c.unidade_id,
            models.Usuario.nome,
        )
    ).all()

    por_unidade: dict[int, list[models.Usuario]] = {}
    for unidade_id, usuario_id, nome in linhas:
        # Proxies leves: só o id e o nome são usados para montar a etapa.
        por_unidade.setdefault(unidade_id, []).append(
            models.Usuario(id=usuario_id, nome=nome)
        )
    return por_unidade


@router.post(
    "/{indicador_id}/etapas-colaboradores",
    response_model=schemas.EtapasGeradasRead,
    status_code=status.HTTP_201_CREATED,
)
def gerar_etapas_por_colaborador(
    indicador_id: int,
    dados: schemas.GerarEtapasColaboradores,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_permission("/planejamento", "editar"),
):
    """Cria uma etapa por colaborador nas unidades do indicador.

    A meta de capacitação é medida por colaborador comprovado, e não por
    documento: a etapa é a unidade de prova. Assim a aprovação de uma etapa
    equivale a um colaborador comprovado, e a porcentagem sai da fórmula que
    o sistema já usa (aprovadas / etapas).

    O alvo é calculado por unidade, arredondado para cima. Uma unidade com 6
    pessoas e meta de 80% precisa de 5 aprovações; arredondar o total
    agregado exigiria de uma unidade mais aprovações do que ela tem gente.
    """
    indicador = db.get(models.Indicador, indicador_id)
    if indicador is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Indicador não encontrado",
        )

    unidades = [u.id for u in indicador.unidades]
    if not unidades:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selecione ao menos uma unidade para gerar as etapas",
        )

    colaboradores = _colaboradores_por_unidade(db, unidades)

    # Etapas geradas que já têm aprovação não podem ser removidas: apagar a
    # etapa levaria junto o histórico de comprovação. Elas são preservadas e a
    # pessoa correspondente não entra na lista do que falta gerar, senão a
    # regeneração criaria uma etapa duplicada para o mesmo colaborador.
    etapas_com_aprova = {
        (e.unidade_id, e.colaborador_id)
        for e in db.scalars(
            select(models.IndicadorEtapa).where(
                models.IndicadorEtapa.indicador_id == indicador.id,
                models.IndicadorEtapa.colaborador_id.is_not(None),
                models.IndicadorEtapa.id.in_(
                    select(models.Comprovacao.etapa_id).where(
                        models.Comprovacao.indicador_id == indicador.id,
                        models.Comprovacao.etapa_id.is_not(None),
                        models.Comprovacao.status
                        == models.StatusComprovacao.APROVADO,
                    )
                ),
            )
        )
    }

    removidas = 0
    if dados.substituir:
        a_remover = db.scalars(
            select(models.IndicadorEtapa).where(
                models.IndicadorEtapa.indicador_id == indicador.id,
                models.IndicadorEtapa.colaborador_id.is_not(None),
                models.IndicadorEtapa.id.not_in(
                    select(models.Comprovacao.etapa_id).where(
                        models.Comprovacao.indicador_id == indicador.id,
                        models.Comprovacao.etapa_id.is_not(None),
                        models.Comprovacao.status
                        == models.StatusComprovacao.APROVADO,
                    )
                ),
            )
        ).all()
        for etapa in a_remover:
            db.delete(etapa)
        removidas = len(a_remover)

    alvo_por_unidade: list[schemas.AlvoUnidade] = []
    criadas = 0
    for unidade_id in sorted(colaboradores):
        pessoas = colaboradores[unidade_id]
        if not pessoas:
            continue

        # Arredonda para cima: 80% de 6 pessoas = 5 (4,8 arredonda para baixo
        # e nunca seria possível atingir 100% com meta fracionada).
        alvo = math.ceil(len(pessoas) * dados.percentual_alvo / 100)
        alvo = min(alvo, len(pessoas))

        nome_unidade = db.scalar(
            select(models.Unidade.nome).where(models.Unidade.id == unidade_id)
        )
        alvo_por_unidade.append(
            schemas.AlvoUnidade(
                unidade_id=unidade_id,
                unidade_nome=nome_unidade or "",
                populacao=len(pessoas),
                alvo=alvo,
            )
        )

        for pessoa in pessoas:
            if (unidade_id, pessoa.id) in etapas_com_aprova:
                continue
            db.add(
                models.IndicadorEtapa(
                    indicador_id=indicador.id,
                    nome=pessoa.nome,
                    unidade_id=unidade_id,
                    colaborador_id=pessoa.id,
                )
            )
            criadas += 1

    db.commit()

    if criadas == 0 and alvo_por_unidade == []:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Nenhum colaborador vinculado às unidades do indicador. "
                "Cadastre os colaboradores nas unidades para gerar as etapas."
            ),
        )

    return schemas.EtapasGeradasRead(
        etapas_criadas=criadas,
        etapas_removidas=removidas,
        alvo_por_unidade=alvo_por_unidade,
    )


@router.get(
    "/{indicador_id}/alvo-colaboradores",
    response_model=list[schemas.AlvoUnidade],
)
def prever_alvo_por_unidade(
    indicador_id: int,
    percentual_alvo: float,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = require_permission("/planejamento", "editar"),
):
    """Prévia do alvo por unidade, sem gravar nada.

    O formulário usa esta chamada para mostrar "80% de 6 colaboradores = 5
    etapas" antes de o usuário confirmar a geração.
    """
    if not 0 < percentual_alvo <= 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O percentual deve estar entre 0 e 100",
        )

    indicador = db.get(models.Indicador, indicador_id)
    if indicador is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Indicador não encontrado",
        )

    colaboradores = _colaboradores_por_unidade(
        db, [u.id for u in indicador.unidades]
    )

    previa: list[schemas.AlvoUnidade] = []
    for unidade_id in sorted(colaboradores):
        pessoas = colaboradores[unidade_id]
        if not pessoas:
            continue
        alvo = math.ceil(len(pessoas) * percentual_alvo / 100)
        nome_unidade = db.scalar(
            select(models.Unidade.nome).where(models.Unidade.id == unidade_id)
        )
        previa.append(
            schemas.AlvoUnidade(
                unidade_id=unidade_id,
                unidade_nome=nome_unidade or "",
                populacao=len(pessoas),
                alvo=min(alvo, len(pessoas)),
            )
        )
    return previa
