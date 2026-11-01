#!/usr/bin/env python3
"""O1. Оптимистичная стратегия: версионный столбец + повтор при конфликте.

Никаких блокировок на чтение — читаем свободно. При записи добавляем в WHERE
проверку версии, прочитанной в этой транзакции:

  UPDATE accounts
     SET balance = <новое>, version = version + 1
   WHERE id = ? AND version = <прочитанная версия>

Затронуто 0 строк → сосед записал раньше нас → КОНФЛИКТ → повторяем
транзакцию целиком. Блокировки существуют лишь мгновение, внутри UPDATE.

Запуск:  python cases/o1_version_retry.py --db pg   |   --db mysql
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
MAX_ATTEMPTS = 5


def withdraw(tag, amount, db, barrier):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        conn = connect(db)
        try:
            bal, ver = conn.query_one(
                "SELECT balance, version FROM accounts WHERE id = %s", (ACC,))
            new = bal - amount
            log(tag, f"попытка {attempt}: прочитал balance={bal}, version={ver}")

            ver_now = "CURRENT_TIMESTAMP(6)" if db == "mysql" else "CURRENT_TIMESTAMP"
            cur = conn.execute(
                f"""
                UPDATE accounts
                   SET balance = %s,
                       version = version + 1,
                       updated_at = {ver_now}
                 WHERE id = %s AND version = %s
                """,
                (new, ACC, ver),
            )
            if cur.rowcount == 1:
                conn.commit()
                log(tag, f"попытка {attempt}: версия {ver} была актуальна → "
                         f"записал {new}, commit ✅")
                return
            conn.rollback()
            log(tag, f"попытка {attempt}: 0 строк обновлено — версия {ver} устарела, "
                     f"конфликт, повтор")
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            log(tag, f"попытка {attempt}: ошибка {conn.error_code(exc)}, повтор")
        finally:
            conn.close()
        sleep(0.15 * attempt)  # лёгкий бэкофф перед повтором

    log(tag, f"❌ не смогло списать {amount} за {MAX_ATTEMPTS} попыток")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)
    log("DEMO", "O1. Оптимистичная блокировка: версионный столбец + retry")

    barrier = threading.Barrier(2)
    run_threads([
        ("T1", lambda: withdraw("T1", 100, db, barrier)),
        ("T2", lambda: withdraw("T2", 200, db, barrier)),
    ])

    print_balances(db)
    expect([
        "ровно один конфликт: проигравшая транзакция получила «0 строк обновлено»",
        "и ПОВТОРИЛА попытку уже с новой версией — данные не потеряны",
        "итог: balance = 700, version = 2 (по одному успешному UPDATE на транзакцию)",
        "чтения не блокировались никогда; блокировка жила лишь мгновение внутри UPDATE",
    ])


if __name__ == "__main__":
    main()
