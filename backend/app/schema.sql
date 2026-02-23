PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    model_used TEXT,
    iterations INTEGER,
    sample_size INTEGER,
    config_json TEXT
);

CREATE TABLE IF NOT EXISTS nodes (
    id TEXT NOT NULL,
    name TEXT NOT NULL,
    tier TEXT,
    stage INTEGER NOT NULL DEFAULT 0,
    lane TEXT NOT NULL DEFAULT 'hybrid',
    description TEXT,
    unlock_condition TEXT,
    support_count INTEGER NOT NULL DEFAULT 0,
    run_id TEXT NOT NULL,
    PRIMARY KEY (run_id, id),
    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL CHECK (edge_type IN ('primary', 'weak')),
    is_direct INTEGER NOT NULL CHECK (is_direct IN (0, 1)),
    stage_jump INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, source_id) REFERENCES nodes (run_id, id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, target_id) REFERENCES nodes (run_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_title TEXT,
    quote TEXT,
    why TEXT,
    folder_status TEXT,
    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id, node_id) REFERENCES nodes (run_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT NOT NULL,
    title TEXT,
    folder_status TEXT,
    text TEXT,
    text_hash TEXT,
    run_id TEXT NOT NULL,
    PRIMARY KEY (run_id, source_id),
    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fragments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    fragment_index INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    validation_report TEXT,
    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_nodes_run_stage_lane ON nodes (run_id, stage, lane);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges (run_id, source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges (run_id, target_id);
CREATE INDEX IF NOT EXISTS idx_citations_node ON citations (run_id, node_id);
CREATE INDEX IF NOT EXISTS idx_sources_title ON sources (run_id, title);

