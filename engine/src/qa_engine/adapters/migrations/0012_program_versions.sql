-- Versões do programa que abriram este banco (para saber de qual versão veio a atualização).
CREATE TABLE program_versions (
    version          TEXT PRIMARY KEY,
    first_opened_at  TEXT NOT NULL,
    last_opened_at   TEXT NOT NULL
);
