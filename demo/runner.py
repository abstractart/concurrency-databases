"""Хелперы демо: лог с таймстемпами, синхронный старт потоков, итоги."""
import threading
import time
from datetime import datetime


def _ts():
    now = datetime.now()
    return f"{now:%H:%M:%S}.{now.microsecond // 1000:03d}"


def log(tag, msg):
    print(f"{_ts()} | {tag:<5} | {msg}", flush=True)


def expect(lines):
    print("\n" + "─" * 64)
    print("ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:")
    for line in lines:
        print(f"  • {line}")
    print("─" * 64, flush=True)


def sleep(seconds):
    time.sleep(seconds)


def elapsed(t0):
    """Секунды с момента t0 = time.monotonic()."""
    return time.monotonic() - t0


def run_threads(fns, timeout=60):
    """fns: [(тег, функция)] — запускает потоки и ждёт завершения.

    Возвращает {тег: исключение или None}. Исключения печатаются, но
    не роняют весь демо-скрипт.
    """
    results = {}

    def wrap(tag, fn):
        def run():
            try:
                fn()
                results[tag] = None
            except Exception as exc:  # noqa: BLE001
                results[tag] = exc
                log(tag, f"❌ {type(exc).__name__}: {exc}")
        return run

    threads = []
    for tag, fn in fns:
        t = threading.Thread(target=wrap(tag, fn), name=tag, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout)
    return results


def final_balances(db):
    """Финальное состояние accounts (в новом соединении, вне демо-транзакций)."""
    from demo.db import connect

    c = connect(db)
    try:
        rows = c.execute(
            "SELECT id, owner, balance, version FROM accounts ORDER BY id"
        ).fetchall()
        c.commit()
        return rows
    finally:
        c.close()


def balance_of(db, acc_id):
    for id_, _, bal, _ in final_balances(db):
        if id_ == acc_id:
            return bal
    raise LookupError(f"счёт {acc_id} не найден")


def print_balances(db, title="Состояние accounts:"):
    log("ИТОГ", title)
    for id_, owner, bal, ver in final_balances(db):
        print(f"          id={id_}  {owner:<6} balance={bal:>9}  version={ver}")
