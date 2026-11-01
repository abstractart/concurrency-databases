#!/usr/bin/env python3
"""R1. REPEATABLE READ: снапшот и повторяемое чтение.

T1 работает в изоляции REPEATABLE READ и читает баланс дважды. Между
чтениями T2 успевает списать деньги и зафиксироваться. Оба чтения T1
видят одно и то же значение — это и есть контракт «повторяемого чтения».
В PostgreSQL и MySQL поведение ОДИНАКОВОЕ (MVCC-снапшот).

Запуск:  python cases/r1_rr_snapshot.py --db pg   |   --db mysql
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.db import connect
from demo.runner import expect, log, print_balances, sleep
from demo.schema import init_schema


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)
    log("DEMO", "R1. REPEATABLE READ: чтение из снапшота")

    t1 = connect(db)
    t1.set_repeatable_read()  # в MySQL это дефолт, задаём явно для наглядности
    t2 = connect(db)
    try:
        b1 = t1.query_one("SELECT balance FROM accounts WHERE id = 1")[0]
        log("T1", f"чтение №1: balance = {b1}")

        t2.execute("UPDATE accounts SET balance = balance - 300 WHERE id = 1")
        t2.commit()
        log("T2", "списал 300 и зафиксировался (независимо от T1)")

        sleep(0.2)  # фиксация T2 точно «пролетела» между чтениями T1
        b2 = t1.query_one("SELECT balance FROM accounts WHERE id = 1")[0]
        log("T1", f"чтение №2: balance = {b2}  ← чужой commit НЕ виден!")

        t1.commit()  # конец RR-транзакции; следующий SELECT начнёт новую
        b3 = t1.query_one("SELECT balance FROM accounts WHERE id = 1")[0]
        log("T1", f"после commit (новая транзакция, новый снапшот): balance = {b3}")
    finally:
        t1.close()
        t2.close()

    print_balances(db)
    expect([
        "оба чтения внутри RR-транзакции вернули 1000, хотя T2 уже зафиксировал 700",
        "повторяемое чтение — контракт RR; в PostgreSQL и MySQL он работает одинаково",
        "после COMMIT транзакция завершилась: новый SELECT стартовал новую транзакцию",
        "и увидел актуальные 700 (свежий снапшот)",
    ])


if __name__ == "__main__":
    main()
