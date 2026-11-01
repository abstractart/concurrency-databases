-- ============================================================
-- R2. REPEATABLE READ при записи: PostgreSQL защищает от lost update
-- PostgreSQL. Два окна psql.
-- ============================================================

-- ── ТЕРМИНАЛ 1 ─────────────────────────────────────────────
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT balance FROM accounts WHERE id = 1;             -- 1000.00
-- пауза: запустите Т2, затем продолжайте
UPDATE accounts SET balance = 1000 - 100 WHERE id = 1; -- записали 900.00
COMMIT;

-- ── ТЕРМИНАЛ 2 (начните ПАРАЛЛЕЛЬНО с Т1, до его COMMIT) ───
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT balance FROM accounts WHERE id = 1;             -- тоже 1000.00 (старый снапшот)
UPDATE accounts SET balance = 1000 - 200 WHERE id = 1;
-- (выполните UPDATE после COMMIT в Т1):
-- ERROR:  could not serialize access due to concurrent update (SQLSTATE 40001)
ROLLBACK;   -- транзакция откатена; повторить её ЦЕЛИКОМ при новом снапшоте

-- ── Проверка ───────────────────────────────────────────────
SELECT balance FROM accounts WHERE id = 1;             -- 900.00: потерянного
                                                       -- обновления НЕТ
-- Сравните с MySQL (sql/mysql/r2_rr_write_conflict.sql): там конфликт
-- не обнаруживается и обновление теряется.
