-- Day 17: a Postgres role that can ONLY read the metadata tables.
-- The agent connects as this role, so even a validator bypass physically
-- cannot mutate, drop, or escalate — the database itself refuses.
--
-- Run once as a superuser (postgres):
--   psql -U postgres -d runbookai -f db/readonly_role.sql

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'runbookai_ro') THEN
        CREATE ROLE runbookai_ro LOGIN PASSWORD 'ro_potty123';
    END IF;
END $$;

-- No inherited privileges; grant exactly what's needed and nothing more.
GRANT CONNECT ON DATABASE runbookai TO runbookai_ro;
GRANT USAGE ON SCHEMA public TO runbookai_ro;
GRANT SELECT ON services, deployments, pods TO runbookai_ro;

-- Explicitly ensure no write path exists (defensive; these aren't granted above).
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM runbookai_ro;

-- Belt-and-suspenders: force every transaction on this role to be read-only,
-- so even a future accidental GRANT can't enable writes.
ALTER ROLE runbookai_ro SET default_transaction_read_only = on;