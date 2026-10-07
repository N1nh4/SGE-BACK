from datetime import date, datetime, timezone
from enum import Enum
import math

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Table, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class StatusComprovacao(str, Enum):
    ANALISE = "analise"
    APROVADO = "aprovado"
    RECUSADO = "recusado"
    SEM_ATUALIZACAO = "sem_atualizacao"


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _prazo_no_ciclo(prazo: date | None, anual: bool) -> date | None:
    """Reaplica o mesmo dia/mês no ano corrente quando o indicador é anual,
    para que o prazo ande sozinho na virada do ano."""
    if prazo is None or not anual:
        return prazo
    ano = date.today().year
    try:
        return date(ano, prazo.month, prazo.day)
    except ValueError:
        # 29 de fevereiro em ano não bissexto: cai para 28.
        return date(ano, 2, 28)


class Objetivo(Base):
    __tablename__ = "objetivos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    nome: Mapped[str] = mapped_column(Text)
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
    nome: Mapped[str] = mapped_column(Text)
    objetivo_id: Mapped[int] = mapped_column(ForeignKey("objetivos.id"))
    # Ano a que o planejamento pertence. Planejamento com indicador "cíclico
    # anual" continua valendo nos anos seguintes, então o filtro por ano mostra
    # quem tem ano == selecionado OU algum indicador anual.
    ano: Mapped[int] = mapped_column(Integer, default=lambda: date.today().year)
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
    def progresso(self) -> float | None:
        indicadores = self.indicadores
        if not indicadores:
            return 0.0
        # Indicador sem denominador não pode entrar nem no numerador nem no
        # denominador. Se entrasse só no numerador, um único documento
        # aprovado em indicador sem etapas faria a iniciativa passar de 100%.
        # Cada indicador entra com o seu próprio denominador: os medidos por
        # colaborador pesam pelo alvo, os demais pelo total de etapas.
        total = 0
        acumulado = 0.0
        for indicador in indicadores:
            denominador = indicador.denominador_progresso
            if denominador == 0:
                continue
            total += denominador
            acumulado += indicador.acumulado_efetivo
        if total == 0:
            return 0.0
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
    nome: Mapped[str] = mapped_column(Text)
    meta: Mapped[str] = mapped_column(Text)
    rotulo_x: Mapped[str] = mapped_column(Text)
    rotulo_y: Mapped[str] = mapped_column(Text)
    orientacao: Mapped[str] = mapped_column(Text)
    prazo: Mapped[date | None] = mapped_column(Date, nullable=True)
    anual: Mapped[bool] = mapped_column(Boolean, default=False)
    ano_ciclo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valor_acumulado: Mapped[float] = mapped_column(default=0.0)
    # Percentual pedido na geração de etapas por colaborador (50 = "50% dos
    # colaboradores ativos"). Nulo nas etapas cadastradas manualmente ou nas
    # geradas antes desta regra: nesses casos o denominador é o total de etapas.
    percentual_alvo: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    def prazo_efetivo(self) -> date | None:
        """Prazo do ciclo vigente. Em indicador anual o mesmo dia/mês é
        reaplicado no ano corrente, então o prazo anda sozinho na virada."""
        return _prazo_no_ciclo(self.prazo, self.anual)

    @property
    def acumulado_efetivo(self) -> float:
        """Valor acumulado do ciclo vigente. Em indicador anual, um ano novo
        começa zerado: o contador só volta a andar na primeira aprovação do
        novo ano. O valor do ano anterior não é apagado — ele continua em
        valor_acumulado/ano_ciclo e é reconstruível pelas comprovações
        aprovadas daquele ano."""
        if self.anual and (
            self.ano_ciclo is None or self.ano_ciclo < date.today().year
        ):
            return 0.0
        return self.valor_acumulado

    @property
    def alvo(self) -> int | None:
        """Alvo de aprovações quando a meta é medida por colaborador.

        Indicador medido por colaborador não conta etapas, conta alvo: a meta
        "50% dos 6 colaboradores ativos" exige 3 aprovações, não 6. O alvo é
        recalculado por unidade e arredondado para cima, para que nenhuma
        unidade precise de mais aprovações do que ela tem gente.

        Pessoas inativas ficam de fora da população, mas as etapas delas
        continuam existindo — elas apenas não pesam. Nada aqui limita o
        progresso a 100%: quem comprova 6 de 6 com meta de 50% está em 200%.

        None nas etapas manuais ou nas geradas antes desta regra: aí o que se
        conta é aprovadas / etapas e não há alvo a informar.
        """
        if self.percentual_alvo is None:
            return None

        por_unidade: dict[int | None, int] = {}
        for etapa in self.etapas:
            colaborador = etapa.colaborador
            if colaborador is not None and colaborador.status != 1:
                continue
            por_unidade[etapa.unidade_id] = por_unidade.get(etapa.unidade_id, 0) + 1

        return sum(
            math.ceil(quantidade * self.percentual_alvo / 100)
            for quantidade in por_unidade.values()
        )

    @property
    def denominador_progresso(self) -> int:
        """O que o progresso deste indicador precisa atingir: o alvo, ou o
        total de etapas quando a meta não é medida por colaborador."""
        alvo = self.alvo
        if alvo is not None:
            return alvo
        return len(self.etapas)

    @property
    def progresso(self) -> float | None:
        # Sem denominador não existe progresso a calcular. Devolver 0 seria
        # mentir: o indicador não está em 0%, está sem forma de ser medido.
        # None é o que a tela traduz como "—".
        total = self.denominador_progresso
        if total == 0:
            return None
        return round((self.acumulado_efetivo / total) * 100, 1)


class IndicadorEtapa(Base):
    __tablename__ = "indicador_etapas"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicador_id: Mapped[int] = mapped_column(ForeignKey("indicadores.id", ondelete="CASCADE"))
    nome: Mapped[str] = mapped_column(Text)
    # Etapa gerada por colaborador carrega a unidade de origem, para que cada
    # setor comprove só os seus. Nulo em etapa cadastrada manualmente.
    unidade_id: Mapped[int | None] = mapped_column(
        ForeignKey("unidades.id", ondelete="CASCADE"), nullable=True
    )
    # Referência ao colaborador que originou a etapa, quando gerada. Preserva a
    # origem mesmo se o nome do colaborador mudar depois.
    colaborador_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )

    indicador: Mapped["Indicador"] = relationship(back_populates="etapas")
    unidade: Mapped["Unidade | None"] = relationship()
    colaborador: Mapped["Usuario | None"] = relationship()


class Comprovacao(Base):
    __tablename__ = "comprovacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    indicador_id: Mapped[int] = mapped_column(ForeignKey("indicadores.id"))
    etapa_id: Mapped[int | None] = mapped_column(
        ForeignKey("indicador_etapas.id", ondelete="SET NULL"), nullable=True
    )
    usuario_id: Mapped[int | None] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    versao: Mapped[int] = mapped_column(Integer, default=1)
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
    usuario: Mapped["Usuario | None"] = relationship()


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
    entidade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    nome: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    nome: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)
    rotulo_x: Mapped[str | None] = mapped_column(Text, nullable=True)
    rotulo_y: Mapped[str | None] = mapped_column(Text, nullable=True)
    orientacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    prazo: Mapped[date | None] = mapped_column(Date, nullable=True)
    anual: Mapped[bool] = mapped_column(Boolean, default=False)

    proposta: Mapped["PropostaIniciativa"] = relationship(
        back_populates="indicadores"
    )
    unidades: Mapped[list["Unidade"]] = relationship(
        secondary=proposta_indicador_unidades, backref="propostas_indicadores"
    )
    etapas: Mapped[list["PropostaIndicadorEtapa"]] = relationship(
        back_populates="indicador", cascade="all, delete-orphan"
    )

    @property
    def prazo_efetivo(self) -> date | None:
        return _prazo_no_ciclo(self.prazo, self.anual)


class PropostaIndicadorEtapa(Base):
    __tablename__ = "propostas_indicador_etapas"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposta_indicador_id: Mapped[int] = mapped_column(
        ForeignKey("propostas_indicadores.id", ondelete="CASCADE")
    )
    nome: Mapped[str] = mapped_column(Text)

    indicador: Mapped["PropostaIndicador"] = relationship(
        back_populates="etapas"
    )
