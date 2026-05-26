from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdminSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    # JWT
    jwt_secret: str = Field(
        default="change-me-in-production-use-long-random-secret",
        alias="ADMIN_JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", alias="ADMIN_JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=60 * 24, alias="ADMIN_JWT_EXPIRE_MINUTES")

    # Persistência
    use_postgres: bool = Field(default=False, alias="ADMIN_USE_POSTGRES")
    database_url: str = Field(default="", alias="ADMIN_DATABASE_URL")
    json_data_path: str = Field(default="data/admin_local.json", alias="ADMIN_JSON_DATA_PATH")
    gateway_log_path: str = Field(default="logs/gateway.log", alias="GATEWAY_LOG_PATH")

    # Postgres
    postgres_user: str = Field(default="sentra", alias="POSTGRES_USER")
    postgres_password: str = Field(default="sentra_secret", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="127.0.0.1", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="sentra_db", alias="POSTGRES_DB")

    # Redis
    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")

    # Email
    smtp_host: str | None = Field(default=None, alias="ADMIN_SMTP_HOST")
    smtp_port: int = Field(default=587, alias="ADMIN_SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="ADMIN_SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="ADMIN_SMTP_PASSWORD")
    smtp_from: str | None = Field(default=None, alias="ADMIN_SMTP_FROM")
    email_use_console: bool = Field(default=True, alias="ADMIN_EMAIL_USE_CONSOLE")
    superuser_email: str = Field(
        default="superuser@sentra.dev", alias="SENTRA_SUPERUSER_EMAIL"
    )
    superuser_password: str = Field(
        default="change-me-in-production", alias="SENTRA_SUPERUSER_PASSWORD"
    )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @model_validator(mode="after")
    def _build_database_url(self) -> "AdminSettings":
        if not self.database_url:
            self.database_url = (
                f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self