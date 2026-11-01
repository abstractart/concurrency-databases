#!/usr/bin/env python3
"""P0. Мотивация: потерянное обновление (lost update) БЕЗ блокировок.

Обе транзакции работают по схеме read-modify-write «как в ORM»:
  1) прочитали balance            (SELECT)
  2) посчитали в приложении: new = balance - сумма
  3) записали готовое значение    (UPDATE ... SET balance = new)

Дефолтные уровни изоляции (PostgreSQL: READ COMMITTED,
MySQL: REPEATABLE READ) от потери обновления НЕ защищают.

Запуск:  python cases/p0_lost_update.py --db pg   |   --db mysql
"""
import argparse
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.db import connect
from demo.runner import expect, log, print_balances, run_threads, sleep
from demo.schema import init_schema

ACC = 1


def withdraw(tag, amount, db, barrier, write_after):
    conn = connect(db)
    try:
        barrier.wait()  # обе транзакции стартуют одновременно
        bal = conn.query_one("SELECT balance FROM accounts WHERE id = %s", (ACC,))[0]
        log(tag, f"прочитал balance = {bal}, буду списывать {amount} (подумаю {write_after} с)")

        sleep(write_after)  # окно, за которое сосед успевает зафиксироваться

        new = bal - amount  # вычисление в приложении, на УСТАРЕВШИХ данных
        conn.execute("UPDATE accounts SET balance = %s WHERE id = %s", (new, ACC))
        conn.commit()
        log(tag, f"записал balance = {new} и зафиксировался (ошибок нет!)")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)
    default_iso = "READ COMMITTED" if db == "pg" else "REPEATABLE READ"
    log("DEMO", f"P0. Потерянное обновление без блокировок (дефолтный уровень изоляции: {default_iso})")

    barrier = threading.Barrier(2)
    run_threads([
        ("T1", lambda: withdraw("T1", 100, db, barrier, write_after=0.5)),
        ("T2", lambda: withdraw("T2", 200, db, barrier, write_after=1.0)),
    ])

    from demo.runner import balance_of
    log("ИТОГ", f"balance[{ACC}] = {balance_of(db, ACC)}")
    print_balances(db)
    expect([
        "обе транзакции прочитали 1000, записали 900 (T1) и 800 (T2) — обе «успешно»",
        "финальный баланс = 800, хотя должно быть 700 (1000 − 100 − 200)",
        "списание T1 на 100 молча ПОТЕРЯНО — ни ошибки, ни предупреждения от СУБД",
        "остальные кейсы показывают, как это чинить: P1–P6 (блокировки) и O1–O3 (оптимистично)",
    ])


if __name__ == "__main__":
    main()
