"""Единый мини-слой доступа к PostgreSQL и MySQL для демо-скриптов.

Оба драйвера следуют DB-API 2.0: транзакция неявно начинается с первого
запроса, поэтому явный BEGIN нигде не посылается.

Параметры подключения переопределяются переменными окружения:
  PG:    PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
  MySQL: MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE
"""
import os

PG = dict(
    host=os.getenv("PGHOST", "localhost"),
    port=int(os.getenv("PGPORT", "5432")),
    user=os.getenv("PGUSER", "postgres"),
    password=os.getenv("PGPASSWORD", "postgres"),
    dbname=os.getenv("PGDATABASE", "demo"),
)
MY = dict(
    host=os.getenv("MYSQLHOST", "127.0.0.1"),
    port=int(os.getenv("MYSQLPORT", "3306")),
    user=os.getenv("MYSQLUSER", "root"),
    password=os.getenv("MYSQLPASSWORD", "root"),
    database=os.getenv("MYSQLDATABASE", "demo"),
)

# Коды ошибок, при которых транзакцию имеет смысл повторить целиком:
#   PostgreSQL: 40001 serialization_failure, 40P01 deadlock_detected
#   MySQL:      1213 ER_LOCK_DEADLOCK,       1205 ER_LOCK_WAIT_TIMEOUT
RETRYABLE = {
    "pg": {"40001", "40P01"},
    "mysql": {"1213", "1205"},
}


class BaseConn:
    driver = "?"
    db = "?"

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

    # -- запросы ---------------------------------------------------------
    def execute(self, sql, params=None):
        """Выполнить запрос; вернуть курсор (доступны .rowcount, .fetchone, ...)."""
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur

    def query_one(self, sql, params=None):
        cur = self.execute(sql, params)
        row = cur.fetchone()
        cur.close()
        return row

    # -- диалектозависимое -------------------------------------------------
    def set_lock_timeout(self, seconds):
        raise NotImplementedError

    def set_serializable(self):
        raise NotImplementedError

    def set_repeatable_read(self):
        raise NotImplementedError

    def error_code(self, exc):
        """Короткий код ошибки: SQLSTATE у PG, errno у MySQL."""
        raise NotImplementedError

    def is_retryable(self, exc):
        return self.error_code(exc) in RETRYABLE[self.db]


class PgConn(BaseConn):
    driver = "PostgreSQL (psycopg 3)"
    db = "pg"

    def __init__(self):
        import psycopg

        self.conn = psycopg.connect(**PG)
        self.conn.autocommit = False

    def _set_isolation(self, level):
        # psycopg3: уровень задаётся до начала транзакции (соединение свежее)
        import psycopg

        self.conn.isolation_level = getattr(psycopg.IsolationLevel, level)

    def set_lock_timeout(self, seconds):
        # SET в PostgreSQL не принимает плейсхолдеры — значение int, инлайним
        self.execute(f"SET lock_timeout = '{int(seconds)}s'")

    def set_serializable(self):
        self._set_isolation("SERIALIZABLE")

    def set_repeatable_read(self):
        self._set_isolation("REPEATABLE_READ")

    def error_code(self, exc):
        return getattr(exc, "sqlstate", None) or ""


class MyConn(BaseConn):
    driver = "MySQL 8 (PyMySQL)"
    db = "mysql"

    def __init__(self):
        import pymysql

        self.conn = pymysql.connect(charset="utf8mb4", autocommit=False, **MY)

    def set_lock_timeout(self, seconds):
        self.execute("SET SESSION innodb_lock_wait_timeout = %s", (int(seconds),))

    def set_serializable(self):
        self.execute("SET SESSION TRANSACTION ISOLATION LEVEL SERIALIZABLE")

    def set_repeatable_read(self):
        # В MySQL это уровень по умолчанию; задаём явно для наглядности
        self.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")

    def error_code(self, exc):
        return str(exc.args[0]) if getattr(exc, "args", None) else ""


def connect(db):
    if db == "pg":
        return PgConn()
    if db == "mysql":
        return MyConn()
    raise ValueError(f"неизвестная СУБД: {db!r} (ожидается 'pg' или 'mysql')")
