"""Database engine and session helpers."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from tide.config import settings

# pool_pre_ping checks a connection is alive before using it (Postgres restarts, etc.).
# connect_timeout makes an unreachable database fail in seconds instead of hanging.
engine = create_engine(
    settings.database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5}
)
SessionLocal = sessionmaker(bind=engine)


def check_connection() -> bool:
    """Return True if we can run a trivial query against Postgres."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
