from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class PapelUsuario(str, Enum):
    MASTER = "master"
    ADM = "adm"
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
    ppa: Mapped[str] = mapped_column(String(255))
    loa: Mapped[str] = mapped_column(String(255))
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
        # TODO: calcular a partir do valor realizado dos indicadores quando
        # houver dados de execução. Enquanto isso, placeholder.
        return 0.0


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


class Indicador(Base):
    __tablename__ = "indicadores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255))
    meta: Mapped[str] = mapped_column(String(255))
    formula: Mapped[str] = mapped_column(Text)
    orientacao: Mapped[str] = mapped_column(Text)
    prazo: Mapped[date | None] = mapped_column(Date, nullable=True)
    unidade_id: Mapped[int | None] = mapped_column(
        ForeignKey("unidades.id"), nullable=True
    )
    iniciativa_id: Mapped[int] = mapped_column(ForeignKey("iniciativas.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )

    iniciativa: Mapped["Iniciativa"] = relationship(back_populates="indicadores")
    unidade: Mapped["Unidade | None"] = relationship()
    comprovacoes: Mapped[list["Comprovacao"]] = relationship(
        back_populates="indicador", cascade="all, delete-orphan"
    )


class Comprovacao(Base):
    __tablename__ = "comprovacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicador_id: Mapped[int] = mapped_column(ForeignKey("indicadores.id"))
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


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    papel: Mapped[PapelUsuario] = mapped_column(
        SqlEnum(PapelUsuario, values_callable=lambda e: [m.value for m in e]),
        default=PapelUsuario.DEFAULT,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )
