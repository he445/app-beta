-- Trava por caixa: quem travou, renovou, assumiu (trava abandonada) ou soltou.
CREATE TABLE box_lock_events (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    at            TEXT NOT NULL,
    box           TEXT NOT NULL,
    action        TEXT NOT NULL CHECK (action IN ('acquire', 'take_over', 'release')),
    who           TEXT NOT NULL,
    machine       TEXT NOT NULL,
    details_json  TEXT
);
