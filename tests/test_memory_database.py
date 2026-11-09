
import sqlite3

import pytest
from threading import Barrier
from app.memory.database import SQLiteDatabase

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
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
def test_database_enables_foreign_keys(tmp_path):
    database = SQLiteDatabase(tmp_path / "test.db")
    database.initialize()

    with database.connection() as connection:
        result = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

    assert result == 1


def test_database_uses_wal_mode(tmp_path):
    database = SQLiteDatabase(tmp_path / "test.db")
    database.initialize()

    with database.connection() as connection:
        result = connection.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0]

    assert result.lower() == "wal"
def test_database_initialization_rejects_corrupted_file(tmp_path):
    database_path = tmp_path / "corrupted.db"

    database_path.write_bytes(b"This is not a valid SQLite database")

    database = SQLiteDatabase(database_path)

    with pytest.raises(sqlite3.DatabaseError):
        database.initialize()
def test_database_integrity_check_passes_for_healthy_database(tmp_path):
    database = SQLiteDatabase(tmp_path / "test.db")
    database.initialize()

    assert database.check_integrity() is True
def test_database_closes_connection_after_failed_transaction(tmp_path):
    database = SQLiteDatabase(tmp_path / "test.db")
    database.initialize()

    with pytest.raises(sqlite3.OperationalError):
        with database.connection() as connection:
            connection.execute("SELECT * FROM nonexistent_table")

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")
def test_database_handles_concurrent_writes(tmp_path):
    database = SQLiteDatabase(tmp_path / "test.db")
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

    barrier = Barrier(2)

    def insert_records(prefix):
        barrier.wait()

        with database.connection() as connection:
            connection.executemany(
                "INSERT INTO memory_test (content) VALUES (?)",
                [(f"{prefix}-{i}",) for i in range(20)],
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(insert_records, "Agent-A"),
            executor.submit(insert_records, "Agent-B"),
        ]

        for future in futures:
            future.result()

    with database.connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM memory_test"
        ).fetchone()[0]

    assert count == 40


def test_database_supports_concurrent_reads_and_writes(tmp_path):
    database = SQLiteDatabase(tmp_path / "test.db")
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
            ("Existing memory",),
        )

    write_started = Barrier(2)
    allow_write_to_finish = Barrier(2)

    def write_records():
        with database.connection() as connection:
            connection.execute(
                "INSERT INTO memory_test (content) VALUES (?)",
                ("New memory",),
            )
            write_started.wait()
            allow_write_to_finish.wait()

    def read_records():
        write_started.wait()

        with database.connection() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM memory_test"
            ).fetchone()[0]

        allow_write_to_finish.wait()
        return count

    with ThreadPoolExecutor(max_workers=2) as executor:
        write_future = executor.submit(write_records)
        read_future = executor.submit(read_records)

        read_count = read_future.result()
        write_future.result()

    assert read_count == 1

    with database.connection() as connection:
        final_count = connection.execute(
            "SELECT COUNT(*) FROM memory_test"
        ).fetchone()[0]

    assert final_count == 2

def test_database_rejects_invalid_foreign_key(tmp_path):
    database = SQLiteDatabase(tmp_path / "test.db")
    database.initialize()

    with database.connection() as connection:
        connection.execute(
            """
            CREATE TABLE parent (
                id INTEGER PRIMARY KEY
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE child (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES parent(id)
            )
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        with database.connection() as connection:
            connection.execute(
                "INSERT INTO child (parent_id) VALUES (?)",
                (999,),
            )
def test_database_foreign_key_integrity_check(tmp_path):
    database = SQLiteDatabase(tmp_path / "test.db")
    database.initialize()

    with database.connection() as connection:
        connection.execute(
            "CREATE TABLE parent (id INTEGER PRIMARY KEY)"
        )
        connection.execute(
            """
            CREATE TABLE child (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER REFERENCES parent(id)
            )
            """
        )

        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "INSERT INTO child (parent_id) VALUES (999)"
        )

    with database.connection() as connection:
        violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

    assert len(violations) == 1

def test_database_foreign_key_integrity_passes_for_healthy_database(
    tmp_path,
):
    database = SQLiteDatabase(tmp_path / "test.db")
    database.initialize()

    with database.connection() as connection:
        connection.execute(
            "CREATE TABLE parent (id INTEGER PRIMARY KEY)"
        )
        connection.execute(
            """
            CREATE TABLE child (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER REFERENCES parent(id)
            )
            """
        )
        connection.execute(
            "INSERT INTO parent (id) VALUES (1)"
        )
        connection.execute(
            "INSERT INTO child (parent_id) VALUES (1)"
        )

    assert database.check_foreign_key_integrity() is True
def test_database_closes_connection_after_successful_transaction(
    tmp_path,
):
    database = SQLiteDatabase(tmp_path / "test.db")
    database.initialize()

    with database.connection() as connection:
        connection.execute("CREATE TABLE memory_test (id INTEGER)")

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")

def test_database_waits_for_locked_database(tmp_path):
    from threading import Event, Thread
    from time import sleep

    database = SQLiteDatabase(tmp_path / "test.db")
    database.initialize()

    with database.connection() as connection:
        connection.execute(
            "CREATE TABLE memory_test (id INTEGER PRIMARY KEY)"
        )

    lock_acquired = Event()

    def hold_write_lock():
        with sqlite3.connect(database.database_path) as lock_connection:
            lock_connection.execute("BEGIN IMMEDIATE")
            lock_acquired.set()

            sleep(0.3)

            lock_connection.rollback()

    locker = Thread(target=hold_write_lock)
    locker.start()

    assert lock_acquired.wait(timeout=2)

    with database.connection() as connection:
        connection.execute(
            "INSERT INTO memory_test DEFAULT VALUES"
        )

    locker.join()

    with database.connection() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM memory_test"
        ).fetchone()[0]

    assert count == 1