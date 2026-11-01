#!/usr/bin/env python3
"""P5. Не ждать вечно: таймаут ожидания блокировки.

T1 держит строку 3 с. T2 настроил таймаут ожидания в 1 с — и получил
ошибку через ~1 с вместо трехсекундного висения:
  PostgreSQL: SET lock_timeout = '1s'   → 55P03 lock_not_available
  MySQL:      innodb_lock_wait_timeout  → 1205 ER_LOCK_WAIT_TIMEOUT

Так приложение может вежливо отказаться от операции («ресурс занят,
попробуйте позже»), а не копить зависшие соединения.

Запуск:  python cases/p5_lock_timeout.py --db pg   |   --db mysql
"""
import argparse
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.db import connect
from demo.runner import elapsed, expect, log, print_balances, run_threads, sleep
from demo.schema import init_schema


def holder(db, barrier):
    conn = connect(db)
    try:
        conn.query_one("SELECT balance FROM accounts WHERE id = 1 FOR UPDATE")
        log("T1", "🔒 держу счёт 1, отпущу через 3 с")
        barrier.wait()
        sleep(3.0)
        conn.commit()
        log("T1", "commit — блокировка снята")
    finally:
        conn.close()


def waiter(db, barrier):
    conn = connect(db)
    try:
        conn.set_lock_timeout(1)
        barrier.wait()
        t0 = time.monotonic()
        try:
            conn.query_one("SELECT balance FROM accounts WHERE id = 1 FOR UPDATE")
            log("T2", "дождался блокировки (не ожидали!)")
            conn.rollback()
        except Exception as exc:  # noqa: BLE001
            expected = "55P03" if db == "pg" else "1205"
            log("T2", f"⏱ прервался через {elapsed(t0):.2f} с (таймаут 1 с): "
                      f"код {conn.error_code(exc)}, ожидался {expected}")
            conn.rollback()
            # Нюанс MySQL: по умолчанию (innodb_rollback_on_timeout=OFF) откатывается
            # только запрос, транзакция формально жива; мы откатываем её явно.
            log("T2", "транзакция откатена: можно вернуть пользователю «занято» и повторить позже")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)
    timeout_name = "lock_timeout" if db == "pg" else "innodb_lock_wait_timeout"
    log("DEMO", f"P5. Таймаут ожидания блокировки ({timeout_name} = 1 c, T1 держит строку 3 c)")

    barrier = threading.Barrier(2)
    run_threads([
        ("T1", lambda: holder(db, barrier)),
        ("T2", lambda: waiter(db, barrier)),
    ])

    print_balances(db)
    expect([
        "T2 прервался примерно через 1.0 с с ошибкой ожидания (PG 55P03 / MySQL 1205),",
        "хотя T1 отпускал строку только через 3 с — приложение не висело зря",
        "данные не изменены (балансы по 1000): прерванная транзакция ничего не записала",
    ])


if __name__ == "__main__":
    main()
