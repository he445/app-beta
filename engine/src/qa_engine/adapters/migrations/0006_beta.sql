-- Coleta do beta (ADR-0015): o que o modelo disse quando o revisor digitou a numeração,
-- exemplos rotulados (guardados só nesta máquina) e as métricas de cada lote, que
-- sobrevivem à retenção dos lotes (só contagens, nada de conteúdo de documento).
ALTER TABLE numbering_overrides ADD COLUMN model_value TEXT;
ALTER TABLE numbering_overrides ADD COLUMN model_state TEXT;

CREATE TABLE feedback (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL CHECK (kind IN ('numbering', 'orientation')),
    batch_id      TEXT NOT NULL,            -- sem chave estrangeira: sobrevive à retenção do lote
    page_id       TEXT NOT NULL,
    reviewer      TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    label_json    TEXT NOT NULL,            -- o que o revisor decidiu
    model_json    TEXT NOT NULL,            -- o que o modelo tinha dito
    image_file    TEXT,                     -- recorte ou miniatura em data_dir/feedback
    UNIQUE (kind, page_id)
);
CREATE INDEX feedback_created ON feedback(created_at);

CREATE TABLE beta_metrics (
    batch_id      TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    metrics_json  TEXT NOT NULL
);
