-- ============================================================
-- P0. Потерянное обновление БЕЗ блокировок
-- MySQL 8 (InnoDB), дефолтный REPEATABLE READ.
-- Два окна: mysql -h127.0.0.1 -uroot -proot demo
-- ============================================================

-- ── ТЕРМИНАЛ 1 ─────────────────────────────────────────────
BEGIN;
SELECT balance FROM accounts WHERE id = 1;              -- 1000.00
-- НЕ фиксируйте сразу: сначала выполните блок в терминале 2
UPDATE accounts SET balance = 1000 - 100 WHERE id = 1;  -- значение посчитано в приложении
COMMIT;

-- ── ТЕРМИНАЛ 2 (пока Т1 стоит между SELECT и UPDATE) ───────
BEGIN;
SELECT balance FROM accounts WHERE id = 1;              -- тоже 1000.00 (снапшот RR)
UPDATE accounts SET balance = 1000 - 200 WHERE id = 1;
COMMIT;                                                 -- пройдёт БЕЗ ошибок

-- ── Проверка (в любом окне) ────────────────────────────────
SELECT balance FROM accounts WHERE id = 1;              -- 800 вместо 700!
-- Списание Т1 (−100) молча потеряно.

-- Сброс данных: common/schema.mysql.sql
