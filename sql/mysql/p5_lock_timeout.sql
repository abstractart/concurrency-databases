-- ============================================================
-- P5. Таймаут ожидания блокировки: innodb_lock_wait_timeout
-- MySQL 8. Два окна mysql.
-- ============================================================

-- ── ТЕРМИНАЛ 1 ─────────────────────────────────────────────
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;  -- держим строку
DO SLEEP(5);                                           -- 5 секунд «работы»

-- ── ТЕРМИНАЛ 2 (пока Т1 спит) ──────────────────────────────
SET SESSION innodb_lock_wait_timeout = 2;              -- не ждать дольше 2 с
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;
-- через 2 секунды:
-- ERROR 1205 (HY000): Lock wait timeout exceeded; try restarting transaction
ROLLBACK;
-- Нюанс: по умолчанию (innodb_rollback_on_timeout=OFF) при 1205
-- откатывается только последний запрос, а транзакция формально жива.
-- Явный ROLLBACK делает завершение предсказуемым.

-- ── ТЕРМИНАЛ 1 (после сна) ─────────────────────────────────
COMMIT;                                                -- отпускаем строку
