from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    # Postgres — variáveis compartilhadas (sem prefixo)
    postgres_user: str = Field(default="sentra", alias="POSTGRES_USER")
    postgres_password: str = Field(default="sentra_secret", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="sentra_db", alias="POSTGRES_DB")
    database_url: str = Field(default="", alias="GATEWAY_DATABASE_URL")

    #Redis
    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    # Observabilidade
    log_path: str = Field(default="logs/gateway.log", alias="GATEWAY_LOG_PATH")
    audit_to_postgres: bool = Field(default=True, alias="GATEWAY_AUDIT_TO_POSTGRES")

    # JWT — mesma secret do admin para validação criptográfica opcional
    jwt_secret: str = Field(default="", alias="ADMIN_JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="ADMIN_JWT_ALGORITHM")

    @model_validator(mode="after")
    def _build_database_url(self) -> "GatewaySettings":
        if not self.database_url:
            self.database_url = (
                f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self