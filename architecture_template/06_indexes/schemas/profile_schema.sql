-- Native memory mode only. Off by default.
-- Canonical profile memory is normally delegated to an external/local-first memory provider.

CREATE TABLE IF NOT EXISTS profile_traits (
  id TEXT PRIMARY KEY,
  trait TEXT NOT NULL,
  evidence TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

