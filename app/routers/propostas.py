from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..database import get_db
from ..deps import get_usuario_atual
from ..services import notificacoes_stream
from .notificacoes import criar_notificacoes_para_papeis

router = APIRouter(prefix="/api/propostas", tags=["propostas"])

PAPEIS_GESTOR = ["master", "adm", "teste"]


def _eh_gestor(usuario: models.Usuario) -> bool:
    """Usuários não-default podem trabalhar em cima de propostas enviadas."""
    return usuario.papel in PAPEIS_GESTOR


def _opcoes():
    return (
        selectinload(models.PropostaIniciativa.objetivo),
        selectinload(models.PropostaIniciativa.criador),
        selectinload(models.PropostaIniciativa.indicadores).selectinload(
            models.PropostaIndicador.unidades
        ),
        selectinload(models.PropostaIniciativa.indicadores).selectinload(
            models.PropostaIndicador.etapas
        ),
    )


def _buscar_proposta(proposta_id: int, db: Session) -> models.PropostaIniciativa:
    proposta = db.scalar(
        select(models.PropostaIniciativa)
        .where(models.PropostaIniciativa.id == proposta_id)
        .options(*_opcoes())
    )
    if proposta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposta não encontrada",
        )
    return proposta


def _aplicar_dados(
    db: Session,
    proposta: models.PropostaIniciativa,
    dados: schemas.PropostaCreate,
    autor: models.Usuario,
):
    """Grava os campos da proposta a partir do payload (tudo opcional)."""
    if dados.nome is not None:
        proposta.nome = dados.nome
    if dados.objetivo_id is not None:
        if db.get(models.Objetivo, dados.objetivo_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Objetivo estratégico não encontrado",
            )
        proposta.objetivo_id = dados.objetivo_id
    proposta.updated_by = autor.id

    if dados.indicadores is not None:
        novos = []
        for ind_dados in dados.indicadores:
            dump = ind_dados.model_dump(exclude={"etapas"})
            unidade_ids = dump.pop("unidade_ids", [])
            etapas_payload = ind_dados.etapas
            ind_id = dump.pop("id", None)

            if ind_id is not None:
                indicador = db.get(models.PropostaIndicador, ind_id)
                if indicador is None or indicador.proposta_id != proposta.id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Indicador de proposta inválido",
                    )
                for campo, valor in dump.items():
                    setattr(indicador, campo, valor)
            else:
                indicador = models.PropostaIndicador(**dump)
                proposta.indicadores.append(indicador)

            if unidade_ids:
                indicador.unidades = list(
                    db.scalars(
                        select(models.Unidade).where(
                            models.Unidade.id.in_(unidade_ids)
                        )
                    ).all()
                )
            else:
                indicador.unidades = []

            indicador.etapas = []
            for etapa_payload in etapas_payload:
                if etapa_payload.nome:
                    indicador.etapas.append(
                        models.PropostaIndicadorEtapa(nome=etapa_payload.nome)
                    )
            novos.append(indicador)
        proposta.indicadores = novos


@router.get("/mine", response_model=list[schemas.PropostaRead])
def listar_minhas_propostas(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(get_usuario_atual),
):
    """Propostas criadas pelo usuário logado (rascunhos e enviadas)."""
    return db.scalars(
        select(models.PropostaIniciativa)
        .where(models.PropostaIniciativa.criado_por == _usuario.id)
        .options(*_opcoes())
        .order_by(models.PropostaIniciativa.id.desc())
    ).all()


@router.get("/pending", response_model=list[schemas.PropostaRead])
def listar_propostas_gestor(
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(get_usuario_atual),
):
    """Propostas enviadas, ainda não convertidas, para master/adm/teste."""
    if not _eh_gestor(_usuario):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para acessar propostas recebidas",
        )
    return db.scalars(
        select(models.PropostaIniciativa)
        .where(
            models.PropostaIniciativa.enviado.is_(True),
            models.PropostaIniciativa.planejamento_id.is_(None),
        )
        .options(*_opcoes())
        .order_by(models.PropostaIniciativa.id.desc())
    ).all()


@router.get("/{proposta_id}", response_model=schemas.PropostaRead)
def obter_proposta(
    proposta_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(get_usuario_atual),
):
    """Detalhe de uma proposta.

    Acesso: o dono sempre; gestores em qualquer proposta; os demais somente
    propostas já enviadas e ainda não convertidas.
    """
    proposta = _buscar_proposta(proposta_id, db)
    if proposta.criado_por == _usuario.id or _eh_gestor(_usuario):
        return proposta
    if proposta.enviado and proposta.planejamento_id is None:
        return proposta
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Sem permissão para ver esta proposta",
    )


@router.post(
    "",
    response_model=schemas.PropostaRead,
    status_code=status.HTTP_201_CREATED,
)
def criar_proposta(
    dados: schemas.PropostaCreate,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(get_usuario_atual),
):
    """Cria um rascunho de proposta de planejamento."""
    proposta = models.PropostaIniciativa(criado_por=_usuario.id)
    _aplicar_dados(db, proposta, dados, _usuario)
    db.add(proposta)
    db.commit()
    return _buscar_proposta(proposta.id, db)


@router.put("/{proposta_id}", response_model=schemas.PropostaRead)
def atualizar_proposta(
    proposta_id: int,
    dados: schemas.PropostaCreate,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(get_usuario_atual),
):
    """Edita a proposta.

    - Dono: pode editar enquanto for rascunho (não enviada).
    - Gestores (master/adm/teste): podem editar qualquer proposta já enviada
      para trabalhar em cima dela.
    """
    proposta = _buscar_proposta(proposta_id, db)
    eh_dono = proposta.criado_por == _usuario.id

    if eh_dono:
        if proposta.enviado:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rascunho já enviado; você não pode mais editar",
            )
    elif not _eh_gestor(_usuario):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para editar esta proposta",
        )

    _aplicar_dados(db, proposta, dados, _usuario)
    db.commit()
    return _buscar_proposta(proposta_id, db)


@router.post("/{proposta_id}/enviar", response_model=schemas.PropostaRead)
def enviar_proposta(
    proposta_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(get_usuario_atual),
):
    """Envia o rascunho. A partir daqui o dono não pode mais editar, e os
    gestores são notificados."""
    proposta = _buscar_proposta(proposta_id, db)
    if proposta.criado_por != _usuario.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você só pode enviar suas próprias propostas",
        )
    if proposta.enviado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proposta já enviada",
        )

    proposta.enviado = True

    notificados = criar_notificacoes_para_papeis(
        db,
        PAPEIS_GESTOR,
        tipo="proposta",
        titulo="Nova proposta de planejamento",
        mensagem=f'{_usuario.nome} enviou uma proposta de planejamento ("{proposta.nome or "sem título"}").',
        ignorar_usuario_id=_usuario.id,
    )

    db.commit()

    for usuario_id in notificados:
        notificacoes_stream.notificar_usuario(
            usuario_id,
            {
                "tipo": "proposta",
                "titulo": "Nova proposta de planejamento",
                "proposta_id": proposta.id,
            },
        )

    return _buscar_proposta(proposta_id, db)


@router.post("/{proposta_id}/converter", response_model=schemas.IniciativaRead)
def converter_proposta(
    proposta_id: int,
    db: Session = Depends(get_db),
    _usuario: models.Usuario = Depends(get_usuario_atual),
):
    """Converte a proposta enviada em planejamento oficial.

    Exige objetivo e pelo menos os campos obrigatórios do planejamento.
    A proposta deixa de aparecer na lista de pendências (ganha planejamento_id).
    """
    if not _eh_gestor(_usuario):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para converter propostas",
        )

    proposta = _buscar_proposta(proposta_id, db)
    if not proposta.enviado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A proposta precisa ser enviada antes de virar planejamento",
        )
    if proposta.planejamento_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta proposta já foi convertida",
        )
    if not proposta.nome or not proposta.objetivo_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A proposta precisa ter nome e objetivo antes de virar planejamento",
        )
    if not proposta.indicadores:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A proposta precisa ter ao menos um indicador",
        )

    novos_indicadores = []
    for p_ind in proposta.indicadores:
        if not (p_ind.nome and p_ind.meta and p_ind.rotulo_x and p_ind.rotulo_y and p_ind.orientacao):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Todos os indicadores precisam de nome, meta, rótulos e orientação",
            )
        indicador = models.Indicador(
            nome=p_ind.nome,
            meta=p_ind.meta,
            rotulo_x=p_ind.rotulo_x,
            rotulo_y=p_ind.rotulo_y,
            orientacao=p_ind.orientacao,
            prazo=p_ind.prazo,
            unidades=p_ind.unidades,
        )
        for p_etapa in p_ind.etapas:
            indicador.etapas.append(models.IndicadorEtapa(nome=p_etapa.nome))
        novos_indicadores.append(indicador)

    iniciativa = models.Iniciativa(
        nome=proposta.nome,
        objetivo_id=proposta.objetivo_id,
        indicadores=novos_indicadores,
    )
    db.add(iniciativa)
    db.flush()

    proposta.planejamento_id = iniciativa.id
    db.commit()

    return db.scalar(
        select(models.Iniciativa)
        .where(models.Iniciativa.id == iniciativa.id)
        .options(
            selectinload(models.Iniciativa.objetivo),
            selectinload(models.Iniciativa.indicadores).selectinload(
                models.Indicador.unidades
            ),
            selectinload(models.Iniciativa.indicadores).selectinload(
                models.Indicador.etapas
            ),
        )
    )