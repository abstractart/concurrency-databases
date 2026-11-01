-- ============================================================
-- Демо-схема для MySQL 8: одна таблица accounts.
-- Python-кейсы (cases/*.py) пересоздают её автоматически при каждом запуске,
-- этот файл — для ручных прогонов в mysql.
-- ============================================================

DROP TABLE IF EXISTS accounts;

CREATE TABLE accounts (
    id         INT PRIMARY KEY,
    owner      VARCHAR(100)  NOT NULL,
    balance    DECIMAL(12,2) NOT NULL DEFAULT 0,
    version    INT           NOT NULL DEFAULT 0,
    -- TIMESTAMP(6) — с микросекундами: нужно для кейса O2 (проверка по updated_at)
    updated_at TIMESTAMP(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) CHARACTER SET utf8mb4;

INSERT INTO accounts (id, owner, balance) VALUES
    (1, 'Алиса', 1000.00),
    (2, 'Боб',    1000.00),
    (3, 'Кэрол',  1000.00);
