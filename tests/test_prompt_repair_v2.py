import copy

import httpx
import pytest

from test_incidents import setup, seed_alarm, tick


def test_llm_is_only_bought_after_previous_candidate_fails_and_filters_options(database):
    with setup(database) as (world, store, api, governance, engine):
        world.validation_rates.update(P1=.8, P3=.8, P4=1.)
        original = api.mutate
        def mutate(method, path, body):
            response = original(method,path,body)
            if path == "/llm/suggest-fixes":
                data = response.json()
                data["suggestions"] += [{"prompt_version":"P2"},{"prompt_version":"unavailable"}]
                return httpx.Response(200,json=data,request=response.request)
            return response
        api.mutate = mutate
        seed_alarm(store,"prompt_version")
        tick(world,api,engine,10)
        tick(world,api,engine,11)
        assert world.paid == []
        tick(world,api,engine,11,15)
        assert world.paid[0] == ("/validation/runs",{"workflow_id":"wf","prompt_version":"P1","n":500})
        tick(world,api,engine,11,30)
        assert store.open_incidents()[0]["data"]["candidates"] == ["P1","P3","P4"]
        tick(world,api,engine,11,45)
        tick(world,api,engine,12)
        assert store.open_incidents()[0]["data"]["candidate"] == "P4"
        assert len(world.paid)==4 and world.credits==182


def test_supervisor_attribution_and_prompt_approval_are_explicit(database):
    with setup(database) as (world, store, api, governance, engine):
        previous = copy.deepcopy(world.config)
        previous["prompt_version"] = "P1"
        store.save_workflow(world.workflow,{"version":1,"config":previous},[])
        world.version = 2
        store.save_workflow(world.workflow,{"version":2,"config":world.config},[])
        store.ingest({"chunk":0,"kind":"events","events":1},[{"event_id":1,"type":"config_changed",
                     "ts":world.now,"workflow_id":"wf","version":2,"actor":"supervisor","changed_dims":["prompt_version"]}])
        world.workflow["governance"]["auto_apply"]["allowed_dims"].append("prompt_version")
        seed_alarm(store,"prompt_version")
        for hour,minute in ((10,0),(11,0),(11,15),(11,30)):
            tick(world,api,engine,hour,minute)
        incident=store.open_incidents()[0]
        proposal=store.proposal(incident["proposal_id"])
        assert proposal["route"]=="approval"
        assert "supervisor" in proposal["body"]["change_summary"]
        assert proposal["body"]["evidence"]["attribution"]["previous"]["prompt"]=="P1"
        assert incident["data"]["supervisor_alert"]["severity"]=="page"
        assert len(world.paid)==1


@pytest.mark.parametrize("status",["rejected","expired"])
def test_denied_prompt_proposal_moves_to_a_new_candidate(database,status):
    with setup(database) as (world, store, api, governance, engine):
        seed_alarm(store,"prompt_version")
        for hour,minute in ((10,0),(11,0),(11,15),(11,30)):
            tick(world,api,engine,hour,minute)
        governance.tick(world.now)
        world.approvals[-1]["status"]=status
        governance.tick(world.now)
        tick(world,api,engine,11,45)
        incident=store.open_incidents()[0]
        assert incident["data"]["candidate_index"]==1
        assert incident["data"]["proposal_attempt"]==1
        assert "validation" not in incident["data"]
        tick(world,api,engine,12)
        assert len([p for p in world.paid if p[0]=="/llm/suggest-fixes"])==1
        assert world.config["prompt_version"]=="P2"
