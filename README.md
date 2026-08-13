# SGE — Backend (FastAPI)

API do Sistema de Gestão Estratégica, construída com **FastAPI**, **SQLAlchemy** e banco de dados **SQLite** (padrão para desenvolvimento) ou **PostgreSQL** (produção).

## Requisitos

- **Python 3.13+** (o projeto foi desenvolvido com Python 3.13)
- `pip` disponível

## Como rodar

### 1. Criar o ambiente virtual

Execute na pasta `backend`:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

> O `.venv` já está no `.gitignore` — não suba ele para o repositório.

### 2. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar o banco (opcional)

Sem nenhuma configuração, a API usa **SQLite** (`sge.db` na pasta `backend`), que já funciona sem precisar de servidor. Para usar **PostgreSQL**:

1. Copie `.env.example` para `.env` e ajuste a variável `DATABASE_URL`.
2. Se for usar o Postgres via Docker, suba o banco:

   ```bash
   docker compose up -d
   ```

### 4. Subir a API

```bash
uvicorn app.main:app --reload
```

A API ficará disponível em:

- API: <http://localhost:8000>
- Documentação interativa (Swagger): <http://localhost:8000/docs>

## Observações

- Na primeira execução, as tabelas são criadas automaticamente e os objetivos estratégicos iniciais são semeados (`seed_objetivos`).
- Arquivos de comprovação (PDFs) são salvos em `backend/uploads/comprovacoes/` (a pasta `uploads/` está no `.gitignore`).
- O frontend (`my-app`) espera a API em `http://localhost:8000` — o CORS já libera `http://localhost:3000`.
