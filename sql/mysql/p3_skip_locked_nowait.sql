-- ============================================================
-- P3. SKIP LOCKED / NOWAIT: очередь задач без ожиданий
-- MySQL 8+. Три окна mysql.
-- ============================================================

-- ── ТЕРМИНАЛ 1 — воркер, долго обрабатывает первую строку ──
BEGIN;
SELECT id, balance FROM accounts ORDER BY id LIMIT 1
  FOR UPDATE SKIP LOCKED;                              -- возьмёт id=1
DO SLEEP(15);                                          -- «обработка задачи»
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
-- ERROR 3572 (HY000): Statement aborted because lock(s) could not be
-- acquired immediately and NOWAIT is set
-- Ожидания не было вообще — приложение сразу знает «занято».
