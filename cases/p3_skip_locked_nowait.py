#!/usr/bin/env python3
"""P3. Пессимистичная блокировка БЕЗ ожиданий: SKIP LOCKED и NOWAIT.

Паттерн «очередь задач» на строках таблицы:
  SKIP LOCKED — взять первую НЕЗАНЯТУЮ строку, чужие блокировки просто
                пропустить (воркеры не дерутся за одну задачу и не ждут);
  NOWAIT      — если строка занята, получить ошибку СРАЗУ, а не ждать.
Поддерживается в PostgreSQL и MySQL 8+.

Запуск:  python cases/p3_skip_locked_nowait.py --db pg   |   --db mysql
"""
import argparse
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.db import connect
from demo.runner import expect, log, print_balances, run_threads, sleep
from demo.schema import init_schema

TAKE = "SELECT id, balance FROM accounts ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED"


def worker(tag, db, barrier, offset, hold):
    conn = connect(db)
    try:
        barrier.wait()
        sleep(offset)  # стартовая задержка, чтобы лог был воспроизводимее
        row = conn.query_one(TAKE)
        if row is None:
            log(tag, "свободных строк нет — брать нечего")
            conn.rollback()
            return
        acc_id = row[0]
        log(tag, f"взял в работу счёт id={acc_id} (занятые пропущены), держу {hold} с")
        sleep(hold)  # «обработка задачи»
        conn.execute(
            "UPDATE accounts SET balance = balance * 1.1 WHERE id = %s", (acc_id,))
        conn.commit()
        log(tag, f"обработал id={acc_id} (+10%), commit")
    finally:
        conn.close()


def impatient(db, barrier):
    """NOWAIT: строка занята → мгновенная ошибка вместо ожидания."""
    conn = connect(db)
    try:
        barrier.wait()
        sleep(0.4)  # к этому моменту W1 уже держит счёт 1
        try:
            conn.query_one("SELECT id FROM accounts WHERE id = 1 FOR UPDATE NOWAIT")
            log("W3", "счёт 1 свободен — забрал (не наш сценарий)")
            conn.rollback()
        except Exception as exc:  # noqa: BLE001
            code = conn.error_code(exc)
            expected = "55P03 (lock_not_available)" if db == "pg" else "3572 (ER_LOCK_NOWAIT)"
            log("W3", f"⏱ NOWAIT не ждал ни секунды: ошибка {type(exc).__name__}, "
                      f"код {code} (ожидался {expected})")
            conn.rollback()
            log("W3", "приложение может сразу отдать «занято» или отдать задачу другому воркеру")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)
    log("DEMO", "P3. Очередь задач на accounts: SKIP LOCKED + NOWAIT")

    barrier = threading.Barrier(3)
    run_threads([
        ("W1", lambda: worker("W1", db, barrier, offset=0.0, hold=2.5)),
        ("W2", lambda: worker("W2", db, barrier, offset=0.2, hold=1.0)),
        ("W3", lambda: impatient(db, barrier)),
    ])

    print_balances(db)
    expect([
        "W1 взял счёт 1 и держал его 2.5 с; W2 НЕ ЖДАЛ и взял следующий свободный — счёт 2",
        "воркеры обработали РАЗНЫЕ строки параллельно: никто никого не блокировал",
        "W3 при NOWAIT получил ошибку мгновенно (PG 55P03 / MySQL 3572), а не завис в ожидании",
        "итог: id=1 и id=2 выросли на 10% (1100), id=3 не тронут",
    ])


if __name__ == "__main__":
    main()
