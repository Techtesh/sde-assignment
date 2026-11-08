from datetime import timedelta

from test_controller import TS, chunk, open_store, sample_events
from test_experiments import setup, start, expose, record, seed_calls


def test_typed_evidence_backfill_matches_ingestion_and_is_not_repeated(database):
    events = sample_events()
    events += [{"event_id": 4, "type": "campaign_created", "ts": TS, "workflow_id": "wf", "campaign_id": "c1"},
               {**events[1], "event_id": 5, "engaged": True}]
    with open_store(database) as store:
        store.ingest(chunk(kind="events", count=5), events)
        expected = store.db.execute("SELECT * FROM person_metrics").fetchall()
        assert expected[0][7:10] == (2, 2, 1)
        assert expected[0][-3:] == (2, 1, 0)
        assert store.active_lead_groups({"workflow_id": "wf", "cadence": [2, 2]}, TS) == []
        for table in ("evidence_ready", "campaigns", "concluded_leads", "person_metrics"):
            store.db.execute(f"DELETE FROM {table}")
    with open_store(database) as store:
        assert store.db.execute("SELECT * FROM person_metrics").fetchall() == expected
        assert store.db.execute("SELECT count(*) FROM campaigns").fetchone()[0] == 1
    with open_store(database) as store:
        assert store.db.execute("SELECT * FROM person_metrics").fetchall() == expected


def test_first_repeat_split_preserves_outcomes_across_trial_and_promotion(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine)
        experiment = record(store, eid)
        later = first + timedelta(hours=72)
        seed_calls(store, 3, later, prefix="trial", promoted=True)
        end = (later + timedelta(hours=1)).isoformat()
        all_rows = store.collect_exposure(experiment, "monitor", 3, later.isoformat(), end)
        first_rows = store.collect_exposure(experiment, "monitor", 3, later.isoformat(), end, exposure="first")
        repeat_rows = store.collect_exposure(experiment, "monitor", 3, later.isoformat(), end, exposure="repeat")
        assert sum(row["dials"] for row in first_rows) == 875
        assert sum(row["dials"] for row in repeat_rows) == 4125
        for key in ("dials", "connected", "engaged"):
            assert sum(row[key] for row in all_rows) == sum(row[key] for row in first_rows + repeat_rows)
        assert store.collect_exposure(experiment, "monitor", 3, later.isoformat(), end, exposure="first") == first_rows


def test_decision_counts_do_not_depend_on_raw_json_queries(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine)
        experiment = record(store, eid)
        # Only this disposable test deletes raw rows; production retains them for audit.
        store.db.execute("DELETE FROM events")
        assert store.first_exposure(experiment, 2, first.isoformat()) is not None
        rows = store.collect_exposure(experiment, "without_raw", 2, first.isoformat(), (first+timedelta(hours=1)).isoformat())
        assert sum(row["dials"] for row in rows) == 5000
