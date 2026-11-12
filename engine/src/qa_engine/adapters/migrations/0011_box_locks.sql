-- Trava por caixa: as caixas que esta máquina travou e o histórico das travas.
CREATE TABLE box_locks (
    batch_id      TEXT NOT NULL,
    box           TEXT NOT NULL,
    scope         TEXT NOT NULL CHECK (scope IN ('shared', 'local')),
    state         TEXT NOT NULL CHECK (state IN ('held', 'lost', 'released')),
    acquired_at   TEXT NOT NULL,
    renewed_at    TEXT,
    ended_at      TEXT,
    holder_json   TEXT,                     -- quem assumiu a caixa, quando a trava foi perdida
    PRIMARY KEY (batch_id, box)
);
CREATE INDEX box_locks_state ON box_locks(state);
CREATE TABLE box_lock_events (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    at            TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('acquired', 'taken_over', 'released', 'lost')),
    batch_id      TEXT NOT NULL,
    box           TEXT NOT NULL,
    who           TEXT NOT NULL,
    machine       TEXT NOT NULL,
    scope         TEXT NOT NULL,
    previous_json TEXT                      -- a trava abandonada assumida, ou a de quem assumiu
);
CREATE INDEX box_lock_events_batch ON box_lock_events(batch_id);
