#!/usr/bin/env python3
"""R3. REPEATABLE READ: UPDATE с вычислением в самом запросе.

R2 показал, что RR + «SET balance = <посчитано в приложении из снапшота>»
теряет обновление в MySQL. Здесь арифметику делает САМА СУБД:

    UPDATE accounts SET balance = balance - %s WHERE id = %s

Разница — в том, ОТ КАКОЙ ВЕРСИИ строки считается выражение:

  MySQL (InnoDB): UPDATE всегда читает последнюю ЗАФИКСИРОВАННУЮ версию
                  («current read», даже в RR). Снапшот говорил «1000»,
                  но вычитание применится к актуальным 900 → итог 700.
                  Потери нет, ретрай не нужен.

  PostgreSQL:     REPEATABLE READ запрещает UPDATE вообще трогать строку,
                  изменившуюся после снапшота → 40001 даже для
                  относительного приращения. Нужен retry: при повторе
                  списание пройдёт от актуальных данных.

Запуск:  python cases/r3_rr_relative_update.py --db pg   |   --db mysql
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


def withdraw(tag, amount, db, barrier, update_after):
    conn = connect(db)
    try:
        conn.set_repeatable_read()
        # Читаем только для нарратива: RR-снапшот в обеих СУБД скажет «1000».
        bal = conn.query_one("SELECT balance FROM accounts WHERE id = %s", (ACC,))[0]
        log(tag, f"RR-снапшот: balance = {bal}; план: "
                 f"«SET balance = balance − {amount}» (вычисляет СУБД)")
        barrier.wait()
        sleep(update_after)

        try:
            # 🔑 Приращение вычисляется В ЗАПРОСЕ, от актуальной версии строки
            conn.execute(
                "UPDATE accounts SET balance = balance - %s WHERE id = %s",
                (amount, ACC))
            conn.commit()
            after = conn.query_one(
                "SELECT balance FROM accounts WHERE id = %s", (ACC,))[0]
            log(tag, f"UPDATE прошёл, commit ✅; после commit: balance = {after}")
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            log(tag, f"❌ {type(exc).__name__}, код {conn.error_code(exc)}: {exc}")
            log(tag, "→ RR в PostgreSQL не пустила UPDATE к строке, изменённой "
                     "после снапшота")
            log(tag, "→ лечение: повторить транзакцию — спишет уже от актуальных "
                     "данных (итог 700)")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)
    log("DEMO", "R3. REPEATABLE READ: «SET balance = balance − X» — вычисление в запросе")

    barrier = threading.Barrier(2)
    run_threads([
        ("T1", lambda: withdraw("T1", 100, db, barrier, update_after=0.5)),
        ("T2", lambda: withdraw("T2", 200, db, barrier, update_after=1.0)),
    ])

    print_balances(db)

    if db == "pg":
        expect([
            "T1 применила «balance = balance − 100» к актуальным 1000 → 900, commit ✅",
            "T2 получила 40001 на UPDATE: строка изменилась после её RR-снапшота —",
            "относительное вычисление не спасает, PG запрещает сам доступ к строке",
            "итог 900 (нужен ретрай); для сравнения: на READ COMMITTED тот же UPDATE",
            "применился бы к актуальной строке без всякой ошибки → итог 700",
        ])
    else:
        expect([
            "снапшот T2 говорил «1000», но UPDATE вычел 200 от АКТУАЛЬНЫХ 900 → итог 700",
            "в MySQL UPDATE делает «current read» даже в RR: относительное вычисление",
            "в запросе = нет потерянных обновлений, ретраев и ошибок",
            "сравните с R2: там «SET balance = <значение из снапшота>» молча затирало",
            "чужую запись — разница только в том, где считается выражение",
        ])


if __name__ == "__main__":
    main()
