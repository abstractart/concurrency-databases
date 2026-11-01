-- ============================================================
-- Демо-схема для PostgreSQL: одна таблица accounts.
-- Python-кейсы (cases/*.py) пересоздают её автоматически при каждом запуске,
-- этот файл — для ручных прогонов в psql.
-- ============================================================

DROP TABLE IF EXISTS accounts;

CREATE TABLE accounts (
    id         INTEGER PRIMARY KEY,
    owner      VARCHAR(100)  NOT NULL,
    balance    NUMERIC(12,2) NOT NULL DEFAULT 0,
    version    INTEGER       NOT NULL DEFAULT 0,
    updated_at TIMESTAMP(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO accounts (id, owner, balance) VALUES
    (1, 'Алиса', 1000.00),
    (2, 'Боб',    1000.00),
    (3, 'Кэрол',  1000.00);
