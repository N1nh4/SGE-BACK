import os


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite:///./sge.db"
    )


settings = Settings()
