"""Пересоздание демо-таблицы accounts перед каждым кейсом.

Каждый запуск кейса начинается с чистого состояния:
три счёта по 1000.00, version = 0.
"""
from demo.db import connect

DDL = {
    "pg": [
        "DROP TABLE IF EXISTS accounts",
        """
        CREATE TABLE accounts (
            id         INTEGER PRIMARY KEY,
            owner      VARCHAR(100)  NOT NULL,
            balance    NUMERIC(12,2) NOT NULL DEFAULT 0,
            version    INTEGER       NOT NULL DEFAULT 0,
            updated_at TIMESTAMP(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        INSERT INTO accounts (id, owner, balance) VALUES
            (1, 'Алиса', 1000.00),
            (2, 'Боб',    1000.00),
            (3, 'Кэрол',  1000.00)
        """,
    ],
    "mysql": [
        "DROP TABLE IF EXISTS accounts",
        """
        CREATE TABLE accounts (
            id         INT PRIMARY KEY,
            owner      VARCHAR(100)  NOT NULL,
            balance    DECIMAL(12,2) NOT NULL DEFAULT 0,
            version    INT           NOT NULL DEFAULT 0,
            updated_at TIMESTAMP(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ) CHARACTER SET utf8mb4
        """,
        "INSERT INTO accounts (id, owner, balance) VALUES "
        "(1, 'Алиса', 1000.00), (2, 'Боб', 1000.00), (3, 'Кэрол', 1000.00)",
    ],
}


def init_schema(db, quiet=False):
    from demo.runner import log

    conn = connect(db)
    try:
        for stmt in DDL[db]:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()
    if not quiet:
        log("DEMO", "таблица accounts пересоздана: 3 счёта по 1000.00, version = 0")
