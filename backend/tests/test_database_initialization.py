import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite://")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, event, inspect

from app.database.db import initialize_database


def test_initialize_database_creates_missing_user_sessions_table():
    engine = create_engine("sqlite://")
    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.create_function("CHAR_LENGTH", 1, len),
    )
    try:
        initialize_database(engine)

        assert inspect(engine).has_table("users")
        assert inspect(engine).has_table("user_sessions")
    finally:
        engine.dispose()
