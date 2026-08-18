import os


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite:///./sge.db"
    )
    secret_key: str = os.getenv(
        "SECRET_KEY", "sge-dev-secret-change-in-production"
    )


settings = Settings()
