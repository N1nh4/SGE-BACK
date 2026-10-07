from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import StatusComprovacao

# Campos de texto livre no banco são TEXT. O limite existe só para barrar
# entradas absurdas (ex.: colagem gigante), não para cortar texto legítimo.
TEXTO_MAX = 2000


class ObjetivoCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nome: str = Field(min_length=1, max_length=TEXTO_MAX)
    ppa: str = Field(min_length=1, max_length=1000)
    loa: str = Field(min_length=1, max_length=1000)


class ObjetivoUpdate(BaseModel):
    codigo: str | None = Field(default=None, max_length=20)
    nome: str | None = Field(default=None, max_length=TEXTO_MAX)
    ppa: str | None = Field(default=None, max_length=1000)
    loa: str | None = Field(default=None, max_length=1000)


class ObjetivoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nome: str
    ppa: str
    loa: str
    created_at: datetime
    updated_at: datetime


class IndicadorCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=TEXTO_MAX)
    meta: str = Field(min_length=1, max_length=TEXTO_MAX)
    rotulo_x: str = Field(min_length=1, max_length=TEXTO_MAX)
    rotulo_y: str = Field(min_length=1, max_length=TEXTO_MAX)
    orientacao: str = Field(min_length=1)
    prazo: date | None = None
    anual: bool = False
    unidade_ids: list[int] = Field(default_factory=list)
    etapas: list[str] = Field(default_factory=list)


class IniciativaCreate(BaseModel):
    objetivo_id: int
    nome: str = Field(min_length=1, max_length=TEXTO_MAX)
    indicadores: list[IndicadorCreate] = Field(default_factory=list, min_length=1)
    # Ano a que o planejamento pertence. Ausente/sem valor = ano corrente.
    ano: int | None = Field(default=None, ge=2000, le=2100)


class IniciativaUpdate(BaseModel):
    objetivo_id: int | None = None
    nome: str | None = Field(default=None, max_length=TEXTO_MAX)
    indicadores: list[IndicadorCreate] | None = None
    ano: int | None = Field(default=None, ge=2000, le=2100)


class ObjetivoResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nome: str
    ppa: str
    loa: str


class UnidadeResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


class EtapaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    # Preenchidos apenas em etapa gerada por colaborador.
    unidade_id: int | None = None
    colaborador_id: int | None = None


class AlvoUnidade(BaseModel):
    unidade_id: int
    unidade_nome: str
    populacao: int
    alvo: int


class GerarEtapasColaboradores(BaseModel):
    """Gera uma etapa por colaborador nas unidades do indicador.

    O alvo é calculado por unidade: 80% de uma unidade com 6 pessoas exige 5
    aprovações (arredondado para cima), e não 80% do total somado. Arredondar
    por unidade evita exigir de uma unidade um número maior que a sua população.
    """

    percentual_alvo: float = Field(gt=0, le=100)
    # Quando verdadeiro, remove as etapas geradas antes para regerar a lista
    # sem duplicar. Etapas com comprovação aprovada não são removidas.
    substituir: bool = True


class EtapasGeradasRead(BaseModel):
    etapas_criadas: int
    etapas_removidas: int
    # Alvo de aprovações por unidade (id, nome, populacao, alvo).
    alvo_por_unidade: list[AlvoUnidade]


class IndicadorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    meta: str
    rotulo_x: str
    rotulo_y: str
    orientacao: str
    prazo: date | None
    anual: bool
    prazo_efetivo: date | None
    unidades: list[UnidadeResumo]
    etapas: list[EtapaRead]
    # Denominador do progresso. Nulo nas etapas manuais: aí o progresso é
    # aprovadas / etapas; quando definido, é aprovadas / alvo (pode passar
    # de 100%).
    percentual_alvo: float | None = None
    alvo: int | None = None
    progresso: float | None
    created_at: datetime
    updated_at: datetime


class UnidadeCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=255)


class UnidadeUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=255)


class UnidadeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    created_at: datetime
    updated_at: datetime


class IniciativaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    ano: int
    progresso: float | None
    objetivo: ObjetivoResumo
    indicadores: list[IndicadorRead]
    created_at: datetime
    updated_at: datetime


class ComprovacaoCreate(BaseModel):
    etapa_id: int | None = None
    ano: int = Field(ge=2000, le=2100)
    mes: int = Field(ge=1, le=12)


class ComprovacaoUpdate(BaseModel):
    status: StatusComprovacao
    justificativa: str | None = None
    prazo_reenvio: date | None = None


class ComprovacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    indicador_id: int
    etapa_id: int | None
    usuario_id: int | None
    versao: int
    ano: int
    mes: int
    arquivo_nome: str
    status: StatusComprovacao
    justificativa: str | None
    prazo_reenvio: date | None
    created_at: datetime
    updated_at: datetime


class ComprovacaoContextoRead(BaseModel):
    unidade_id: int
    planejamento_id: int
    indicador_id: int
    mes: int
    ano: int


class UsuarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    papel: str
    status: int
    created_at: datetime
    updated_at: datetime


class NotificacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    tipo: str
    titulo: str
    mensagem: str
    lida: bool
    created_at: datetime
    entidade_id: int | None = None


class UnidadeLogin(BaseModel):
    id: int
    nome: str
    papel: str


class PaginaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chave: str
    nome: str


class PaginaComAcoes(BaseModel):
    chave: str
    acoes: list[str]


class AcaoDisponivel(BaseModel):
    chave: str
    nome: str


class PaginaCatalogo(BaseModel):
    chave: str
    nome: str
    acoes: list[AcaoDisponivel]


class PerfilPaginaItem(BaseModel):
    pagina_id: int
    acoes: list[str]


class PerfilRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chave: str
    nome: str
    paginas: list[PaginaRead]


class PerfilCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=100)


class PerfilUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=100)


class PerfilPaginaUpdate(BaseModel):
    paginas: list["PerfilPaginaItem"]


class PerfilPaginaAcoesUpdate(BaseModel):
    perfil_id: int
    pagina_id: int
    acoes: list[str]


class LoginRequest(BaseModel):
    email: str
    senha: str


class LoginResponse(BaseModel):
    token: str
    usuario: UsuarioRead
    unidades: list[UnidadeLogin]
    paginas: list[PaginaComAcoes]


class SelecionarUnidadeRequest(BaseModel):
    unidade_id: int


class SelecionarUnidadeResponse(BaseModel):
    token: str
    usuario: UsuarioRead
    unidade_id: int
    papel: str
    paginas: list[PaginaComAcoes]


class MeResponse(BaseModel):
    usuario: UsuarioRead
    unidades: list[UnidadeLogin]
    unidade_id: int | None
    papel: str
    paginas: list[PaginaComAcoes]


class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    senha: str = Field(min_length=6, max_length=255)
    papel: str = "default"
    unidade_id: int | None = None
    status: int = 1


class UsuarioUpdate(BaseModel):
    nome: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    senha: str | None = Field(default=None, min_length=6, max_length=255)
    papel: str | None = None
    unidade_id: int | None = None
    status: int | None = None


class PropostaIndicadorEtapaCreate(BaseModel):
    nome: str | None = Field(default=None, max_length=TEXTO_MAX)


class PropostaEtapaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


class PropostaIndicadorPayload(BaseModel):
    """Indicador de uma proposta. Todos os campos opcionais."""

    id: int | None = None  # presente ao editar um indicador já existente
    nome: str | None = Field(default=None, max_length=TEXTO_MAX)
    meta: str | None = Field(default=None, max_length=TEXTO_MAX)
    rotulo_x: str | None = Field(default=None, max_length=TEXTO_MAX)
    rotulo_y: str | None = Field(default=None, max_length=TEXTO_MAX)
    orientacao: str | None = None
    prazo: date | None = None
    anual: bool = False
    unidade_ids: list[int] = Field(default_factory=list)
    etapas: list[PropostaIndicadorEtapaCreate] = Field(default_factory=list)


class PropostaCreate(BaseModel):
    """Criação/edição de uma proposta. Todos os campos opcionais."""

    nome: str | None = Field(default=None, max_length=TEXTO_MAX)
    objetivo_id: int | None = None
    indicadores: list[PropostaIndicadorPayload] = Field(default_factory=list)


class PropostaIndicadorEtapaAlias(BaseModel):
    id: int | None = None
    nome: str


class PropostaUnidadeResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


class PropostaObjetivoResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nome: str


class PropostaIndicadorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str | None
    meta: str | None
    rotulo_x: str | None
    rotulo_y: str | None
    orientacao: str | None
    prazo: date | None
    anual: bool
    prazo_efetivo: date | None
    unidades: list[PropostaUnidadeResumo]
    etapas: list[PropostaEtapaRead]


class PropostaAutor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


class PropostaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str | None
    enviado: bool
    criado_por: int | None
    criador: PropostaAutor | None
    criado_at: datetime
    atualizado_at: datetime
    objetivo: PropostaObjetivoResumo | None
    indicadores: list[PropostaIndicadorRead]
