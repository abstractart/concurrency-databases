#!/usr/bin/env python3
"""Прогон всех демо-кейсов на всех СУБД.

Запуск:
  python run_all.py                    # все кейсы × [pg, mysql]
  python run_all.py --dbs pg           # только PostgreSQL
  python run_all.py --dbs pg mysql     # то же, через пробелы тоже можно
  python run_all.py --filter deadlock  # кейсы с 'deadlock' в имени файла
  python run_all.py --verbose          # печатать вывод кейсов полностью, вживую

Кейс считается пройденным, если его скрипт завершился с кодом 0 в отведённый
таймаут. В конце печатается сводная таблица; код возврата 1, если был хотя бы
один сбой.

Требования: подняты контейнеры (docker compose up -d, дождаться healthy) и
установлены драйверы (pip install -r requirements.txt). Запускать тем же
интерпретатором, что и кейсы, напр.: .venv/bin/python run_all.py
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES_DIR = ROOT / "cases"
ORDER = {"p": 0, "r": 1, "o": 2}  # группы в порядке README: пессимистичные, RR, оптимистичные


def discover_cases():
    files = [p for p in CASES_DIR.glob("*.py") if p.name != "__init__.py"]
    return sorted(files, key=lambda p: (ORDER.get(p.stem[:1], 9), p.stem))


def case_title(path):
    """Первая строка docstring кейса — для заголовка в логе."""
    try:
        text = path.read_text(encoding="utf-8")
        if '"""' in text:
            first = text.split('"""')[1].strip().splitlines()
            if first:
                return first[0].strip().lstrip("P0123456789. ").strip()
    except OSError:
        pass
    return path.stem


def run_case(python, case, db, timeout, verbose):
    cmd = [python, str(case), "--db", db]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            stdout=None if verbose else subprocess.PIPE,
            stderr=None if verbose else subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        secs = time.monotonic() - t0
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode == 0, secs, out, None
    except subprocess.TimeoutExpired:
        return False, time.monotonic() - t0, "", f"не уложился в таймаут {timeout} с"


def main():
    ap = argparse.ArgumentParser(description="Прогон всех демо-кейсов на всех СУБД")
    ap.add_argument("--dbs", nargs="+", default=["pg", "mysql"], choices=("pg", "mysql"),
                    help="на каких СУБД гнать (по умолчанию: pg mysql)")
    ap.add_argument("--filter", help="оставить кейсы с подстрокой в имени, напр. 'p4' или 'rr'")
    ap.add_argument("--timeout", type=int, default=180, help="таймаут одного кейса, сек")
    ap.add_argument("--verbose", action="store_true", help="показывать вывод кейсов вживую")
    args = ap.parse_args()

    cases = discover_cases()
    if args.filter:
        cases = [c for c in cases if args.filter.lower() in c.stem.lower()]
    if not cases:
        print("Кейсы не найдены (проверьте --filter)")
        return 1

    print(f"Кейсов: {len(cases)} × СУБД: {', '.join(args.dbs)} = "
          f"{len(cases) * len(args.dbs)} запусков\n")

    results = {}  # (stem, db) -> (ok, output, error)
    for case in cases:
        print(f"── {case.stem} — {case_title(case)}")
        for db in args.dbs:
            ok, secs, out, err = run_case(sys.executable, case, db, args.timeout, args.verbose)
            mark = "✅" if ok else "❌"
            note = f"  ({err})" if err else ""
            print(f"     {db:<6} {mark} {secs:5.1f}s{note}")
            results[(case.stem, db)] = (ok, out, err)
        print()

    # ── сводная таблица ────────────────────────────────────────
    width = max(len(c.stem) for c in cases)
    line = "═" * (width + 4 + 9 * len(args.dbs))
    print(line)
    print(f"{'кейс':<{width}}  " + "".join(f"{d:>8}" for d in args.dbs))
    failed = []
    for case in cases:
        row = f"{case.stem:<{width}}  "
        for db in args.dbs:
            ok, out, err = results[(case.stem, db)]
            row += f"{'✅' if ok else '❌':>8}"
            if not ok:
                failed.append((case.stem, db, out, err))
        print(row)
    print(line)

    total = len(cases) * len(args.dbs)
    print(f"Итого: {total - len(failed)}/{total} успешно")

    # ── подробности неудач ─────────────────────────────────────
    if failed:
        print("\n── Подробности неудач (последние 30 строк вывода) ──")
        for name, db, out, err in failed:
            print(f"\n❌ {name} [{db}]" + (f" — {err}" if err else ""))
            tail = "\n".join(out.splitlines()[-30:])
            if tail.strip():
                print(tail)
        print("\nПодсказки:")
        print("  • базы подняты? docker compose up -d, затем дождаться healthy в docker compose ps")
        print("  • драйверы установлены? pip install -r requirements.txt")
        print("  • запускайте venv-интерпретатором: .venv/bin/python run_all.py")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
