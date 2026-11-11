-- Lote local lido no lugar (ADR-0013): de onde veio o lote e em que etapa está.
-- source: upload (enviado pelo navegador), demo (lote de demonstração) ou local (pasta no lugar).
-- Lote local nunca tem a pasta "root" apagada pela retenção: ela é o original.
ALTER TABLE batches ADD COLUMN source TEXT NOT NULL DEFAULT 'upload'
    CHECK (source IN ('upload', 'demo', 'local'));
ALTER TABLE batches ADD COLUMN stage TEXT
    CHECK (stage IS NULL OR stage IN ('settling', 'snapshot', 'analyzing'));
