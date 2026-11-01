#!/usr/bin/env python3
"""P4. Deadlock из-за порядка блокировки — и как его починить.

Сценарий A (неправильно): два встречных перевода (1→2 и 2→1). Каждая
транзакция сначала блокирует «свой» счёт, потом просит чужой → цикл
ожидания → deadlock. СУБД сама обнаруживает его и откатывает жертву:
  PostgreSQL: 40P01 deadlock_detected (детект ~1 с, deadlock_timeout)
  MySQL:      1213 ER_LOCK_DEADLOCK (детект мгновенный)

Сценарий B (правильно): обе транзакции блокируют счёты в ОДНОМ порядке
(по возрастанию id). Цикл невозможен по построению — вторая просто ждёт.

Запуск:  python cases/p4_deadlock.py --db pg   |   --db mysql
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

outcome = {}  # tag -> код ошибки (если перевод не прошёл)


def transfer(tag, db, frm, to, amount, ordered):
    conn = connect(db)
    try:
        # Порядок захвата блокировок — единственное различие между A и B
        ids = sorted((frm, to)) if ordered else (frm, to)
        for acc_id in ids:
            t0 = time.monotonic()
            conn.query_one(
                "SELECT id, balance FROM accounts WHERE id = %s FOR UPDATE", (acc_id,))
            waited = elapsed(t0)
            note = f" (ждал {waited:.2f} с)" if waited > 0.2 else ""
            log(tag, f"🔒 заблокировал счёт {acc_id}{note}")
            sleep(0.5)  # окно, чтобы сосед успел взять свой первый счёт

        conn.execute(
            "UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, frm))
        conn.execute(
            "UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, to))
        conn.commit()
        log(tag, f"перевод {frm}→{to} на {amount} проведён, commit")
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        code = conn.error_code(exc)
        outcome[tag] = code
        log(tag, f"❌ перевод откатен: {type(exc).__name__}, код {code}")
    finally:
        conn.close()


def run_scenario(db, title, ordered):
    log("DEMO", f"── {title} ──")
    outcome.clear()
    barrier = threading.Barrier(2)
    run_threads([
        ("T12", lambda: transfer("T12", db, 1, 2, 100, ordered)),
        ("T21", lambda: transfer("T21", db, 2, 1, 50, ordered)),
    ])
    failed = {tag: code for tag, code in outcome.items()}
    if failed:
        log("ИТОГ", f"не прошёл перевод: {failed} — жертву deadlock нужно повторить")
    else:
        log("ИТОГ", "оба перевода прошли без ошибок")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    log("DEMO", "P4. Deadlock при встречных переводах")
    init_schema(db)
    run_scenario(db, "Сценарий A: разный порядок блокировок → deadlock", ordered=False)
    print_balances(db, "Состояние после сценария A (применился только один перевод):")

    init_schema(db)
    run_scenario(db, "Сценарий B: одинаковый порядок (по возрастанию id) → deadlock невозможен", ordered=True)
    print_balances(db, "Состояние после сценария B (применились оба перевода):")

    expect([
        "в сценарии A ровно одна транзакция упала: PG 40P01 / MySQL 1213 — СУБД разрулила цикл",
        "в сценарии B оба перевода прошли: тот, кто пришёл вторым, просто подождал (~0.5 с)",
        "правило: захватывайте блокировки в одном порядке (напр., по возрастанию id) — deadlock исключён",
        "сумма балансов в обоих сценариях сохранилась: 2000",
    ])


if __name__ == "__main__":
    main()
