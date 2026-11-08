-- Correção em lote: cada decisão guarda a operação que a registrou (desfazer em lote).
ALTER TABLE decisions ADD COLUMN operation_id TEXT;
CREATE INDEX decisions_operation ON decisions(operation_id);

CREATE TABLE operations (
    id            TEXT PRIMARY KEY,
    batch_id      TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    scope_kind    TEXT NOT NULL CHECK (scope_kind IN ('batch', 'document')),
    scope_id      TEXT NOT NULL,
    status        TEXT NOT NULL
                  CHECK (status IN ('queued', 'running', 'applied', 'saved', 'undone', 'failed')),
    done          INTEGER NOT NULL DEFAULT 0,
    total         INTEGER NOT NULL DEFAULT 0,
    current       TEXT,
    reviewer      TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    saved_at      TEXT,
    error         TEXT,
    result_json   TEXT,                     -- bulk-correction.schema.json#/properties/result
    undo_json     TEXT                      -- bulk-correction.schema.json#/properties/undo
);
CREATE INDEX operations_batch ON operations(batch_id, started_at);
