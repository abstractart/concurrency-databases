#!/usr/bin/env python3
"""P1. Пессимистичная стратегия: SELECT ... FOR UPDATE.

T1 блокирует строку и «работает» с ней 1.5 с. T2 в это время тоже выполняет
SELECT ... FOR UPDATE — и ВИСИТ на нём, пока T1 не зафиксируется.
В отличие от P0, T2 читает уже обновлённый баланс: ничего не теряется.
Цена корректности — ожидание второй транзакции.

Запуск:  python cases/p1_for_update.py --db pg   |   --db mysql
"""
import argparse
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.db import connect
from demo.runner import elapsed, expect, log, print_balances, run_threads, sleep
from demo.schema import init_schema

ACC = 1


def withdraw(tag, amount, db, barrier, hold, offset=0.0):
    conn = connect(db)
    try:
        barrier.wait()
        sleep(offset)  # стартовая задержка: делаем сценарий воспроизводимым
        t0 = __import__("time").monotonic()
        # 🔒 Пессимистичная блокировка: строка заблокирована до конца транзакции
        row = conn.query_one(
            "SELECT balance FROM accounts WHERE id = %s FOR UPDATE", (ACC,))
        waited = elapsed(t0)
        note = f" (ждал {waited:.2f} с)" if waited > 0.2 else ""
        log(tag, f"🔒 получил блокировку{note}, balance = {row[0]}")

        sleep(hold)  # имитация «долгой работы» ПОСЛЕ захвата блокировки

        # приращение считается на сервере от АКТУАЛЬНОГО значения
        conn.execute(
            "UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, ACC))
        conn.commit()
        log(tag, f"списал {amount}, commit — блокировка отпущена")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)
    log("DEMO", "P1. Пессимистичная блокировка: SELECT ... FOR UPDATE")

    barrier = threading.Barrier(2)
    run_threads([
        ("T1", lambda: withdraw("T1", 100, db, barrier, hold=1.5)),
        ("T2", lambda: withdraw("T2", 200, db, barrier, hold=0.0, offset=0.2)),
    ])

    from demo.runner import balance_of
    log("ИТОГ", f"balance[{ACC}] = {balance_of(db, ACC)}")
    expect([
        "в логе видно: одна из транзакций ждала на FOR UPDATE ~1.5 с, пока сосед держал строку",
        "вторая транзакция прочитала УЖЕ обновлённый баланс → итог 700, потерь нет",
        "это и есть пессимистичная стратегия: блокируем ДО изменения, конфликта не возникает",
        "цена: вторая транзакция всё время конфликта простаивала",
    ])


if __name__ == "__main__":
    main()
