-- Liberação por processo (ADR-0018): processos prontos e os que faltam, na ordem do lote.
-- JSON: {"ready": [{"id", "name"}], "pending": [{"id", "name"}]}.
ALTER TABLE batches ADD COLUMN queue_json TEXT;
