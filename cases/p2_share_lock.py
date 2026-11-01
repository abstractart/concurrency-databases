#!/usr/bin/env python3
"""P2. Разделяемая блокировка: FOR SHARE.

Синтаксис одинаков в PG и MySQL 8 (в MySQL 5.7 — LOCK IN SHARE MODE).

Правило:
  FOR SHARE + FOR SHARE  → совместимы: читатели работают ПАРАЛЛЕЛЬНО
  FOR SHARE + FOR UPDATE → несовместимы: писатель ждёт всех читателей

Запуск:  python cases/p2_share_lock.py --db pg   |   --db mysql
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

ACC = 1
HOLD = 2.0


def reader(tag, db, barrier):
    conn = connect(db)
    try:
        barrier.wait()
        t0 = time.monotonic()
        row = conn.query_one(
            "SELECT balance FROM accounts WHERE id = %s FOR SHARE", (ACC,))
        log(tag, f"📖 FOR SHARE получена за {elapsed(t0):.2f} с "
                 f"(balance = {row[0]}); держу {HOLD} с")
        sleep(HOLD)
        conn.rollback()  # менять нечего — транзакцией просто отпускаем блокировку
        log(tag, "rollback — разделяемая блокировка отпущена")
    finally:
        conn.close()


def writer(db, barrier):
    conn = connect(db)
    try:
        barrier.wait()
        sleep(0.2)  # даём читателям успеть взять FOR SHARE первыми
        t0 = time.monotonic()
        row = conn.query_one(
            "SELECT balance FROM accounts WHERE id = %s FOR UPDATE", (ACC,))
        log(f"W", f"✍️ FOR UPDATE дождалась читателей за {elapsed(t0):.2f} с "
                  f"(balance = {row[0]})")
        conn.execute(
            "UPDATE accounts SET balance = balance + 500 WHERE id = %s", (ACC,))
        conn.commit()
        log("W", "начислил +500, commit")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)
    log("DEMO", "P2. Разделяемая блокировка: FOR SHARE (2 читателя + 1 писатель)")

    barrier = threading.Barrier(3)
    run_threads([
        ("T1", lambda: reader("T1", db, barrier)),
        ("T2", lambda: reader("T2", db, barrier)),
        ("W", lambda: writer(db, barrier)),
    ])

    print_balances(db)
    expect([
        "оба читателя получили FOR SHARE мгновенно (~0.00 с) — читатели не мешают друг другу",
        "писатель ждал на FOR UPDATE ~2 с, пока читатели не отпустят строку",
        "итог: 1500 (1000 + 500), обновление применено строго после читателей",
    ])


if __name__ == "__main__":
    main()
