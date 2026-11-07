
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import settings


class SQLiteDatabase:
    """Manages NEUROCORE's local SQLite database."""

    def __init__(self, database_path: str | Path | None = None):
        self.database_path = Path(
            database_path or settings.database_path
        )

    def initialize(self) -> None:
        """Creates the database directory and initializes SQLite."""

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA foreign_keys = ON")

    def check_integrity(self) -> bool:
        """Returns whether the SQLite database passes its integrity check."""

        with self.connection() as connection:
            result = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

        return result == "ok"

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Provides a managed database connection."""

        connection = sqlite3.connect(
            self.database_path,
            timeout=10,
        )

        connection.row_factory = sqlite3.Row

        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()
