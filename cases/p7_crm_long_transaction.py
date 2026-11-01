#!/usr/bin/env python3
"""P7. CRM анти-паттерн: транзакция, открытая на время редактирования пользователем.

Схема «открыл карточку → BEGIN + FOR UPDATE → пользователь думает → Сохранить →
COMMIT» технически работает: транзакцию никто не заставляет закрывать, она просто
остаётся открытой. Проблема в цене. Здесь два сценария:

  A: M1 «редактирует» карточку 6 с, держа строку и соединение. M2 за это время
     не может сохранить вообще (пользователь видит ошибку), M3 — только с 3-й
     попытки, после того как M1 нажал «Сохранить».
  B: каждая открытая карточка НЕ возвращает соединение в пул. Пула на 3
     соединения хватает трём пользователям — четвёртому не достаётся даже
     на «открыть карточку».

Правильные альтернативы: оптимистичная блокировка (O1), короткие транзакции
(как P1), TTL-блокировки приложения, атомарные UPDATE (R3).

Запуск:  python cases/p7_crm_long_transaction.py --db pg   |   --db mysql
"""
import argparse
import queue
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demo.db import connect
from demo.runner import elapsed, expect, log, print_balances, run_threads, sleep
from demo.schema import init_schema

ACC = 1


class MiniPool:
    """Игрушечный аналог пула соединений (как SQLAlchemy QueuePool)."""

    def __init__(self, size, db):
        self._free = queue.LifoQueue()
        for _ in range(size):
            self._free.put(connect(db))

    def get(self, timeout=1.0):
        return self._free.get(timeout=timeout)

    def put(self, conn):
        self._free.put(conn)


# ── Сценарий A: транзакция живёт, пока пользователь редактирует ──────────────
def manager_edits(tag, db, offset, hold):
    """«Открыл форму» = BEGIN + FOR UPDATE. Транзакция остаётся открытой, пока
    пользователь думает; блокировка и соединение заняты всё это время."""
    conn = connect(db)
    try:
        sleep(offset)
        conn.query_one(
            "SELECT id, owner, balance FROM accounts WHERE id = %s FOR UPDATE", (ACC,))
        log(tag, f"📝 открыл карточку: строка заблокирована, транзакция НЕ закрыта; "
                 f"«редактирую» {hold} с")
        sleep(hold)  # 🕐 человеческое время внутри транзакции — вот анти-паттерн
        conn.execute("UPDATE accounts SET balance = balance - 100 WHERE id = %s", (ACC,))
        conn.commit()
        log(tag, "💾 «Сохранить» → commit: блокировка и соединение освобождены "
                 "только сейчас")
    finally:
        conn.close()


def manager_saves(tag, db, offset, attempts, timeout_s):
    """Конкурентное сохранение: UPDATE стоит в очереди на чужую блокировку."""
    conn = connect(db)
    try:
        conn.set_lock_timeout(timeout_s)
        for attempt in range(1, attempts + 1):
            sleep(offset if attempt == 1 else 0.4)
            t0 = time.monotonic()
            try:
                conn.execute(
                    "UPDATE accounts SET balance = balance - 200 WHERE id = %s", (ACC,))
                conn.commit()
                log(tag, f"💾 сохранение прошло с попытки {attempt} "
                         f"(ждал чужую транзакцию {elapsed(t0):.2f} с)")
                return
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                log(tag, f"❌ попытка {attempt}: пользователь видит «Попробуйте позже» "
                         f"— строка занята ЧУЖОЙ незакрытой транзакцией "
                         f"({conn.error_code(exc)} после {elapsed(t0):.2f} с)")
        log(tag, "…так и не смог сохранить, пока сосед «редактирует»")
    finally:
        conn.close()


# ── Сценарий B: соединения не возвращаются в пул ─────────────────────────────
def open_card_request(tag, pool, hold, offset=0.0):
    """HTTP-запрос «открыть карточку»: изъял соединение из пула и не вернул,
    пока пользователь не сохранит форму."""
    sleep(offset)
    try:
        conn = pool.get(timeout=1.0)
    except queue.Empty:
        log(tag, "❌ «Открыть карточку» недоступно: ПУЛ ИСЧЕРПАН — все соединения "
                 "держат незакрытые транзакции")
        return
    try:
        conn.query_one("SELECT id, owner FROM accounts WHERE id = 1")  # просмотр не блокирует
        log(tag, f"📝 открыл карточку; соединение изъято из пула на {hold} с "
                 f"(транзакция открыта)")
        sleep(hold)
        conn.commit()
        log(tag, "💾 сохранил — соединение только теперь вернулось в пул")
        pool.put(conn)
    finally:
        pass  # соединения с незакрытыми транзакциями сознательно «утекают»


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", choices=("pg", "mysql"), required=True)
    db = ap.parse_args().db

    log("DEMO", "P7. CRM анти-паттерн: транзакция живёт, пока пользователь редактирует")
    init_schema(db)

    log("DEMO", "── Сценарий A: M1 «редактирует» 6 с, M2/M3 пытаются сохранить ──")
    run_threads([
        ("M1", lambda: manager_edits("M1", db, offset=0.0, hold=6.0)),
        ("M2", lambda: manager_saves("M2", db, offset=0.5, attempts=1, timeout_s=2)),
        ("M3", lambda: manager_saves("M3", db, offset=1.0, attempts=3, timeout_s=2)),
    ])
    print_balances(db, "После сценария A (итог корректный, но какой ценой):")

    log("DEMO", "── Сценарий B: пул на 3 соединения, 4 пользователя открывают карточки ──")
    pool = MiniPool(3, db)
    try:
        run_threads([
            ("U1", lambda: open_card_request("U1", pool, hold=5.0)),
            ("U2", lambda: open_card_request("U2", pool, hold=5.2, offset=0.2)),
            ("U3", lambda: open_card_request("U3", pool, hold=5.4, offset=0.4)),
            ("U4", lambda: open_card_request("U4", pool, hold=5.6, offset=0.6)),
        ])
    finally:
        while True:  # приберём соединения, не попавшие в пул
            try:
                pool.get(timeout=0.1).close()
            except queue.Empty:
                break

    print_balances(db)
    expect([
        "корректность не пострадала (итог 700) — проблема в ДОСТУПНОСТИ:",
        "A: пока M1 «думал» 6 с, M2 не смог сохранить вообще (ошибка пользователю),",
        "   M3 сохранил только с 3-й попытки, дождавшись чужого «Сохранить»",
        "B: трёх открытых карточек хватило, чтобы 4-й пользователь не смог",
        "   открыть даже просмотр — соединения не возвращаются в пул",
        "масштабируйте на 50 менеджеров и 5 минут редактирования — лежит вся система",
        "правильно: НЕ держать транзакцию между HTTP-запросами; version+retry (O1),",
        "короткие транзакции (P1), TTL-блокировки приложения, атомарные UPDATE (R3)",
    ])


if __name__ == "__main__":
    main()
