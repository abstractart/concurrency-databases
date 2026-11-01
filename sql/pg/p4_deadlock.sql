-- ============================================================
-- P4. Deadlock при встречных переводах
-- PostgreSQL. Два окна psql.
-- ============================================================

-- ── ТЕРМИНАЛ 1 — перевод 1→2 ───────────────────────────────
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;  -- сначала счёт 1
SELECT pg_sleep(3);
SELECT balance FROM accounts WHERE id = 2 FOR UPDATE;  -- ← здесь deadlock:
-- ERROR: deadlock detected (SQLSTATE 40P01)
-- СУБД сама выбрала жертву и откатила одну из транзакций.

-- ── ТЕРМИНАЛ 2 — перевод 2→1 (запустите, пока Т1 спит) ─────
BEGIN;
SELECT balance FROM accounts WHERE id = 2 FOR UPDATE;  -- сначала счёт 2
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;  -- ← цикл ожидания замкнулся
-- Одна из транзакций получит 40P01 и должна повториться:
--   ROLLBACK;  и выполнить перевод заново.
-- Выжившая транзакция просто делает COMMIT.

-- ============================================================
-- ЛЕКАРСТВО: блокировать счёты в ОДНОМ порядке (по возрастанию id).
-- Тогда цикл невозможен по построению — вторая транзакция просто ждёт.
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
