-- Aprovar tudo como defeito de origem (ADR-0031): a decisão em lote pode valer para todas
-- as regras, leva a ressalva do revisor a cada decisão e só inclui página faltando quando
-- o revisor confirmou a lista de pastas e folhas.
ALTER TABLE operations ADD COLUMN note TEXT;
ALTER TABLE operations ADD COLUMN include_missing INTEGER NOT NULL DEFAULT 0;
