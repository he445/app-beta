-- Histórico de configuração: quem mudou, quando, o valor anterior e o novo.
CREATE TABLE config_history (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    at            TEXT NOT NULL,
    who           TEXT NOT NULL,
    scope         TEXT NOT NULL CHECK (scope IN ('settings', 'profile')),
    target        TEXT NOT NULL,            -- perfil (id) ou camada de configuração (user)
    key           TEXT NOT NULL,            -- chave com pontos: stations.cg-e3.rules.blur.params.dark_level
    before_json   TEXT,
    after_json    TEXT
);
CREATE INDEX config_history_at ON config_history(at);
