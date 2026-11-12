-- Ordem das páginas escolhida pelo revisor na tela de Sequência (arrastar, Alt + setas).
-- Vale sobre a ordem proposta pelo resolvedor no lote corrigido; apagar a linha desfaz.
CREATE TABLE manual_orders (
    document_id   TEXT PRIMARY KEY,
    batch_id      TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    page_ids      TEXT NOT NULL,  -- JSON: lista com todas as páginas do documento
    reviewer      TEXT NOT NULL,
    decided_at    TEXT NOT NULL
);
CREATE INDEX manual_orders_batch ON manual_orders(batch_id);
