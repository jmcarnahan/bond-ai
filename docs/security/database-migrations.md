# Database Migrations — Security Threat Model Remediation

**Baseline**: `Common Tools` PR (#151, commit 7fd0909)
**Target**: `security-threat-model-remediation` + `security-phase4-authorization` branches

These SQL statements must be run against Aurora PostgreSQL in each deployment environment before deploying the corresponding code changes.

---

## Migration Order

Run these in order. Each section can be run independently, but the order ensures tables exist before any code references them.

---

## 1. New Table: `auth_oauth_states` (Phase 2 — OAuth state for login flow)

Stores temporary OAuth state during the primary login flow. Unlike `connection_oauth_states`, this table has NO foreign key to `users` because the user hasn't authenticated yet when login is initiated. Records auto-cleaned after 10 minutes.

```sql
CREATE TABLE IF NOT EXISTS auth_oauth_states (
    state VARCHAR NOT NULL PRIMARY KEY,
    provider_name VARCHAR NOT NULL,
    code_verifier VARCHAR,
    redirect_uri VARCHAR,
    platform VARCHAR,
    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'utc')
);
```

## 2. New Table: `auth_codes` (Phase 3 — Authorization code exchange)

Short-lived authorization codes for the token exchange flow. After OAuth callback, a code is issued and the frontend exchanges it for either an HttpOnly cookie (web) or a bearer token (mobile). Codes are single-use and expire after 60 seconds.

```sql
CREATE TABLE IF NOT EXISTS auth_codes (
    code VARCHAR NOT NULL PRIMARY KEY,
    access_token VARCHAR NOT NULL,
    user_id VARCHAR NOT NULL,
    platform VARCHAR,
    created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'utc'),
    used_at TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);
```

## 3. New Table: `revoked_tokens` (Phase 3 — Token revocation)

Tracks revoked JWT tokens by their `jti` claim. Used by `POST /auth/logout` to invalidate tokens before natural expiry. The `expires_at` field (copied from the JWT `exp` claim) enables periodic cleanup of expired records.

```sql
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti VARCHAR NOT NULL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    revoked_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'utc'),
    expires_at TIMESTAMP NOT NULL
);
```

## 4. Alter Table: `users` — Add `is_admin` column (Phase 4 — DB-backed admin role)

Adds a boolean `is_admin` column to the users table. This replaces the email-match-only admin check with a DB-backed role. The `ADMIN_USERS` env var still serves as a bootstrap mechanism — admin status is synced from the env var to the DB on each login.

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;
```

After running this, existing users will have `is_admin = FALSE`. They will be updated automatically on their next login if their email is in the `ADMIN_USERS` environment variable. To set admin status immediately without waiting for login:

```sql
-- Replace with actual admin email(s)
UPDATE users SET is_admin = TRUE WHERE email IN ('admin@yourcompany.com');
```

---

## Cleanup Queries (Optional, run periodically)

These are not migrations but useful maintenance queries:

```sql
-- Clean up expired auth codes (older than 5 minutes)
DELETE FROM auth_codes WHERE expires_at < (NOW() AT TIME ZONE 'utc' - INTERVAL '5 minutes');

-- Clean up expired revoked tokens (JWT has naturally expired, no need to track)
DELETE FROM revoked_tokens WHERE expires_at < (NOW() AT TIME ZONE 'utc');

-- Clean up stale OAuth states (older than 10 minutes)
DELETE FROM auth_oauth_states WHERE created_at < (NOW() AT TIME ZONE 'utc' - INTERVAL '10 minutes');
```

---

## Verification

After running the migrations, verify the schema:

```sql
-- Check new tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('auth_oauth_states', 'auth_codes', 'revoked_tokens')
ORDER BY table_name;

-- Check is_admin column exists on users
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'users' AND column_name = 'is_admin';
```

Expected output:
- 3 new tables: `auth_oauth_states`, `auth_codes`, `revoked_tokens`
- `users.is_admin`: boolean, default FALSE

---

## 5. ALTER agents table: Add `slug` column (Agent Forwarding)

Human-readable agent identifier (e.g. `brave-sailing-fox`) used for agent-to-agent forwarding and as a stable, user-facing reference. Auto-generated on agent creation; backfilled on startup for existing agents.

```sql
ALTER TABLE agents ADD COLUMN slug VARCHAR;
CREATE UNIQUE INDEX ix_agents_slug ON agents (slug);
```

After deploying the code, the application will auto-backfill slugs for existing agents on startup via `_backfill_agent_slugs()`.

---

## Notes

- **SQLite (local dev)**: These migrations are NOT needed. `Base.metadata.create_all()` creates tables automatically on startup. The `ALTER TABLE` for `is_admin` is handled by SQLAlchemy's column default.
- **Aurora PostgreSQL (deployed)**: Must be run manually via the AWS RDS Query Editor or psql before deploying the code changes.
- **Rollback**: To undo, `DROP TABLE auth_oauth_states, auth_codes, revoked_tokens;` and `ALTER TABLE users DROP COLUMN is_admin;`. Note: dropping `revoked_tokens` means any revoked tokens become valid again until they naturally expire.
