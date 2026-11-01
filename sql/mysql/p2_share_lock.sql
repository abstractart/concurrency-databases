-- ============================================================
-- P2. Разделяемая блокировка: FOR SHARE (в MySQL 5.7 — LOCK IN SHARE MODE)
-- MySQL 8. Три окна mysql.
-- ============================================================

-- ── ТЕРМИНАЛ 1 и ТЕРМИНАЛ 2 — два читателя (выполните в обоих) ──
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR SHARE;   -- оба получают блокировку
                                                       -- сразу и одновременно
-- транзакции держим открытыми!

-- ── ТЕРМИНАЛ 3 — писатель (пока Т1 и Т2 открыты) ───────────
BEGIN;
SELECT balance FROM accounts WHERE id = 1 FOR UPDATE;  -- зависнет: ждёт читателей

-- ── Затем ──────────────────────────────────────────────────
-- В Т1 и Т2 выполните COMMIT (или ROLLBACK) —
-- и в Т3 мгновенно продолжится SELECT, после чего:
UPDATE accounts SET balance = balance + 500 WHERE id = 1;
COMMIT;

SELECT balance FROM accounts WHERE id = 1;             -- 1500.00
