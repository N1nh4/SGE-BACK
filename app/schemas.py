from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ObjetivoCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nome: str = Field(min_length=1, max_length=255)
    descricao: str = Field(min_length=1)
    ppa: str = Field(min_length=1, max_length=255)
    loa: str = Field(min_length=1, max_length=255)


class ObjetivoUpdate(BaseModel):
    codigo: str | None = Field(default=None, max_length=20)
    nome: str | None = Field(default=None, max_length=255)
    descricao: str | None = None
    ppa: str | None = Field(default=None, max_length=255)
    loa: str | None = Field(default=None, max_length=255)


class ObjetivoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nome: str
    descricao: str
    ppa: str
    loa: str
    created_at: datetime
    updated_at: datetime


class IndicadorCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=255)
    meta: str = Field(min_length=1, max_length=255)
    formula: str = Field(min_length=1)
    orientacao: str = Field(min_length=1)
    prazo: date | None = None
    unidade_id: int | None = None


class IniciativaCreate(BaseModel):
    objetivo_id: int
    nome: str = Field(min_length=1, max_length=255)
    indicadores: list[IndicadorCreate] = Field(default_factory=list, min_length=1)


class ObjetivoResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nome: str
    descricao: str
    ppa: str
    loa: str


class UnidadeResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str


class IndicadorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    meta: str
    formula: str
    orientacao: str
    prazo: date | None
    unidade_id: int | None
    unidade: UnidadeResumo | None
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
    ano: int = Field(ge=2000, le=2100)
    mes: int = Field(ge=1, le=12)


class ComprovacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    indicador_id: int
    ano: int
    mes: int
    arquivo_nome: str
    created_at: datetime
    updated_at: datetime
