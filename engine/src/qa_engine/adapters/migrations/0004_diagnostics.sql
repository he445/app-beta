-- Diagnóstico (ADR-0016): erros do motor, dos processos de análise, da abertura e da
-- interface. Nunca imagem nem texto de documento; caminhos absolutos já mascarados.
CREATE TABLE diagnostics (
    id          TEXT PRIMARY KEY,
    signature   TEXT NOT NULL,
    at          TEXT NOT NULL,            -- ISO 8601 UTC
    record_json TEXT NOT NULL             -- registro completo (application/diagnostics.py)
);
CREATE INDEX diagnostics_signature ON diagnostics(signature);
CREATE INDEX diagnostics_at ON diagnostics(at);

CREATE TABLE diagnostic_resolutions (
    signature   TEXT PRIMARY KEY,
    resolved_at TEXT NOT NULL,
    resolved_by TEXT NOT NULL
);
