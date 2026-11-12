-- Relatório por caixa: cada versão fica guardada; uma nova só sai quando as pendências mudam.
CREATE TABLE box_reports (
    id            TEXT PRIMARY KEY,
    batch_id      TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    box           TEXT NOT NULL,
    version       INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    state         TEXT NOT NULL CHECK (state IN ('clean', 'pending', 'resolved')),
    pendencies    TEXT NOT NULL,            -- chave das pendências, para saber se mudou
    report_json   TEXT NOT NULL,            -- box-report.schema.json
    UNIQUE (batch_id, box, version)
);
