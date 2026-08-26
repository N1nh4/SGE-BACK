from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models  # noqa: F401
from .database import Base, engine
from .routers import auth, comprovacoes, objetivos, paginas, planejamento, unidades, usuarios


def _migrar_colunas() -> None:
    """Adiciona colunas de versões antigas em tabelas já criadas."""
    insp = inspect(engine)
    e_postgres = engine.dialect.name == "postgresql"
    pk_col = "id SERIAL PRIMARY KEY" if e_postgres else "id INTEGER PRIMARY KEY AUTOINCREMENT"

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
            "ppa": "VARCHAR(1000) NOT NULL DEFAULT ''",
            "loa": "VARCHAR(1000) NOT NULL DEFAULT ''",
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
            "senha_hash": "VARCHAR(255) NOT NULL DEFAULT ''",
            "status": "INTEGER NOT NULL DEFAULT 1",
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
                if e_postgres:
                    conn.execute(
                        text(
                            "INSERT INTO indicador_unidades (indicador_id, unidade_id) "
                            "SELECT id, unidade_id FROM indicadores "
                            "WHERE unidade_id IS NOT NULL "
                            "AND unidade_id IN (SELECT id FROM unidades) "
                            "ON CONFLICT DO NOTHING"
                        )
                    )
                else:
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
        ts_type = "TIMESTAMP WITH TIME ZONE" if e_postgres else "DATETIME"
        if "indicador_etapas" not in insp.get_table_names():
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS indicador_etapas ("
                    f"  {pk_col},"
                    "  indicador_id INTEGER NOT NULL,"
                    "  nome VARCHAR(255) NOT NULL,"
                    f"  created_at {ts_type},"
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

        # Migração: expandir ppa/loa de VARCHAR(255) para VARCHAR(1000).
        if e_postgres and "objetivos" in insp.get_table_names():
            for col_name in ("ppa", "loa"):
                conn.execute(
                    text(
                        f"ALTER TABLE objetivos ALTER COLUMN {col_name} "
                        f"TYPE VARCHAR(1000)"
                    )
                )

        # Migração: converter usuarios.papel de enum para VARCHAR (PostgreSQL).
        if e_postgres and "usuarios" in insp.get_table_names():
            cols = {c["name"]: c["type"].__class__.__name__ for c in insp.get_columns("usuarios")}
            if cols.get("papel") == "ENUM":
                conn.execute(
                    text(
                        "ALTER TABLE usuarios ALTER COLUMN papel "
                        "TYPE VARCHAR(20) USING papel::text"
                    )
                )

        # Migração: criar tabela usuario_unidades.
        if "usuario_unidades" not in insp.get_table_names():
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS usuario_unidades ("
                    "  usuario_id INTEGER NOT NULL,"
                    "  unidade_id INTEGER NOT NULL,"
                    "  papel VARCHAR(20) NOT NULL DEFAULT 'default',"
                    "  PRIMARY KEY (usuario_id, unidade_id),"
                    "  FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,"
                    "  FOREIGN KEY (unidade_id) REFERENCES unidades(id) ON DELETE CASCADE"
                    ")"
                )
            )

            # Migrar dados existentes: unidade_id + papel → usuario_unidades.
            if e_postgres:
                conn.execute(
                    text(
                        "INSERT INTO usuario_unidades (usuario_id, unidade_id, papel) "
                        "SELECT id, unidade_id, papel FROM usuarios "
                        "WHERE unidade_id IS NOT NULL "
                        "ON CONFLICT DO NOTHING"
                    )
                )
            else:
                conn.execute(
                    text(
                        "INSERT OR IGNORE INTO usuario_unidades (usuario_id, unidade_id, papel) "
                        "SELECT id, unidade_id, papel FROM usuarios "
                        "WHERE unidade_id IS NOT NULL"
                    )
                )

        # Migracao: remover coluna unidade_id de usuarios.
        if "usuarios" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("usuarios")}
            if "unidade_id" in cols:
                if e_postgres:
                    conn.execute(text("ALTER TABLE usuarios DROP COLUMN unidade_id"))
                else:
                    conn.execute(text("ALTER TABLE usuarios RENAME TO usuarios_old"))
                    conn.execute(
                        text(
                            "CREATE TABLE usuarios ("
                            "  id INTEGER PRIMARY KEY,"
                            "  nome VARCHAR(255) NOT NULL,"
                            "  email VARCHAR(255) NOT NULL UNIQUE,"
                            "  senha_hash VARCHAR(255) NOT NULL,"
                            "  papel VARCHAR(20) NOT NULL DEFAULT 'default',"
                            "  status INTEGER NOT NULL DEFAULT 1,"
                            "  created_at TIMESTAMP,"
                            "  updated_at TIMESTAMP"
                            ")"
                        )
                    )
                    conn.execute(
                        text(
                            "INSERT INTO usuarios (id, nome, email, senha_hash, papel, status, created_at, updated_at) "
                            "SELECT id, nome, email, senha_hash, papel, status, created_at, updated_at "
                            "FROM usuarios_old"
                        )
                    )
                    conn.execute(text("DROP TABLE usuarios_old"))

        # Migração: remover coluna descricao de objetivos (apenas SQLite).
        if not e_postgres and "objetivos" in insp.get_table_names():
            colunas_obj = {
                col["name"] for col in insp.get_columns("objetivos")
            }
            if "descricao" in colunas_obj:
                # Coluna ainda existe — remove com reconstrução completa.
                conn.execute(text("ALTER TABLE objetivos RENAME TO objetivos_old"))
                conn.execute(
                    text(
                        "CREATE TABLE objetivos ("
                        f"  {pk_col},"
                        "  codigo VARCHAR(20) NOT NULL UNIQUE,"
                        "  nome VARCHAR(255) NOT NULL,"
                        "  ppa VARCHAR(1000) NOT NULL,"
                        "  loa VARCHAR(1000) NOT NULL,"
                        "  created_at DATETIME,"
                        "  updated_at DATETIME"
                        ")"
                    )
                )
                conn.execute(
                    text(
                        "INSERT INTO objetivos (id, codigo, nome, ppa, loa, created_at, updated_at) "
                        "SELECT id, codigo, nome, ppa, loa, created_at, updated_at "
                        "FROM objetivos_old"
                    )
                )
                conn.execute(text("DROP TABLE objetivos_old"))
            else:
                # Coluna já removida — verifica se a tabela tem PK/UNIQUE.
                pk_cols = set(
                    insp.get_pk_constraint("objetivos").get("constrained_columns", [])
                )
                uniq_cols = {
                    col_name
                    for constraint in insp.get_unique_constraints("objetivos")
                    for col_name in constraint.get("column_names", [])
                } if insp.get_unique_constraints("objetivos") else set()

                if "id" not in pk_cols or "codigo" not in uniq_cols:
                    conn.execute(text("ALTER TABLE objetivos RENAME TO objetivos_old"))
                    conn.execute(
                        text(
                            "CREATE TABLE objetivos ("
                            f"  {pk_col},"
                            "  codigo VARCHAR(20) NOT NULL UNIQUE,"
                            "  nome VARCHAR(255) NOT NULL,"
                            "  ppa VARCHAR(1000) NOT NULL,"
                            "  loa VARCHAR(1000) NOT NULL,"
                            "  created_at DATETIME,"
                            "  updated_at DATETIME"
                            ")"
                        )
                    )
                    conn.execute(
                        text(
                            "INSERT INTO objetivos (id, codigo, nome, ppa, loa, created_at, updated_at) "
                            "SELECT id, codigo, nome, ppa, loa, created_at, updated_at "
                            "FROM objetivos_old"
                        )
                    )
                conn.execute(text("DROP TABLE objetivos_old"))

        # Migração: criar tabela perfis.
        if "perfis" not in insp.get_table_names():
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS perfis ("
                    f"  {pk_col},"
                    "  chave VARCHAR(20) NOT NULL UNIQUE,"
                    "  nome VARCHAR(100) NOT NULL"
                    ")"
                )
            )

        # Popular perfis padrão (idempotente).
        perfis_padrao = [
            ("master", "Master"),
            ("adm", "Administrador"),
            ("default", "Padrão"),
        ]
        for chave, nome in perfis_padrao:
            if e_postgres:
                conn.execute(
                    text(
                        "INSERT INTO perfis (chave, nome) VALUES (:chave, :nome) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"chave": chave, "nome": nome},
                )
            else:
                conn.execute(
                    text(
                        "INSERT OR IGNORE INTO perfis (chave, nome) VALUES (:chave, :nome)"
                    ),
                    {"chave": chave, "nome": nome},
                )

        # Migrar perfil_paginas: papel string → perfil_id FK.
        if "perfil_paginas" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("perfil_paginas")}
            if "papel" in cols and "perfil_id" not in cols:
                if e_postgres:
                    conn.execute(text("ALTER TABLE perfil_paginas DROP CONSTRAINT perfil_paginas_pkey"))
                    conn.execute(text("ALTER TABLE perfil_paginas ADD COLUMN perfil_id INTEGER NOT NULL DEFAULT 0"))
                    conn.execute(
                        text(
                            "UPDATE perfil_paginas pp SET perfil_id = pf.id "
                            "FROM perfis pf WHERE pp.papel = pf.chave"
                        )
                    )
                    conn.execute(text("ALTER TABLE perfil_paginas DROP COLUMN papel"))
                    conn.execute(text("ALTER TABLE perfil_paginas ADD CONSTRAINT perfil_paginas_pkey PRIMARY KEY (perfil_id, pagina_id)"))
                else:
                    conn.execute(text("ALTER TABLE perfil_paginas RENAME TO perfil_paginas_old"))
                    conn.execute(
                        text(
                            "CREATE TABLE perfil_paginas ("
                            "  perfil_id INTEGER NOT NULL,"
                            "  pagina_id INTEGER NOT NULL,"
                            "  PRIMARY KEY (perfil_id, pagina_id),"
                            "  FOREIGN KEY (perfil_id) REFERENCES perfis(id) ON DELETE CASCADE,"
                            "  FOREIGN KEY (pagina_id) REFERENCES paginas(id) ON DELETE CASCADE"
                            ")"
                        )
                    )
                    conn.execute(
                        text(
                            "INSERT INTO perfil_paginas (perfil_id, pagina_id) "
                            "SELECT pf.id, pp.pagina_id "
                            "FROM perfil_paginas_old pp "
                            "JOIN perfis pf ON pf.chave = pp.papel"
                        )
                    )
                    conn.execute(text("DROP TABLE perfil_paginas_old"))

        if "perfil_paginas" not in insp.get_table_names():
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS perfil_paginas ("
                    "  perfil_id INTEGER NOT NULL,"
                    "  pagina_id INTEGER NOT NULL,"
                    "  acoes JSONB DEFAULT '[\"ver\"]',"
                    "  PRIMARY KEY (perfil_id, pagina_id),"
                    "  FOREIGN KEY (perfil_id) REFERENCES perfis(id) ON DELETE CASCADE,"
                    "  FOREIGN KEY (pagina_id) REFERENCES paginas(id) ON DELETE CASCADE"
                    ")"
                )
            )

        # Migracao: adicionar coluna acoes em perfil_paginas.
        if "perfil_paginas" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("perfil_paginas")}
            if "acoes" not in cols:
                conn.execute(text("ALTER TABLE perfil_paginas ADD COLUMN acoes JSONB DEFAULT '[\"ver\"]'"))
                conn.execute(text("UPDATE perfil_paginas SET acoes = '[\"ver\",\"criar\",\"editar\",\"excluir\"]'"))

        # Popular páginas disponíveis (idempotente).
        paginas_disponiveis = [
            ("/indicadores", "Indicadores"),
            ("/objetivos", "Objetivos"),
            ("/planejamento", "Planejamento"),
            ("/comprovacoes", "Comprovações"),
            ("/unidades", "Unidades"),
            ("/validacao", "Validação"),
            ("/configurador", "Configurações"),
        ]
        for chave, nome in paginas_disponiveis:
            if e_postgres:
                conn.execute(
                    text(
                        "INSERT INTO paginas (chave, nome) VALUES (:chave, :nome) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"chave": chave, "nome": nome},
                )
            else:
                conn.execute(
                    text(
                        "INSERT OR IGNORE INTO paginas (chave, nome) VALUES (:chave, :nome)"
                    ),
                    {"chave": chave, "nome": nome},
                )

        # Popular perfil_paginas padrão com acoes (idempotente).
        import json

        all_actions = ["ver", "criar", "editar", "excluir"]
        view_approve = ["ver", "aprovar"]

        permissoes_padrao = {
            "master": {chave: all_actions for chave in [
                "/indicadores", "/objetivos", "/planejamento",
                "/comprovacoes", "/unidades", "/validacao", "/configurador",
            ]},
            "adm": {
                "/indicadores": ["ver", "criar", "editar"],
                "/objetivos": ["ver", "criar", "editar"],
                "/planejamento": ["ver", "criar", "editar"],
                "/comprovacoes": ["ver"],
                "/unidades": ["ver"],
                "/validacao": view_approve,
                "/configurador": [],
            },
            "default": {
                "/indicadores": ["ver"],
                "/planejamento": ["ver", "criar", "editar"],
                "/comprovacoes": ["ver", "criar"],
                "/objetivos": ["ver"],
                "/unidades": ["ver"],
                "/validacao": ["ver"],
                "/configurador": [],
            },
        }
        for papel, paginas_acoes in permissoes_padrao.items():
            for chave, acoes in paginas_acoes.items():
                acoes_json = json.dumps(acoes)
                conn.execute(
                    text(
                        "INSERT INTO perfil_paginas (perfil_id, pagina_id, acoes) "
                        "SELECT pf.id, pg.id, CAST(:acoes AS JSONB) FROM perfis pf, paginas pg "
                        "WHERE pf.chave = :papel AND pg.chave = :chave "
                        "ON CONFLICT (perfil_id, pagina_id) DO UPDATE SET acoes = CAST(:acoes AS JSONB)"
                    ),
                    {"papel": papel, "chave": chave, "acoes": acoes_json},
                )


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _migrar_colunas()
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

app.include_router(auth.router)
app.include_router(objetivos.router)
app.include_router(planejamento.router)
app.include_router(comprovacoes.router)
app.include_router(unidades.router)
app.include_router(usuarios.router)
app.include_router(paginas.router)


@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs"}
