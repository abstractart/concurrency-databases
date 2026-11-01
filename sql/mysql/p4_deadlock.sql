-- ============================================================
-- P4. Deadlock при встречных переводах
-- MySQL 8. Два окна mysql.
-- ============================================================

-- ── ТЕРМИНАЛ 1 — перевод 1→2 ───────────────────────────────
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;  -- сначала счёт 1
DO SLEEP(3);
SELECT balance FROM accounts WHERE id = 2 FOR UPDATE;  -- ← здесь deadlock:
-- ERROR 1213 (40001): Deadlock found when trying to get lock;
-- try restarting transaction
-- InnoDB мгновенно детектирует цикл и откатывает ОДНУ транзакцию (жертву).

-- ── ТЕРМИНАЛ 2 — перевод 2→1 (запустите, пока Т1 спит) ─────
BEGIN;
SELECT balance FROM accounts WHERE id = 2 FOR UPDATE;  -- сначала счёт 2
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;  -- ← цикл ожидания замкнулся
-- Жертва (получившая 1213): ROLLBACK; и повторить перевод заново.
-- Выжившая транзакция просто делает COMMIT.

-- ============================================================
-- ЛЕКАРСТВО: блокировать счёты в ОДНОМ порядке (по возрастанию id).
-- ============================================================

-- ── ТЕРМИНАЛ 1: перевод 1→2 ────────────────────────────────
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;  -- меньший id — первым
SELECT balance FROM accounts WHERE id = 2 FOR UPDATE;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;

-- ── ТЕРМИНАЛ 2: перевод 2→1, ТОЖЕ с меньшим id первым ──────
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;  -- подождёт Т1, и это ок
SELECT balance FROM accounts WHERE id = 2 FOR UPDATE;
UPDATE accounts SET balance = balance - 50 WHERE id = 2;
UPDATE accounts SET balance = balance + 50 WHERE id = 1;
COMMIT;                                                -- оба перевода прошли

-- Диагностика: SHOW ENGINE INNODB STATUS\G  (секция LATEST DETECTED DEADLOCK)
