from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class PapelUsuario(str, Enum):
    MASTER = "master"
    ADM = "adm"
    PONTO_FOCAL = "ponto_focal"
    DEFAULT = "default"


class StatusComprovacao(str, Enum):
    ANALISE = "analise"
    APROVADO = "aprovado"
    RECUSADO = "recusado"


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class Objetivo(Base):
    __tablename__ = "objetivos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(255))
    descricao: Mapped[str] = mapped_column(Text)
    ppa: Mapped[str] = mapped_column(String(1000))
    loa: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )

    iniciativas: Mapped[list["Iniciativa"]] = relationship(
        back_populates="objetivo", cascade="all, delete-orphan"
    )


class Iniciativa(Base):
    __tablename__ = "iniciativas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255))
    objetivo_id: Mapped[int] = mapped_column(ForeignKey("objetivos.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )

    objetivo: Mapped["Objetivo"] = relationship(back_populates="iniciativas")
    indicadores: Mapped[list["Indicador"]] = relationship(
        back_populates="iniciativa", cascade="all, delete-orphan"
    )

    @property
    def progresso(self) -> float:
        indicadores = self.indicadores
        if not indicadores:
            return 0.0
        total = sum(len(i.etapas) for i in indicadores)
        if total == 0:
            return 0.0
        acumulado = sum(i.valor_acumulado for i in indicadores)
        return round((acumulado / total) * 100, 1)


indicador_unidades = Table(
    "indicador_unidades",
    Base.metadata,
    Column("indicador_id", ForeignKey("indicadores.id", ondelete="CASCADE"), primary_key=True),
    Column("unidade_id", ForeignKey("unidades.id", ondelete="CASCADE"), primary_key=True),
)


class Unidade(Base):
    __tablename__ = "unidades"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )

    indicadores: Mapped[list["Indicador"]] = relationship(
        secondary=indicador_unidades, back_populates="unidades"
    )


class Indicador(Base):
    __tablename__ = "indicadores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255))
    meta: Mapped[str] = mapped_column(String(255))
    rotulo_x: Mapped[str] = mapped_column(String(255))
    rotulo_y: Mapped[str] = mapped_column(String(255))
    orientacao: Mapped[str] = mapped_column(Text)
    prazo: Mapped[date | None] = mapped_column(Date, nullable=True)
    valor_acumulado: Mapped[float] = mapped_column(default=0.0)
    iniciativa_id: Mapped[int] = mapped_column(ForeignKey("iniciativas.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )

    iniciativa: Mapped["Iniciativa"] = relationship(back_populates="indicadores")
    unidades: Mapped[list["Unidade"]] = relationship(
        secondary=indicador_unidades, back_populates="indicadores"
    )
    comprovacoes: Mapped[list["Comprovacao"]] = relationship(
        back_populates="indicador", cascade="all, delete-orphan"
    )
    etapas: Mapped[list["IndicadorEtapa"]] = relationship(
        back_populates="indicador", cascade="all, delete-orphan"
    )

    @property
    def progresso(self) -> float:
        total = len(self.etapas)
        if total == 0:
            return 0.0
        return round((self.valor_acumulado / total) * 100, 1)


class IndicadorEtapa(Base):
    __tablename__ = "indicador_etapas"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicador_id: Mapped[int] = mapped_column(ForeignKey("indicadores.id", ondelete="CASCADE"))
    nome: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )

    indicador: Mapped["Indicador"] = relationship(back_populates="etapas")


class Comprovacao(Base):
    __tablename__ = "comprovacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicador_id: Mapped[int] = mapped_column(ForeignKey("indicadores.id"))
    etapa_id: Mapped[int | None] = mapped_column(
        ForeignKey("indicador_etapas.id", ondelete="SET NULL"), nullable=True
    )
    ano: Mapped[int] = mapped_column(Integer)
    mes: Mapped[int] = mapped_column(Integer)
    arquivo_nome: Mapped[str] = mapped_column(String(255))
    arquivo_caminho: Mapped[str] = mapped_column(String(500))
    status: Mapped[StatusComprovacao] = mapped_column(
        SqlEnum(
            StatusComprovacao, values_callable=lambda e: [m.value for m in e]
        ),
        default=StatusComprovacao.ANALISE,
    )
    justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    prazo_reenvio: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )

    indicador: Mapped["Indicador"] = relationship(back_populates="comprovacoes")
    etapa: Mapped["IndicadorEtapa | None"] = relationship()


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    papel: Mapped[PapelUsuario] = mapped_column(
        SqlEnum(PapelUsuario, values_callable=lambda e: [m.value for m in e]),
        default=PapelUsuario.DEFAULT,
    )
    unidade_id: Mapped[int | None] = mapped_column(
        ForeignKey("unidades.id"), nullable=True
    )
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )

    unidade: Mapped["Unidade | None"] = relationship()
