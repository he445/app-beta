-- Esquema inicial. SQL puro, legível por qualquer linguagem (ADR-0005).
CREATE TABLE batches (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    profile_id    TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'analyzed', 'failed')),
    done          INTEGER NOT NULL DEFAULT 0,
    total         INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,            -- ISO 8601 UTC
    root          TEXT NOT NULL,            -- pasta do lote no servidor
    error         TEXT,
    report_json   TEXT,                     -- analysis.schema.json, sem as sinalizações
    summary_json  TEXT                      -- batch-summary.schema.json atualizado a cada decisão
);

CREATE TABLE pages (
    id            TEXT PRIMARY KEY,
    batch_id      TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    document_id   TEXT NOT NULL,
    source_file   TEXT NOT NULL,
    page_in_file  INTEGER NOT NULL,
    dpi           REAL
);
CREATE INDEX pages_batch ON pages(batch_id);

CREATE TABLE findings (
    id            TEXT PRIMARY KEY,
    batch_id      TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    ord           INTEGER NOT NULL,
    rule          TEXT NOT NULL,
    severity      TEXT NOT NULL,
    target_kind   TEXT NOT NULL,
    target_id     TEXT NOT NULL,
    finding_json  TEXT NOT NULL             -- finding.schema.json, com a decisão vigente
);
CREATE INDEX findings_batch ON findings(batch_id, ord);

-- Histórico imutável de decisões: mede a precisão real de cada regra (calibração contínua).
CREATE TABLE decisions (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id    TEXT NOT NULL,
    batch_id      TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    rule          TEXT NOT NULL,
    action        TEXT NOT NULL,
    reviewer      TEXT NOT NULL,
    decided_at    TEXT NOT NULL,
    note          TEXT
);
CREATE INDEX decisions_rule ON decisions(rule, action);

CREATE TABLE numbering_overrides (
    page_id       TEXT PRIMARY KEY REFERENCES pages(id) ON DELETE CASCADE,
    batch_id      TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    value         TEXT NOT NULL,
    reviewer      TEXT NOT NULL,
    decided_at    TEXT NOT NULL
);
