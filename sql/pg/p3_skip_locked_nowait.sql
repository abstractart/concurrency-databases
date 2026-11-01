-- ============================================================
-- P3. SKIP LOCKED / NOWAIT: очередь задач без ожиданий
-- PostgreSQL. Три окна psql.
-- ============================================================

-- ── ТЕРМИНАЛ 1 — воркер, долго обрабатывает первую строку ──
BEGIN;
SELECT id, balance FROM accounts ORDER BY id LIMIT 1
  FOR UPDATE SKIP LOCKED;                              -- возьмёт id=1
SELECT pg_sleep(15);                                   -- «обработка задачи»
UPDATE accounts SET balance = balance * 1.1 WHERE id = 1;
COMMIT;

-- ── ТЕРМИНАЛ 2 — второй воркер, пока Т1 спит ───────────────
BEGIN;
SELECT id, balance FROM accounts ORDER BY id LIMIT 1
  FOR UPDATE SKIP LOCKED;                              -- СРАЗУ вернёт id=2:
                                                       -- занятая id=1 пропущена, не ждали
UPDATE accounts SET balance = balance * 1.1 WHERE id = 2;
COMMIT;

-- ── ТЕРМИНАЛ 3 — NOWAIT: либо сразу, либо ошибка ───────────
SELECT id FROM accounts WHERE id = 1 FOR UPDATE NOWAIT;
-- ERROR:  could not obtain lock on row in relation "accounts" (SQLSTATE 55P03)
-- Ожидания не было вообще — приложение сразу знает «занято».
