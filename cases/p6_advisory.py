#!/usr/bin/env python3
"""P6. Advisory-блокировки: мьютекс на уровне СУБД, не привязанный к строкам.

  PostgreSQL: pg_advisory_lock(key) / pg_try_advisory_lock(key)
                            / pg_advisory_unlock(key)   — уровень СЕССИИ
  MySQL:      GET_LOCK('имя', timeout) / GET_LOCK('имя', 0)  (try)
                            / RELEASE_LOCK('имя')

Годится для «критических секций» приложения: только один воркер выполняет
задачу (напр., ночное начисление), даже если строк в таблице ещё нет.

Запуск:  python cases/p6_advisory.py --db pg   |   --db mysql
"""
import argparse
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.db import connect
from demo.runner import elapsed, expect, log, run_threads, sleep
from demo.schema import init_schema

KEY = 42
NAME = "critical_section"


def acquire(db, conn):
    if db == "pg":
        conn.query_one("SELECT pg_advisory_lock(%s)", (KEY,))
    else:
        got = conn.query_one("SELECT GET_LOCK(%s, 60)", (NAME,))[0]
        assert got == 1, "не удалось получить блокировку за 60 с"


def release(db, conn):
    if db == "pg":
        conn.query_one("SELECT pg_advisory_unlock(%s)", (KEY,))
    else:
        conn.query_one("SELECT RELEASE_LOCK(%s)", (NAME,))
    conn.commit()


def try_lock(db, conn, key_or_name):
    """True, если блокировка получена сразу (и тогда её же и отпускаем)."""
    if db == "pg":
        ok = bool(conn.query_one("SELECT pg_try_advisory_lock(%s)", (key_or_name,))[0])
        if ok:
            conn.query_one("SELECT pg_advisory_unlock(%s)", (key_or_name,))
    else:
        ok = conn.query_one("SELECT GET_LOCK(%s, 0)", (key_or_name,))[0] == 1
        if ok:
            conn.query_one("SELECT RELEASE_LOCK(%s)", (key_or_name,))
    return ok


def holder(db, barrier):
    conn = connect(db)
    try:
        acquire(db, conn)
        log("T1", "🔒 захватил advisory-блокировку (ключ 42 / 'critical_section')")

        # Пока T1 держит блокировку, второе соединение пробует try-вариант
        probe = connect(db)
        try:
            busy = not try_lock(db, probe, KEY if db == "pg" else NAME)
            free = try_lock(db, probe, 43 if db == "pg" else "other_section")
            probe.commit()
            log("T1", f"try-lock со стороны: ключ 42 занят? {busy}; ключ 43 свободен? {free}")
        finally:
            probe.close()

        barrier.wait()  # к этому моменту T2 уже встал в ожидание
        sleep(1.5)      # «критическая секция»
        release(db, conn)
        log("T1", "блокировка отпущена")
    finally:
        conn.close()


def waiter(db, barrier):
    conn = connect(db)
    try:
        barrier.wait()
        t0 = time.monotonic()
        acquire(db, conn)  # висит, пока T1 не отпустит
        log("T2", f"дождался своей очереди за {elapsed(t0):.2f} с и захватил блокировку")
        release(db, conn)
        log("T2", "отработал и отпустил")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)  # таблица для advisory-блокировок не нужна — это уровень сессии
    log("DEMO", "P6. Advisory-блокировки: взаимная исключительность вне строк таблицы")

    barrier = threading.Barrier(2)
    run_threads([
        ("T1", lambda: holder(db, barrier)),
        ("T2", lambda: waiter(db, barrier)),
    ])

    expect([
        "T2 ждал ~1.5 с, пока T1 держит «критическую секцию», и вошёл только после отпускания",
        "try-lock вернул «занято» для ключа 42 и «свободно» для ключа 43 — ключи независимы",
        "advisory-блокировки не связаны со строками: удобно для глобальных мьютексов приложения",
        "PG: блокировки живут на уровне сессии; MySQL: освобождаются при закрытии соединения",
    ])


if __name__ == "__main__":
    main()
