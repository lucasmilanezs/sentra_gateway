from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdminSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADMIN_", env_file=".env", extra="ignore")

    jwt_secret: str = Field(default="change-me-in-production-use-long-random-secret")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    database_url: str = Field(
        default="postgresql+psycopg2://sentra:sentra@localhost:5432/sentra_admin",
        description="URL SQLAlchemy para Postgres (futuro); arquivo JSON usado até lá.",
    )

    json_data_path: str = Field(default="data/admin_local.json")

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    email_use_console: bool = Field(default=True, description="Se true, apenas loga o código.")
