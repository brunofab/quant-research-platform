from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine

from quant_research.settings import get_settings


def create_database_engine() -> Engine:
    settings = get_settings()

    url = URL.create(
        drivername="postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )

    return create_engine(
        url,
        pool_pre_ping=True,
    )


def check_database_connection() -> tuple[str, str]:
    engine = create_database_engine()

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT current_database(), current_user")
        ).one()

    return row[0], row[1]
