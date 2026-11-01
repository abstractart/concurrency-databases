-- ============================================================
-- P1. Пессимистичная блокировка: SELECT ... FOR UPDATE
-- PostgreSQL. Два окна psql.
-- ============================================================

-- ── ТЕРМИНАЛ 1 ─────────────────────────────────────────────
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;   -- 🔒 строка заблокирована
SELECT pg_sleep(10);                                    -- «долгая работа» (10 с)
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
COMMIT;                                                 -- только теперь продолжится Т2

-- ── ТЕРМИНАЛ 2 (запустите, пока Т1 спит) ───────────────────
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;   -- 🔒 висит в ожидании Т1
-- ...после COMMIT в Т1 запрос мгновенно вернёт УЖЕ 900.00:
UPDATE accounts SET balance = balance - 200 WHERE id = 1;
COMMIT;                                                 -- итог 700.00, ничего не потеряно

-- ── Проверка ───────────────────────────────────────────────
SELECT balance FROM accounts WHERE id = 1;              -- 700.00

-- Сброс данных: common/schema.pg.sql
