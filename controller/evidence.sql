INSERT INTO campaigns
SELECT run_id,workflow_id,payload->>'campaign_id',min(ts) FROM {source}
WHERE kind='campaign_created' GROUP BY 1,2,3
ON CONFLICT (run_id,workflow_id,campaign_id) DO UPDATE
SET created_at=LEAST(campaigns.created_at,EXCLUDED.created_at);

INSERT INTO concluded_leads
SELECT DISTINCT run_id,workflow_id,payload->>'lead_id' FROM {source}
WHERE kind='call' AND (payload->>'engaged')::boolean ON CONFLICT DO NOTHING;

INSERT INTO person_metrics
SELECT run_id,workflow_id,(payload->>'config_version')::integer,payload->>'cohort_id',
       ts,payload->>'person_id',payload->'variant'->>'voice',count(*),
       count(*) FILTER (WHERE (payload->>'connected')::boolean),
       count(*) FILTER (WHERE (payload->>'engaged')::boolean),min(event_id),
       (array_agg((payload->>'connected')::boolean::integer ORDER BY event_id))[1],
       (array_agg((payload->>'engaged')::boolean::integer ORDER BY event_id))[1]
FROM {source} WHERE kind='call' AND NOT history GROUP BY 1,2,3,4,5,6,7
ON CONFLICT (run_id,workflow_id,config_version,cohort_id,ts,person_id,voice) DO UPDATE
SET dials=person_metrics.dials+EXCLUDED.dials,
    connected=person_metrics.connected+EXCLUDED.connected,
    engaged=person_metrics.engaged+EXCLUDED.engaged,
    first_connected=CASE WHEN EXCLUDED.first_event_id<person_metrics.first_event_id
                        THEN EXCLUDED.first_connected ELSE person_metrics.first_connected END,
    first_engaged=CASE WHEN EXCLUDED.first_event_id<person_metrics.first_event_id
                      THEN EXCLUDED.first_engaged ELSE person_metrics.first_engaged END,
    first_event_id=LEAST(person_metrics.first_event_id,EXCLUDED.first_event_id);
