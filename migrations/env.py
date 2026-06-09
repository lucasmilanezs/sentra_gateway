import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Alembic config object
config = context.config

# Setup loggers
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importar Base compartilhada e todos os modelos ORM para
# que suas tabelas sejam registradas no metadata antes do autogenerate.
from src.shared.db import Base
import src.admin.infrastructure.persistence.postgres.models  # noqa: F401

target_metadata = Base.metadata


def get_url() -> str:
    """
    URL síncrona para uso exclusivo do Alembic.
    Usa psycopg (v3) em modo sync — mesmo pacote do runtime async,
    eliminando a necessidade de psycopg2-binary.
    """
    user = os.getenv("POSTGRES_USER", "sentra")
    password = os.getenv("POSTGRES_PASSWORD", "sentra_secret")
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "sentra_db")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def run_migrations_offline() -> None:
    """Modo offline: gera SQL sem conexão real com o banco."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo online: conecta ao banco e executa as migrations."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()