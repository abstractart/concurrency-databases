#!/usr/bin/env python3
"""O2. Оптимистичная стратегия без нового столбца: проверка по updated_at.

Та же идея, что в O1, но «версией» служит метка времени последнего изменения:

  UPDATE accounts
     SET balance = <новое>, updated_at = CURRENT_TIMESTAMP
   WHERE id = ? AND updated_at = <прочитанная метка>

Плюс: не нужно менять схему и ORM-модель — updated_at часто уже есть.
Минусы (почему version надёжнее): часы приложений/БД, округление,
две записи в одну микросекунду, изменение updated_at «побочными» апдейтами.

Запуск:  python cases/o2_updated_at.py --db pg   |   --db mysql
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
            bal, upd = conn.query_one(
                "SELECT balance, updated_at FROM accounts WHERE id = %s", (ACC,))
            new = bal - amount
            log(tag, f"попытка {attempt}: balance={bal}, updated_at={upd}")

            # TIMESTAMP(6) в обеих СУБД хранит микросекунды — значение
            # можно смело подставить обратно в WHERE; в MySQL обязательно
            # CURRENT_TIMESTAMP(6), иначе метка усечётся до секунд
            upd_now = "CURRENT_TIMESTAMP(6)" if db == "mysql" else "CURRENT_TIMESTAMP"
            cur = conn.execute(
                f"""
                UPDATE accounts
                   SET balance = %s, updated_at = {upd_now}
                 WHERE id = %s AND updated_at = %s
                """,
                (new, ACC, upd),
            )
            if cur.rowcount == 1:
                conn.commit()
                log(tag, f"попытка {attempt}: метка актуальна → записал {new}, commit ✅")
                return
            conn.rollback()
            log(tag, f"попытка {attempt}: 0 строк — кто-то записал после нашего чтения, повтор")
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            log(tag, f"попытка {attempt}: ошибка {conn.error_code(exc)}, повтор")
        finally:
            conn.close()
        sleep(0.15 * attempt)

    log(tag, f"❌ не смогло списать {amount} за {MAX_ATTEMPTS} попыток")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    init_schema(db)
    log("DEMO", "O2. Оптимистичная блокировка через updated_at (без столбца version)")

    barrier = threading.Barrier(2)
    run_threads([
        ("T1", lambda: withdraw("T1", 100, db, barrier)),
        ("T2", lambda: withdraw("T2", 200, db, barrier)),
    ])

    print_balances(db)
    expect([
        "конфликт детектируется так же, как в O1, но по метке updated_at вместо version",
        "итог: balance = 700, updated_at обновлён дважды",
        "в реальном коде предпочитайте version: метки чувствительны к часам и округлению",
    ])


if __name__ == "__main__":
    main()
