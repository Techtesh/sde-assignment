import random
from datetime import timedelta

from test_experiments import setup, start, expose, tick, record


def promoted(world, store, api, governance, engine):
    eid = start(world, store, api, governance, engine)
    first = expose(world, store, api, engine)
    tick(world, api, engine, first+timedelta(hours=72))
    governance.tick(world.now)
    world.approvals[-1]["status"] = "approved"
    governance.tick(world.now)
    tick(world, api, engine)
    begin = expose(world, store, api, engine, version=3, prefix="promoted", promoted=True)
    data = record(store, eid)["data"]
    assert data["promotion_lift"] == data["evaluation"]["primary"]["difference"]
    assert data["promotion_config_version"] == 3 and data["promoted_at"]
    return eid, begin


def population(lift, segment="all"):
    rng = random.Random(889)
    calls = 1 if segment == "first" else 3 if segment == "repeat" else 4
    rows = []
    for voice in ("V1", "V2"):
        for person in range(2000):
            connected = engaged = 0
            for _ in range(calls):
                answered = rng.random()<0.7
                connected += answered
                engaged += answered and rng.random() < (0.35 + (lift if voice == "V2" else 0))
            rows.append({"person_id":f"{voice}-{person}","voice":voice,"dials":calls,"connected":connected,"engaged":engaged})
    return rows


def test_two_low_lift_days_restore_previous_allocation_after_permission(database, monkeypatch):
    with setup(database) as (world, store, api, governance, engine):
        eid, begin = promoted(world, store, api, governance, engine)
        samples = {kind:population(.12,kind) for kind in ("all","first","repeat")}
        monkeypatch.setattr(store,"collect_exposure",lambda *args,exposure="all":samples[exposure])
        tick(world, api, engine, begin+timedelta(hours=24))
        assert record(store,eid)["status"] == "monitoring"
        tick(world, api, engine, begin+timedelta(hours=48))
        assert record(store,eid)["status"] == "restoring"
        proposal = store.proposal(record(store,eid)["proposal_id"])
        assert proposal["urgent"] and proposal["body"]["proposed_config"]["allocations"]["default"]["voice"] == {"V1":1}
        assert "two consecutive days" in proposal["body"]["rationale"]
        assert world.config["allocations"]["default"]["voice"]["V2"] == .9


def test_repeat_exposure_decay_is_visible_even_when_overall_lift_holds(database, monkeypatch):
    with setup(database) as (world, store, api, governance, engine):
        eid, begin = promoted(world, store, api, governance, engine)
        samples = {"all":population(.24),"first":population(.5,"first"),"repeat":population(.1,"repeat")}
        monkeypatch.setattr(store,"collect_exposure",lambda *args,exposure="all":samples[exposure])
        tick(world, api, engine, begin+timedelta(hours=24))
        tick(world, api, engine, begin+timedelta(hours=48))
        data = record(store,eid)["data"]
        assert record(store,eid)["status"] == "restoring"
        assert data["decay_streaks"]["all"] == 0 and data["decay_streaks"]["repeat"] == 2
        assert "repeat:" in data["restore_reason"]


def test_zero_compatible_two_day_window_retires_without_claiming_harm(database, monkeypatch):
    with setup(database) as (world, store, api, governance, engine):
        eid, begin = promoted(world, store, api, governance, engine)
        strong, zero = population(.3), population(0)
        monkeypatch.setattr(store,"collect_exposure",lambda exp,phase,*args,exposure="all":zero if phase.startswith("decay48") else strong)
        tick(world, api, engine, begin+timedelta(hours=48))
        data = record(store,eid)["data"]
        assert record(store,eid)["status"] == "restoring"
        assert "insufficient evidence" in data["restore_reason"]
        assert data["decay_streaks"]["all"] == 0


def test_old_predeclared_promotion_share_is_preserved_on_restart(database):
    with setup(database) as (world, store, api, governance, engine):
        eid = start(world, store, api, governance, engine)
        first = expose(world, store, api, engine)
        experiment = record(store,eid)
        plan = {**experiment["data"]["plan"],"winner_share":.8,"rule_version":"clustered-fixed-v1"}
        store.update_experiment(eid,"running",world.now,{**experiment["data"],"plan":plan})
        tick(world, api, engine, first+timedelta(hours=72))
        assert store.proposal(record(store,eid)["proposal_id"])["body"]["proposed_config"]["allocations"]["default"]["voice"]["V2"] == .8
