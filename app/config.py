import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite:///./sge.db"
    ).strip()
    secret_key: str = os.getenv(
        "SECRET_KEY", "sge-dev-secret-change-in-production"
    ).strip()


settings = Settings()
