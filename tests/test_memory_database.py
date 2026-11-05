
import sqlite3

import pytest

from app.memory.database import SQLiteDatabase


def test_database_initialization(tmp_path):
    database_path = tmp_path / "data" / "test.db"

    database = SQLiteDatabase(database_path)
    database.initialize()

    assert database_path.exists()


def test_database_connection_and_storage(tmp_path):
    database_path = tmp_path / "test.db"

    database = SQLiteDatabase(database_path)
    database.initialize()

    with database.connection() as connection:
        connection.execute(
            """
            CREATE TABLE memory_test (
                id INTEGER PRIMARY KEY,
                content TEXT NOT NULL
            )
            """
        )

        connection.execute(
            "INSERT INTO memory_test (content) VALUES (?)",
            ("NEUROCORE memory test",),
        )

    with database.connection() as connection:
        result = connection.execute(
            "SELECT content FROM memory_test WHERE id = 1"
        ).fetchone()

    assert result["content"] == "NEUROCORE memory test"


def test_database_rolls_back_failed_transaction(tmp_path):
    database_path = tmp_path / "test.db"

    database = SQLiteDatabase(database_path)
    database.initialize()

    with database.connection() as connection:
        connection.execute(
            """
            CREATE TABLE memory_test (
                id INTEGER PRIMARY KEY,
                content TEXT NOT NULL
            )
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        with database.connection() as connection:
            connection.execute(
                "INSERT INTO memory_test (content) VALUES (?)",
                ("First record",),
            )

            connection.execute(
                "INSERT INTO memory_test (id, content) VALUES (?, ?)",
                (1, "Duplicate ID"),
            )

    with database.connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM memory_test"
        ).fetchone()[0]

    assert count == 0
