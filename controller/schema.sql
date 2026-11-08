CREATE TABLE IF NOT EXISTS controller_runs (
    run_id text PRIMARY KEY,
    simulator_url text NOT NULL,
    last_ts timestamptz,
    state jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS controller_endpoints (
    simulator_url text PRIMARY KEY,
    run_id text NOT NULL REFERENCES controller_runs,
    generation integer NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_snapshots (
    run_id text NOT NULL REFERENCES controller_runs,
    workflow_id text NOT NULL,
    definition jsonb NOT NULL,
    PRIMARY KEY (run_id, workflow_id)
);

CREATE TABLE IF NOT EXISTS loop_ticks (
    run_id text NOT NULL REFERENCES controller_runs,
    ts timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    metrics jsonb NOT NULL,
    PRIMARY KEY (run_id, ts)
);

CREATE TABLE IF NOT EXISTS loop_starts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id text NOT NULL REFERENCES controller_runs,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    sim_ts timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS recent_loop_starts ON loop_starts(run_id,started_at);

CREATE TABLE IF NOT EXISTS config_history (
    run_id text NOT NULL REFERENCES controller_runs,
    workflow_id text NOT NULL,
    version integer NOT NULL,
    snapshot jsonb NOT NULL,
    PRIMARY KEY (run_id, workflow_id, version)
);

CREATE TABLE IF NOT EXISTS ingested_chunks (
    run_id text NOT NULL REFERENCES controller_runs,
    chunk bigint NOT NULL,
    kind text NOT NULL CHECK (kind IN ('history', 'events')),
    event_count bigint NOT NULL,
    PRIMARY KEY (run_id, chunk)
);

CREATE TABLE IF NOT EXISTS events (
    run_id text NOT NULL REFERENCES controller_runs,
    event_id bigint NOT NULL,
    chunk bigint NOT NULL,
    history boolean NOT NULL,
    ts timestamptz NOT NULL,
    workflow_id text NOT NULL,
    kind text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (run_id, event_id)
);
CREATE INDEX IF NOT EXISTS events_workflow_time ON events (run_id, workflow_id, ts);

CREATE TABLE IF NOT EXISTS leads (
    run_id text NOT NULL REFERENCES controller_runs,
    workflow_id text NOT NULL,
    lead_id text NOT NULL,
    person_id text NOT NULL,
    campaign_id text NOT NULL,
    features jsonb NOT NULL,
    PRIMARY KEY (run_id, workflow_id, lead_id)
);

CREATE TABLE IF NOT EXISTS hourly_metrics (
    run_id text NOT NULL REFERENCES controller_runs,
    workflow_id text NOT NULL,
    history boolean NOT NULL,
    hour timestamptz NOT NULL,
    config_version integer NOT NULL,
    cohort_id text NOT NULL,
    dimension text NOT NULL,
    variant text NOT NULL,
    dials bigint NOT NULL,
    connected bigint NOT NULL,
    engaged bigint NOT NULL,
    hallucinations bigint NOT NULL,
    PRIMARY KEY (run_id, workflow_id, history, hour, config_version, cohort_id, dimension, variant)
);

CREATE TABLE IF NOT EXISTS audit_log (
    run_id text NOT NULL REFERENCES controller_runs,
    event_id bigint NOT NULL,
    ts timestamptz NOT NULL,
    workflow_id text NOT NULL,
    kind text NOT NULL,
    actor text,
    evidence jsonb NOT NULL,
    PRIMARY KEY (run_id, event_id)
);

CREATE TABLE IF NOT EXISTS proposals (
    run_id text NOT NULL REFERENCES controller_runs,
    proposal_id text NOT NULL,
    decision_id text NOT NULL,
    workflow_id text NOT NULL,
    base_config jsonb NOT NULL,
    body jsonb NOT NULL,
    route text NOT NULL CHECK (route IN ('auto', 'approval')),
    status text NOT NULL CHECK (status IN
        ('planned','submitted','pending','approved','applying','applied','rejected',
         'expired','lapsed','stale','blocked','superseded')),
    urgent boolean NOT NULL,
    created_at timestamptz NOT NULL,
    submitted_at timestamptz,
    approval_id text,
    parent_id text,
    response jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (run_id, proposal_id),
    UNIQUE (run_id, decision_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_proposal ON proposals (run_id, workflow_id)
    WHERE status IN ('planned','submitted','pending','approved','applying');

CREATE TABLE IF NOT EXISTS proposal_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id text NOT NULL,
    proposal_id text NOT NULL,
    ts timestamptz NOT NULL,
    status text NOT NULL,
    evidence jsonb NOT NULL,
    FOREIGN KEY (run_id, proposal_id) REFERENCES proposals (run_id, proposal_id)
);

CREATE TABLE IF NOT EXISTS detection_windows (
    run_id text NOT NULL REFERENCES controller_runs,
    workflow_id text NOT NULL,
    config_version integer NOT NULL,
    kind text NOT NULL,
    subject text NOT NULL,
    hour timestamptz NOT NULL,
    streak integer NOT NULL,
    episode_start timestamptz NOT NULL,
    evidence jsonb NOT NULL,
    PRIMARY KEY (run_id,workflow_id,config_version,kind,subject,hour)
);

CREATE TABLE IF NOT EXISTS incidents (
    run_id text NOT NULL REFERENCES controller_runs,
    incident_id text NOT NULL,
    workflow_id text NOT NULL,
    tenant_id text NOT NULL,
    kind text NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL,
    proposal_id text,
    data jsonb NOT NULL,
    PRIMARY KEY (run_id,incident_id)
);
CREATE INDEX IF NOT EXISTS incidents_workflow ON incidents (run_id,workflow_id,status);

CREATE TABLE IF NOT EXISTS incident_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id text NOT NULL,
    incident_id text NOT NULL,
    ts timestamptz NOT NULL,
    status text NOT NULL,
    evidence jsonb NOT NULL,
    FOREIGN KEY (run_id,incident_id) REFERENCES incidents (run_id,incident_id)
);

CREATE TABLE IF NOT EXISTS credit_budgets (
    run_id text PRIMARY KEY REFERENCES controller_runs,
    initial_credits double precision NOT NULL
);

CREATE TABLE IF NOT EXISTS external_actions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id text NOT NULL,
    action_id text NOT NULL,
    incident_id text NOT NULL,
    tenant_id text NOT NULL,
    kind text NOT NULL,
    cost integer NOT NULL CHECK (cost > 0),
    created_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('uncertain','succeeded','failed')),
    request jsonb NOT NULL,
    response jsonb NOT NULL DEFAULT '{}',
    UNIQUE (run_id,action_id),
    FOREIGN KEY (run_id,incident_id) REFERENCES incidents (run_id,incident_id)
);

CREATE TABLE IF NOT EXISTS experiments (
    run_id text NOT NULL REFERENCES controller_runs,
    experiment_id text NOT NULL,
    workflow_id text NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL,
    proposal_id text,
    data jsonb NOT NULL,
    PRIMARY KEY (run_id,experiment_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_experiment ON experiments (run_id,workflow_id)
    WHERE status IN ('planned','running','promoting','monitoring','restoring');

CREATE TABLE IF NOT EXISTS experiment_audit (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id text NOT NULL,
    experiment_id text NOT NULL,
    ts timestamptz NOT NULL,
    status text NOT NULL,
    evidence jsonb NOT NULL,
    FOREIGN KEY (run_id,experiment_id) REFERENCES experiments (run_id,experiment_id)
);

CREATE TABLE IF NOT EXISTS experiment_people (
    run_id text NOT NULL,
    experiment_id text NOT NULL,
    phase text NOT NULL,
    person_id text NOT NULL,
    voice text NOT NULL,
    dials bigint NOT NULL,
    connected bigint NOT NULL,
    engaged bigint NOT NULL,
    PRIMARY KEY (run_id,experiment_id,phase,person_id,voice),
    FOREIGN KEY (run_id,experiment_id) REFERENCES experiments (run_id,experiment_id)
);

CREATE TABLE IF NOT EXISTS experiment_windows (
    run_id text NOT NULL,
    experiment_id text NOT NULL,
    phase text NOT NULL,
    end_at timestamptz NOT NULL,
    PRIMARY KEY (run_id,experiment_id,phase,end_at),
    FOREIGN KEY (run_id,experiment_id) REFERENCES experiments (run_id,experiment_id)
);

CREATE TABLE IF NOT EXISTS campaigns (
    run_id text NOT NULL REFERENCES controller_runs,
    workflow_id text NOT NULL,
    campaign_id text NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (run_id,workflow_id,campaign_id)
);

CREATE TABLE IF NOT EXISTS concluded_leads (
    run_id text NOT NULL REFERENCES controller_runs,
    workflow_id text NOT NULL,
    lead_id text NOT NULL,
    PRIMARY KEY (run_id,workflow_id,lead_id)
);

CREATE TABLE IF NOT EXISTS person_metrics (
    run_id text NOT NULL REFERENCES controller_runs,
    workflow_id text NOT NULL,
    config_version integer NOT NULL,
    cohort_id text NOT NULL,
    ts timestamptz NOT NULL,
    person_id text NOT NULL,
    voice text NOT NULL,
    dials bigint NOT NULL,
    connected bigint NOT NULL,
    engaged bigint NOT NULL,
    first_event_id bigint NOT NULL,
    first_connected integer NOT NULL,
    first_engaged integer NOT NULL,
    PRIMARY KEY (run_id,workflow_id,config_version,cohort_id,ts,person_id,voice)
);

CREATE TABLE IF NOT EXISTS evidence_ready (
    run_id text PRIMARY KEY REFERENCES controller_runs
);
