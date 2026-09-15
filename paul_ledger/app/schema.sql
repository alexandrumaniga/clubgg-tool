-- Paul's Book — D1 schema
-- Ledger is stored as one versioned JSON document in kv('state').
CREATE TABLE IF NOT EXISTS kv (
  key     TEXT PRIMARY KEY,
  value   TEXT,
  updated INTEGER
);
-- Access codes. Entering a valid, non-revoked code logs a device in.
CREATE TABLE IF NOT EXISTS codes (
  code     TEXT PRIMARY KEY,
  label    TEXT,
  is_admin INTEGER DEFAULT 0,
  revoked  INTEGER DEFAULT 0,
  created  INTEGER
);
