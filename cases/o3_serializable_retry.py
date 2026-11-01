#!/usr/bin/env python3
"""O3. Оптимистичная стратегия силами СУБД: SERIALIZABLE + повтор.

Приложение лишь помечает транзакцию SERIALIZABLE и повторяет её при
ошибке сериализации. Кто обнаруживает конфликт — различается:

  PostgreSQL: настоящий SSI (Serializable Snapshot Isolation). Конфликт →
              ошибка 40001 serialization_failure на UPDATE или COMMIT.
              Самая «оптимистичная» реализация: блокировки почти не
              используются, конфликт виден постфактум.

  MySQL:      SERIALIZABLE реализован БЛОКИРОВКАМИ: обычный SELECT получает
              shared lock (как FOR SHARE). Две параллельные транзакции,
              прочитавшие строку и обе пытающиеся её изменить, упираются
              во взаимный ожидание → InnoDB детектирует deadlock (1213)
              или, при выключенном детекте, ждёт таймаута (1205).
              Итог тот же: повторить транзакцию, но механика «оптимистики»
              здесь уже наполовину «пессимистика».

Коды для ретрая в обоих случаях — см. RETRYABLE в demo/db.py.

Запуск:  python cases/o3_serializable_retry.py --db pg   |   --db mysql
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
MAX_ATTEMPTS = 3


def withdraw(tag, amount, db, barrier):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        conn = connect(db)
        try:
            conn.set_serializable()
            bal = conn.query_one(
                "SELECT balance FROM accounts WHERE id = %s", (ACC,))[0]
            if attempt == 1:
                barrier.wait()  # обе транзакции читают «одновременно»
            sleep(0.3)          # окно для конфликта

            new = bal - amount
            conn.execute("UPDATE accounts SET balance = %s WHERE id = %s", (new, ACC))
            conn.commit()
            log(tag, f"попытка {attempt}: прочитал {bal} → записал {new}, commit ✅")
            return
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            # В production фильтруйте по conn.is_retryable(exc) из demo/db.py
            log(tag, f"попытка {attempt}: конфликт — {type(exc).__name__}, "
                     f"код {conn.error_code(exc)} → повтор транзакции")
        finally:
            conn.close()
        sleep(0.1)

    log(tag, f"❌ не смогло списать {amount} за {MAX_ATTEMPTS} попыток")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)
    log("DEMO", "O3. SERIALIZABLE + retry (конфликт обнаруживает сама СУБД)")

    barrier = threading.Barrier(2)
    run_threads([
        ("T1", lambda: withdraw("T1", 100, db, barrier)),
        ("T2", lambda: withdraw("T2", 200, db, barrier)),
    ])

    print_balances(db)

    if db == "pg":
        expect([
            "одна транзакция зафиксировалась, вторая получила 40001",
            "«could not serialize access…» (на UPDATE или на COMMIT) — это SSI в работе",
            "упавшая транзакция просто повторилась целиком и успешно: итог 700",
            "в PostgreSQL SERIALIZABLE — «чистая» оптимистика на уровне изоляции",
        ])
    else:
        expect([
            "конфликт проявился как deadlock: MySQL 1213 (SERIALIZABLE даёт SELECT'ам",
            "shared-блокировки, обе транзакции ждут X-блокировку друг друга)",
            "жертва deadlock повторила транзакцию: итог 700",
            "в MySQL тот же паттерн, но коды для ретрая другие: 1213 и 1205",
        ])


if __name__ == "__main__":
    main()
