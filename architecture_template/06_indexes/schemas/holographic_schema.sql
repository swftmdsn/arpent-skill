-- Native memory mode only. Off by default.
-- Durable observations and buffer items are normally delegated to the active memory provider.

CREATE TABLE IF NOT EXISTS observations (
  id TEXT PRIMARY KEY,
  body TEXT NOT NULL,
  role TEXT NOT NULL,
  source TEXT,
  expires_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

