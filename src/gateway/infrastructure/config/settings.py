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

    # Observabilidade
    log_path: str = Field(default="logs/gateway.log", alias="GATEWAY_LOG_PATH")

    @model_validator(mode="after")
    def _build_database_url(self) -> "GatewaySettings":
        if not self.database_url:
            self.database_url = (
                f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self