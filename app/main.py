from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models  # noqa: F401
from .database import Base, engine
from .routers import comprovacoes, objetivos, planejamento, unidades, usuarios
from .seed import seed_objetivos, seed_usuarios


def _migrar_colunas() -> None:
    """Adiciona colunas de versões antigas em tabelas já criadas."""
    insp = inspect(engine)
    e_postgres = engine.dialect.name == "postgresql"

    # SQLite não aceita DEFAULT não-constante (ex.: CURRENT_TIMESTAMP) em
    # ADD COLUMN, então colunas de data são adicionadas sem default e os
    # registros existentes são preenchidos em seguida. Os valores de novas
    # linhas e atualizações são definidos pelo Python (default/onupdate).
    definicoes_por_tabela = {
        "objetivos": {
            "created_at": (
                "TIMESTAMP WITH TIME ZONE" if e_postgres else "DATETIME"
            ),
            "updated_at": (
                "TIMESTAMP WITH TIME ZONE" if e_postgres else "DATETIME"
            ),
            "ppa": "VARCHAR(255) NOT NULL DEFAULT ''",
            "loa": "VARCHAR(255) NOT NULL DEFAULT ''",
        },
        "indicadores": {
            "unidade_id": "INTEGER",
            "valor_acumulado": "REAL NOT NULL DEFAULT 0",
            "rotulo_x": "VARCHAR(255) NOT NULL DEFAULT ''",
            "rotulo_y": "VARCHAR(255) NOT NULL DEFAULT ''",
        },
        "comprovacoes": {
            "status": "VARCHAR(20) NOT NULL DEFAULT 'analise'",
            "justificativa": "TEXT",
            "prazo_reenvio": "DATE",
            "etapa_id": "INTEGER",
        },
        "usuarios": {
            "unidade_id": "INTEGER",
        },
    }
    colunas_de_data = {"created_at", "updated_at"}

    with engine.begin() as conn:
        for tabela, definicoes in definicoes_por_tabela.items():
            if tabela not in insp.get_table_names():
                continue
            colunas = {col["name"] for col in insp.get_columns(tabela)}
            for nome, tipo in definicoes.items():
                if nome in colunas:
                    continue
                conn.execute(
                    text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")
                )
                if nome in colunas_de_data:
                    conn.execute(
                        text(
                            f"UPDATE {tabela} SET {nome} = CURRENT_TIMESTAMP "
                            f"WHERE {nome} IS NULL"
                        )
                    )

        # Migração: antigo responsavel_id passou a ser unidade_id.
        if "indicadores" in insp.get_table_names():
            colunas_ind = {
                col["name"] for col in insp.get_columns("indicadores")
            }
            if "unidade_id" in colunas_ind and "responsavel_id" in colunas_ind:
                conn.execute(
                    text(
                        "UPDATE indicadores SET unidade_id = responsavel_id "
                        "WHERE unidade_id IS NULL AND responsavel_id IS NOT NULL "
                        "AND responsavel_id IN (SELECT id FROM unidades)"
                    )
                )

        # Migração: unidade_id (FK única) → tabela associativa indicador_unidades.
        if "indicadores" in insp.get_table_names():
            colunas_ind = {
                col["name"] for col in insp.get_columns("indicadores")
            }
            tem_tabela_assoc = "indicador_unidades" in insp.get_table_names()

            if not tem_tabela_assoc:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS indicador_unidades ("
                        "  indicador_id INTEGER NOT NULL,"
                        "  unidade_id INTEGER NOT NULL,"
                        "  PRIMARY KEY (indicador_id, unidade_id),"
                        "  FOREIGN KEY (indicador_id) REFERENCES indicadores(id)"
                        "    ON DELETE CASCADE,"
                        "  FOREIGN KEY (unidade_id) REFERENCES unidades(id)"
                        "    ON DELETE CASCADE"
                        ")"
                    )
                )

            if "unidade_id" in colunas_ind:
                conn.execute(
                    text(
                        "INSERT OR IGNORE INTO indicador_unidades "
                        "(indicador_id, unidade_id) "
                        "SELECT id, unidade_id FROM indicadores "
                        "WHERE unidade_id IS NOT NULL "
                        "AND unidade_id IN (SELECT id FROM unidades)"
                    )
                )

        # Migração: criar tabela indicador_etapas.
        if "indicador_etapas" not in insp.get_table_names():
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS indicador_etapas ("
                    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "  indicador_id INTEGER NOT NULL,"
                    "  nome VARCHAR(255) NOT NULL,"
                    "  created_at DATETIME,"
                    "  FOREIGN KEY (indicador_id) REFERENCES indicadores(id)"
                    "    ON DELETE CASCADE"
                    ")"
                )
            )

        # Migração: dropar coluna formula (substituída por rotulo_x/rotulo_y).
        if "indicadores" in insp.get_table_names():
            colunas_ind = {
                col["name"] for col in insp.get_columns("indicadores")
            }
            if "formula" in colunas_ind:
                conn.execute(text("ALTER TABLE indicadores DROP COLUMN formula"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrar_colunas()
    seed_objetivos()
    seed_usuarios()
    yield


app = FastAPI(title="SGE API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(objetivos.router)
app.include_router(planejamento.router)
app.include_router(comprovacoes.router)
app.include_router(unidades.router)
app.include_router(usuarios.router)


@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}
