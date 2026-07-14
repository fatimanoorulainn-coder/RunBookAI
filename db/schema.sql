-- RunbookAI PostgreSQL Schema
-- Stores infrastructure metadata, incidents, and agent investigation traces

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ============================================================
-- Services
-- Represents deployable services in the infrastructure
-- ============================================================

CREATE TABLE IF NOT EXISTS services (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    namespace VARCHAR(255) NOT NULL,
    owner_team VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- Deployments
-- Represents service deployments and their health state
-- ============================================================

CREATE TABLE IF NOT EXISTS deployments (
    id SERIAL PRIMARY KEY,
    service_id INTEGER NOT NULL,

    name VARCHAR(255) NOT NULL,
    replicas_expected INTEGER NOT NULL CHECK (replicas_expected >= 0),
    replicas_available INTEGER NOT NULL CHECK (replicas_available >= 0),

    status VARCHAR(50) NOT NULL DEFAULT 'Healthy'
        CHECK (status IN ('Healthy', 'Degraded')),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_deployment_service
        FOREIGN KEY (service_id)
        REFERENCES services(id)
        ON DELETE CASCADE
);


-- ============================================================
-- Pods
-- Represents individual running containers/pods
-- ============================================================

CREATE TABLE IF NOT EXISTS pods (
    id SERIAL PRIMARY KEY,
    deployment_id INTEGER NOT NULL,

    name VARCHAR(255) NOT NULL,

    phase VARCHAR(50) NOT NULL
        CHECK (phase IN ('Running', 'Failed')),

    restart_count INTEGER NOT NULL DEFAULT 0
        CHECK (restart_count >= 0),

    status_reason TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_pod_deployment
        FOREIGN KEY (deployment_id)
        REFERENCES deployments(id)
        ON DELETE CASCADE
);


-- ============================================================
-- Investigations
-- Represents an agent investigation session
-- ============================================================

CREATE TABLE IF NOT EXISTS investigations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    service_name VARCHAR(255) NOT NULL,

    status VARCHAR(50) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed'))
);


-- ============================================================
-- Investigation Traces
-- Stores every reasoning/tool execution step
-- ============================================================

CREATE TABLE IF NOT EXISTS investigation_traces (
    id SERIAL PRIMARY KEY,

    investigation_id UUID NOT NULL,

    step_number INTEGER NOT NULL
        CHECK (step_number > 0),

    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    tool_name VARCHAR(255) NOT NULL,

    tool_input JSONB,

    tool_output JSONB,

    CONSTRAINT fk_trace_investigation
        FOREIGN KEY (investigation_id)
        REFERENCES investigations(id)
        ON DELETE CASCADE,

    CONSTRAINT unique_step_per_investigation
        UNIQUE (investigation_id, step_number)
);


-- ============================================================
-- Indexes for faster agent queries
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_services_name
ON services(name);


CREATE INDEX IF NOT EXISTS idx_deployments_service
ON deployments(service_id);


CREATE INDEX IF NOT EXISTS idx_pods_deployment
ON pods(deployment_id);


CREATE INDEX IF NOT EXISTS idx_investigation_traces_lookup
ON investigation_traces(investigation_id, step_number);