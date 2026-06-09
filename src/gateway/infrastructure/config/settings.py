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
    redis_fail_open: bool = Field(default=True, alias="GATEWAY_REDIS_FAIL_OPEN")
    redis_connect_timeout_seconds: float = Field(default=1.0, alias="GATEWAY_REDIS_CONNECT_TIMEOUT_SECONDS")
    redis_operation_timeout_seconds: float = Field(default=1.5, alias="GATEWAY_REDIS_OPERATION_TIMEOUT_SECONDS")
    redis_subscriber_max_retries: int = Field(default=5, alias="GATEWAY_REDIS_SUBSCRIBER_MAX_RETRIES")
    redis_runtime_max_failures: int = Field(default=5, alias="GATEWAY_REDIS_RUNTIME_MAX_FAILURES")
    redis_health_probe_max_failures: int = Field(default=3, alias="GATEWAY_REDIS_HEALTH_PROBE_MAX_FAILURES")
    redis_pubsub_idle_ping_seconds: float = Field(default=20.0, alias="GATEWAY_REDIS_PUBSUB_IDLE_PING_SECONDS")

    # Optional read-only authorization for detailed health payloads exposed by the gateway.
    admin_jwt_secret: str = Field(default="change-me-in-production-use-long-random-secret", alias="ADMIN_JWT_SECRET")
    admin_jwt_algorithm: str = Field(default="HS256", alias="ADMIN_JWT_ALGORITHM")

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    # Local-only key used to encrypt/decrypt contractor-provided JWT signing material.
    # Never commit its value; generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    policy_secret_key: str = Field(default="", alias="SENTRA_POLICY_SECRET_KEY")

    # Observabilidade
    audit_to_postgres: bool = Field(default=True, alias="GATEWAY_AUDIT_TO_POSTGRES")
    raw_log_retention_days: int = Field(default=7, alias="GATEWAY_RAW_LOG_RETENTION_DAYS")
    raw_log_max_entries_per_tenant_per_day: int = Field(default=1000, alias="GATEWAY_RAW_LOG_MAX_ENTRIES_PER_TENANT_PER_DAY")
    raw_log_redact_headers: str = Field(
        default="authorization,cookie,set-cookie,x-api-key",
        alias="GATEWAY_RAW_LOG_REDACT_HEADERS",
    )

    @property
    def raw_log_redact_header_names(self) -> tuple[str, ...]:
        return tuple(h.strip().lower() for h in self.raw_log_redact_headers.split(",") if h.strip())


    @model_validator(mode="after")
    def _build_database_url(self) -> "GatewaySettings":
        if not self.database_url:
            self.database_url = (
                f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self