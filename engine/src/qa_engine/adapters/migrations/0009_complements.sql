-- Folhas inseridas depois (a faltante apareceu): ficam na área de complementos do lote,
-- nunca na pasta original. Auditoria de quem inseriu e de quem removeu.
CREATE TABLE complements (
    page_id       TEXT PRIMARY KEY,
    batch_id      TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    document_id   TEXT NOT NULL,
    file          TEXT NOT NULL,
    sha256        TEXT NOT NULL,
    position      INTEGER NOT NULL,
    inserted_by   TEXT NOT NULL,
    inserted_at   TEXT NOT NULL,
    removed_by    TEXT,
    removed_at    TEXT
);
