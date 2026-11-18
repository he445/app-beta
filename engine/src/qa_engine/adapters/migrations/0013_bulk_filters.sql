-- Corrigir pasta / Corrigir tudo / Decidir semelhantes (ADR-0024): a operação em lote
-- guarda a regra filtrada, a decisão aplicada (vazia = corrigir o automático) e se rodou
-- com a caixa ainda em análise (só nos processos prontos).
ALTER TABLE operations ADD COLUMN rule TEXT;
ALTER TABLE operations ADD COLUMN action TEXT
    CHECK (action IS NULL OR action IN ('approve', 'reject', 'source_defect'));
ALTER TABLE operations ADD COLUMN partial INTEGER NOT NULL DEFAULT 0;
