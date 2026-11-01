-- ============================================================
-- R3. REPEATABLE READ + UPDATE с вычислением в запросе
-- PostgreSQL. Два окна psql.
-- ============================================================

-- ── ТЕРМИНАЛ 1 ─────────────────────────────────────────────
BEGIN ISOLATION LEVEL REPEATABLE READ;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;  -- от актуальных 1000 → 900.00
COMMIT;

-- ── ТЕРМИНАЛ 2 (начните параллельно, UPDATE — после COMMIT Т1) ──
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT balance FROM accounts WHERE id = 1;                 -- снапшот: 1000.00
UPDATE accounts SET balance = balance - 200 WHERE id = 1;
-- ERROR:  could not serialize access due to concurrent update (SQLSTATE 40001)
-- Относительное вычисление не спасает: RR запрещает UPDATE трогать строку,
-- изменённую после снапшота.
ROLLBACK;                                                  -- и повторить транзакцию:
                                                           -- спишет от актуальных данных
-- ── Проверка ───────────────────────────────────────────────
SELECT balance FROM accounts WHERE id = 1;                 -- 900.00 (T2 ещё не повторилась)

-- Для сравнения: на READ COMMITTED (дефолт) второй UPDATE без всякой ошибки
-- применился бы к актуальным 900 → итог 700. Относительное вычисление в
-- запросе + READ COMMITTED = классический «атомарный UPDATE».
