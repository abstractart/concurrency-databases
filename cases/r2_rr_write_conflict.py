#!/usr/bin/env python3
"""R2. REPEATABLE READ при записи — ключевое различие PostgreSQL и MySQL.

Обе транзакции в RR прочитали 1000 и списывают по схеме read-modify-write:

  PostgreSQL: RR = snapshot isolation. UPDATE T2 после фиксации T1 падает
              с 40001 «could not serialize access due to concurrent update».
              Потерянное обновление невозможно, но нужен retry.

  MySQL:      конфликт НЕ обнаруживается. UPDATE делает «current read»
              (видит актуальную строку), но ЗНАЧЕНИЕ посчитано приложением
              из старого снапшота — итог: потерянное обновление.
              Классическая ситуация ORM: прочитал сущность → поменял поле →
              сохранил. Лечится FOR SHARE / FOR UPDATE или version (кейс O1).

Запуск:  python cases/r2_rr_write_conflict.py --db pg   |   --db mysql
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
        conn.set_repeatable_read()
        bal = conn.query_one("SELECT balance FROM accounts WHERE id = %s", (ACC,))[0]
        log(tag, f"RR-снапшот: balance = {bal}; запишу {bal} − {amount} через {write_after} с")
        barrier.wait()
        sleep(write_after)

        new = bal - amount  # значение посчитано по СТАРОМУ снапшоту
        try:
            conn.execute("UPDATE accounts SET balance = %s WHERE id = %s", (new, ACC))
            conn.commit()
            log(tag, f"записал balance = {new}, commit прошёл без ошибок")
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            log(tag, f"❌ {type(exc).__name__}, код {conn.error_code(exc)}: {exc}")
            log(tag, "→ транзакция откатена; корректная стратегия — повторить её целиком (O1/O3)")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)
    log("DEMO", "R2. REPEATABLE READ: две записи в одну строку (read-modify-write)")

    barrier = threading.Barrier(2)
    run_threads([
        ("T1", lambda: withdraw("T1", 100, db, barrier, write_after=0.5)),
        ("T2", lambda: withdraw("T2", 200, db, barrier, write_after=1.0)),
    ])

    print_balances(db)

    if db == "pg":
        expect([
            "T1 записал 900 и зафиксировался; T2 на UPDATE получила 40001",
            "«could not serialize access due to concurrent update» — RR в PostgreSQL",
            "НЕ даёт потерять обновление; приложению нужен retry (см. O3)",
            "итог: 900 — то, что успело зафиксироваться первым",
        ])
    else:
        expect([
            "ОБЕ транзакции «успешно» записали: итог 800 вместо правильных 700",
            "UPDATE в MySQL применился к актуальной строке (current read), но значение",
            "посчитано из старого снапшота → потерянное обновление, и СУБД молчит",
            "RR в MySQL НЕ защищает от lost update: используйте FOR SHARE/FOR UPDATE",
            "или версионный столбец — см. кейс O1",
        ])


if __name__ == "__main__":
    main()
