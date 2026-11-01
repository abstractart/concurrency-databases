-- ============================================================
-- R3. REPEATABLE READ + UPDATE с вычислением в запросе
-- MySQL 8. Два окна mysql.
-- ============================================================

-- ── ТЕРМИНАЛ 1 ─────────────────────────────────────────────
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;  -- current read: 1000 → 900.00
COMMIT;

-- ── ТЕРМИНАЛ 2 (начните параллельно, UPDATE — после COMMIT Т1) ──
BEGIN;
SELECT balance FROM accounts WHERE id = 1;                 -- снапшот RR: 1000.00
UPDATE accounts SET balance = balance - 200 WHERE id = 1;  -- current read: 900 → 700.00!
COMMIT;                                                    -- БЕЗ ошибок

SELECT balance FROM accounts WHERE id = 1;                 -- 700.00 — ничего не потеряно

-- Смысл: в InnoDB UPDATE всегда читает последнюю зафиксированную версию
-- строки («current read»), поэтому арифметика в самом запросе считается
-- от АКТУАЛЬНОГО значения, а не от снапшота.
-- Сравните с r2_rr_write_conflict.sql: там «SET balance = <значение из
-- снапшота>» молча затирало чужую запись. Разница только в том,
-- где считается выражение — в приложении или в СУБД.
