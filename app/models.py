from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


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


class Responsavel(Base):
    __tablename__ = "responsaveis"

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
    responsavel_id: Mapped[int | None] = mapped_column(
        ForeignKey("responsaveis.id"), nullable=True
    )
    iniciativa_id: Mapped[int] = mapped_column(ForeignKey("iniciativas.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )

    iniciativa: Mapped["Iniciativa"] = relationship(back_populates="indicadores")
    responsavel: Mapped["Responsavel | None"] = relationship()
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )

    indicador: Mapped["Indicador"] = relationship(back_populates="comprovacoes")
