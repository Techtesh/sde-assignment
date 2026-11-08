import copy
import math
import random

import pytest

from controller.statistics import comparison, evaluate, planned_samples
from statistics import NormalDist


def plan():
    return {"control": "C", "challenger": "T", "alpha": 0.025, "min_primary": 200,
            "minimum_lift": 0.08, "objective": {"primary": "engagement_rate", "guardrail": {"pickup_rate_max_drop": 0.02}}}


def people(seed=1, count=3000, lift=0.2):
    rng = random.Random(seed)
    rows = []
    for arm, count in (("C", count * 4), ("T", count)):
        for i in range(count):
            connected = sum(rng.random() < 0.5 for _ in range(4))
            engaged = sum(rng.random() < (0.5 + (lift if arm == "T" else 0)) for _ in range(connected))
            rows.append({"person_id": f"{arm}-{i}", "voice": arm, "dials": 4, "connected": connected, "engaged": engaged})
    return rows


def test_known_lift_requires_primary_improvement_and_guardrail_noninferiority():
    result = evaluate(people(), plan())
    assert result["decision"] == "winner"
    assert result["primary"]["lower"] > 0
    assert result["guardrail"]["lower"] > -0.02


def test_more_calls_from_same_people_do_not_invent_independent_samples():
    data = people(count=300)
    initial = comparison(data, "C", "T", "engagement_rate", 0.025)
    repeated = copy.deepcopy(data)
    for row in repeated:
        for key in ("dials", "connected", "engaged"):
            row[key] *= 100
    result = comparison(repeated, "C", "T", "engagement_rate", 0.025)
    assert result["standard_error"] == pytest.approx(initial["standard_error"])
    assert result["lower"] == pytest.approx(initial["lower"])


def test_same_person_in_both_arms_preserves_covariance():
    data = people(count=300)
    disjoint = comparison(data, "C", "T", "engagement_rate", 0.025)
    for row in data:
        row["person_id"] = row["person_id"].split("-")[1]
    overlapping = comparison(data, "C", "T", "engagement_rate", 0.025)
    assert overlapping["clusters"] < disjoint["clusters"]
    assert overlapping["standard_error"] != disjoint["standard_error"]


def test_guardrail_harm_prevents_promoting_a_primary_winner():
    data = people()
    for row in data:
        if row["voice"] == "T":
            row["dials"] *= 2
    result = evaluate(data, plan())
    assert result["primary"]["lower"] > 0
    assert result["decision"] == "lost"


def test_sparse_and_boundary_populations_are_inconclusive():
    assert evaluate([], plan())["decision"] == "inconclusive"
    data = people(count=10)
    assert evaluate(data, plan())["decision"] == "inconclusive"
    for row in data:
        row["connected"] = row["engaged"] = 0
    assert evaluate(data, plan())["decision"] == "inconclusive"


def test_power_target_and_testing_budget_are_declared():
    assert planned_samples(0.5, 0.025) >= 200
    assert planned_samples(0.5, 0.005) > planned_samples(0.5, 0.025)
    assert sum(0.05 / (i * (i + 1)) for i in range(1, 10000)) < 0.05


@pytest.mark.parametrize("share", [0.1, 0.2, 0.5])
def test_planned_samples_is_an_arm_target_with_approximately_eighty_percent_power(share):
    challenger = planned_samples(0.5, 0.025, share=share)
    control = challenger * (1 - share) / share
    error = math.sqrt(0.25 * (1 / challenger + 1 / control))
    power = NormalDist().cdf(0.08 / error - NormalDist().inv_cdf(0.975))
    assert 0.8 <= power < 0.805


def test_seeded_correlated_null_calibration():
    rng = random.Random(829)
    positives = 0
    winners = 0
    replicates = 500
    for _ in range(replicates):
        data = []
        for arm in ("C", "T"):
            for person in range(600):
                # Four perfectly correlated calls per arm/person: a naive call test is overconfident.
                connected = 4 * (rng.random() < 0.7)
                engaged = connected * (rng.random() < 0.5)
                data.append({"person_id": f"{arm}-{person}", "voice": arm,
                             "dials": 4, "connected": connected, "engaged": engaged})
        result = comparison(data, "C", "T", "engagement_rate", 0.025)
        positives += result["lower"] is not None and result["lower"] > 0
        winner = evaluate(data, plan())["decision"] == "winner"
        winners += winner
        assert not winner or result["lower"] > 0
    # Allow binomial sampling uncertainty; do not require exactly <= alpha in finite simulations.
    tolerance = 0.025 + 3 * math.sqrt(0.025 * 0.975 / replicates)
    assert positives / replicates <= tolerance
    print({"replicates": replicates, "clustered_null_primary_positives": positives,
           "full_procedure_false_winners": winners, "nominal_alpha": 0.025})
