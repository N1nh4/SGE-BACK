from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, JSON, String, Table, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


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
    papel: Mapped[str] = mapped_column(String(20), default="default")
    status: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )

    unidades: Mapped[list["Unidade"]] = relationship(
        secondary="usuario_unidades", viewonly=True
    )
    notificacoes: Mapped[list["Notificacao"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )


class Notificacao(Base):
    __tablename__ = "notificacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[str] = mapped_column(String(30))
    titulo: Mapped[str] = mapped_column(String(255))
    mensagem: Mapped[str] = mapped_column(Text)
    lida: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="notificacoes")


usuario_unidades = Table(
    "usuario_unidades",
    Base.metadata,
    Column("usuario_id", ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
    Column("unidade_id", ForeignKey("unidades.id", ondelete="CASCADE"), primary_key=True),
    Column("papel", String(20), nullable=False, default="default"),
)


class Pagina(Base):
    __tablename__ = "paginas"

    id: Mapped[int] = mapped_column(primary_key=True)
    chave: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(255))


class Perfil(Base):
    __tablename__ = "perfis"

    id: Mapped[int] = mapped_column(primary_key=True)
    chave: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(100))

    paginas: Mapped[list["Pagina"]] = relationship(
        secondary="perfil_paginas", viewonly=True
    )


class PerfilPagina(Base):
    __tablename__ = "perfil_paginas"

    perfil_id: Mapped[int] = mapped_column(
        ForeignKey("perfis.id", ondelete="CASCADE"), primary_key=True
    )
    pagina_id: Mapped[int] = mapped_column(
        ForeignKey("paginas.id", ondelete="CASCADE"), primary_key=True
    )
    acoes: Mapped[list] = mapped_column(JSON, default=list)

    pagina: Mapped["Pagina"] = relationship()


# ---------------------------------------------------------------------------
# Propostas de Planejamento (pré-planejamento / rascunho compartilhado)
# ---------------------------------------------------------------------------
# Espelham a estrutura oficial (Iniciativa/Indicador/IndicadorEtapa/unidades),
# porém tudo opcional, pois são rascunhos. Um usuário "default" cria e envia;
# master/adm trabalham em cima do rascunho e, ao final, convertem em
# planejamento oficial.

proposta_indicador_unidades = Table(
    "proposta_indicador_unidades",
    Base.metadata,
    Column(
        "proposta_indicador_id",
        ForeignKey("propostas_indicadores.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "unidade_id",
        ForeignKey("unidades.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class PropostaIniciativa(Base):
    __tablename__ = "propostas_iniciativas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    objetivo_id: Mapped[int | None] = mapped_column(
        ForeignKey("objetivos.id"), nullable=True
    )
    criado_por: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    enviado: Mapped[bool] = mapped_column(default=False)
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    planejamento_id: Mapped[int | None] = mapped_column(
        ForeignKey("iniciativas.id", ondelete="SET NULL"), nullable=True
    )
    criado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
    atualizado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora, onupdate=_agora
    )

    objetivo: Mapped["Objetivo | None"] = relationship()
    criador: Mapped["Usuario | None"] = relationship(
        foreign_keys=[criado_por]
    )
    indicadores: Mapped[list["PropostaIndicador"]] = relationship(
        back_populates="proposta",
        cascade="all, delete-orphan",
        order_by="PropostaIndicador.id",
    )
    planejamento: Mapped["Iniciativa | None"] = relationship()


class PropostaIndicador(Base):
    __tablename__ = "propostas_indicadores"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposta_id: Mapped[int] = mapped_column(
        ForeignKey("propostas_iniciativas.id", ondelete="CASCADE")
    )
    nome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rotulo_x: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rotulo_y: Mapped[str | None] = mapped_column(String(255), nullable=True)
    orientacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    prazo: Mapped[date | None] = mapped_column(Date, nullable=True)

    proposta: Mapped["PropostaIniciativa"] = relationship(
        back_populates="indicadores"
    )
    unidades: Mapped[list["Unidade"]] = relationship(
        secondary=proposta_indicador_unidades, backref="propostas_indicadores"
    )
    etapas: Mapped[list["PropostaIndicadorEtapa"]] = relationship(
        back_populates="indicador", cascade="all, delete-orphan"
    )


class PropostaIndicadorEtapa(Base):
    __tablename__ = "propostas_indicador_etapas"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposta_indicador_id: Mapped[int] = mapped_column(
        ForeignKey("propostas_indicadores.id", ondelete="CASCADE")
    )
    nome: Mapped[str] = mapped_column(String(255))

    indicador: Mapped["PropostaIndicador"] = relationship(
        back_populates="etapas"
    )
