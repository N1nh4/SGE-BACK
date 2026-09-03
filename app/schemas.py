from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import StatusComprovacao


class ObjetivoCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nome: str = Field(min_length=1, max_length=255)
    ppa: str = Field(min_length=1, max_length=1000)
    loa: str = Field(min_length=1, max_length=1000)


class ObjetivoUpdate(BaseModel):
    codigo: str | None = Field(default=None, max_length=20)
    nome: str | None = Field(default=None, max_length=255)
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
    nome: str = Field(min_length=1, max_length=255)
    meta: str = Field(min_length=1, max_length=255)
    rotulo_x: str = Field(min_length=1, max_length=255)
    rotulo_y: str = Field(min_length=1, max_length=255)
    orientacao: str = Field(min_length=1)
    prazo: date | None = None
    unidade_ids: list[int] = Field(default_factory=list)
    etapas: list[str] = Field(default_factory=list)


class IniciativaCreate(BaseModel):
    objetivo_id: int
    nome: str = Field(min_length=1, max_length=255)
    indicadores: list[IndicadorCreate] = Field(default_factory=list, min_length=1)


class IniciativaUpdate(BaseModel):
    objetivo_id: int | None = None
    nome: str | None = Field(default=None, max_length=255)
    indicadores: list[IndicadorCreate] | None = None


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


class IndicadorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    meta: str
    rotulo_x: str
    rotulo_y: str
    orientacao: str
    prazo: date | None
    unidades: list[UnidadeResumo]
    etapas: list[EtapaRead]
    progresso: float
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
    progresso: float
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
    ano: int
    mes: int
    arquivo_nome: str
    status: StatusComprovacao
    justificativa: str | None
    prazo_reenvio: date | None
    created_at: datetime
    updated_at: datetime


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
    nome: str | None = Field(default=None, max_length=255)


class PropostaEtapaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


class PropostaIndicadorPayload(BaseModel):
    """Indicador de uma proposta. Todos os campos opcionais."""

    id: int | None = None  # presente ao editar um indicador já existente
    nome: str | None = Field(default=None, max_length=255)
    meta: str | None = Field(default=None, max_length=255)
    rotulo_x: str | None = Field(default=None, max_length=255)
    rotulo_y: str | None = Field(default=None, max_length=255)
    orientacao: str | None = None
    prazo: date | None = None
    unidade_ids: list[int] = Field(default_factory=list)
    etapas: list[PropostaIndicadorEtapaCreate] = Field(default_factory=list)


class PropostaCreate(BaseModel):
    """Criação/edição de uma proposta. Todos os campos opcionais."""

    nome: str | None = Field(default=None, max_length=255)
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
