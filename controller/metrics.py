"""Population alarm rules; these are not experiment winner tests."""

import copy
import math

from .policy import distribution


Z = 3.29  # Nominal 99.9% Wilson intervals, not a whole-run false-alarm guarantee.
MIN_DIALS = 60
MIN_CONNECTED = 30
MIN_HISTORY = 200


def wilson(successes: int, trials: int, z: float = Z) -> tuple[float, float]:
    if not 0 <= successes <= trials:
        raise ValueError("Invalid binomial counts")
    if trials == 0:
        return 0.0, 1.0
    rate = successes / trials
    scale = 1 + z * z / trials
    center = (rate + z * z / (2 * trials)) / scale
    spread = z * math.sqrt(rate * (1 - rate) / trials + z * z / (4 * trials * trials)) / scale
    return max(0.0, center - spread), min(1.0, center + spread)


def counts(rows: list[dict]) -> dict:
    return {key: sum(row[key] for row in rows) for key in ("dials", "connected", "engaged", "hallucinations")}


def fisher_upper(successes: int, trials: int, reference_successes: int, reference_trials: int) -> float:
    """One-sided exact conditional test: is the current success rate elevated?"""
    if not 0 <= successes <= trials or not 0 <= reference_successes <= reference_trials:
        raise ValueError("Invalid binomial counts")
    if not trials or not reference_trials:
        return 1.0
    total = trials + reference_trials
    positive = successes + reference_successes
    negative = total - positive
    def log_choose(n, k):
        return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    denominator = log_choose(total, trials)
    lower = max(successes, trials - negative)
    return min(1.0, math.fsum(
        math.exp(log_choose(positive, k) + log_choose(negative, trials - k) - denominator)
        for k in range(lower, min(trials, positive) + 1)
    ))


def alarms(current: list[dict], historical: list[dict], config: dict) -> list[dict]:
    """Compare caller IDs within cohort/hour; QA alarms compare a prompt with normal history."""
    results = []
    for row in current:
        name, dim, variant = row["cohort_id"], row["dimension"], row["variant"]
        if dim not in {"caller_id", "prompt_version"}:
            continue
        baseline = [old for old in historical if old["cohort_id"] == name and old["dimension"] == dim
                    and (dim == "prompt_version" or old["variant"] == variant)]
        normal = counts(baseline)
        signal = False
        extra = {}
        if dim == "caller_id":
            if variant not in distribution(config, name, dim):
                continue
            peers = [peer for peer in current if peer["cohort_id"] == name and peer["dimension"] == dim
                     and peer["variant"] != variant and peer["dials"] >= MIN_DIALS
                     and peer["variant"] in distribution(config, name, dim)]
            healthy = []
            for peer in peers:
                past = counts([old for old in historical if old["cohort_id"] == name
                               and old["dimension"] == dim and old["variant"] == peer["variant"]])
                if past["dials"] >= MIN_HISTORY:
                    declining = (past["connected"] / past["dials"] - peer["connected"] / peer["dials"] >= 0.03
                                 and fisher_upper(past["connected"], past["dials"], peer["connected"], peer["dials"]) <= 0.01)
                    if not declining:
                        healthy.append(peer)
            if row["dials"] >= MIN_DIALS and normal["dials"] >= MIN_HISTORY and healthy:
                peer = sorted(healthy, key=lambda item: (-item["connected"] / item["dials"], item["variant"]))[0]
                own_p = fisher_upper(normal["connected"], normal["dials"], row["connected"], row["dials"])
                peer_p = fisher_upper(peer["connected"], peer["dials"], row["connected"], row["dials"])
                rate = row["connected"] / row["dials"]
                signal = (normal["connected"] / normal["dials"] - rate >= 0.03
                          and peer["connected"] / peer["dials"] - rate >= 0.02 and max(own_p, peer_p) <= 0.01)
                extra = {"replacement": peer["variant"], "peer": peer, "history_fisher_p": own_p,
                         "peer_fisher_p": peer_p, "alpha": 0.01}
        elif variant == config["prompt_version"]:
            if row["connected"] >= MIN_CONNECTED and normal["connected"] >= MIN_HISTORY:
                probability = fisher_upper(row["hallucinations"], row["connected"], normal["hallucinations"], normal["connected"])
                excess = row["hallucinations"] / row["connected"] - normal["hallucinations"] / normal["connected"]
                signal = row["hallucinations"] >= 3 and excess >= 0.02 and probability <= 0.01
                extra = {"fisher_p": probability, "observed_excess": excess, "alpha": 0.01, "minimum_excess": 0.02}
        else:
            continue
        results.append({"kind": dim, "subject": f"{name}:{variant}", "cohort": name,
                        "variant": variant, "signal": signal, "current": row, "baseline": normal, **extra})
    return results


def rotate_caller(config: dict, alarm: dict) -> dict:
    proposed = copy.deepcopy(config)
    name, bad, replacement = alarm["cohort"], alarm["variant"], alarm["replacement"]
    if name == "default":
        # Preserve inherited allocations on populations without their own alarm evidence.
        for cohort in config["cohorts"]:
            cid = cohort["id"]
            proposed["allocations"].setdefault(cid, {}).setdefault(
                "caller_id", distribution(config, cid, "caller_id"),
            )
    weights = distribution(config, name, "caller_id")
    shifted = weights.pop(bad, 0)
    weights[replacement] = weights.get(replacement, 0) + shifted
    proposed["allocations"].setdefault(name, {})["caller_id"] = weights
    return proposed


def adjusted_population_harm(before: dict, after: dict, historical_before: dict,
                             historical_after: dict, objective: dict) -> dict:
    """Operational guardrails with conservative uncertainty around clock-hour adjustment."""
    metrics = {"pickup_rate": ("connected", "dials"), "engagement_rate": ("engaged", "connected")}
    checks = {}
    for metric, (numerator, denominator) in metrics.items():
        margin = objective["guardrail"].get(f"{metric}_max_drop", 0.05 if metric == objective["primary"] else None)
        if margin is None:
            continue
        populations = (before, after, historical_before, historical_after)
        supported = all(row[denominator] >= 30 for row in populations)
        check = {"supported": supported, "material_harm": False, "margin": margin}
        if supported:
            pre_low = wilson(before[numerator], before[denominator])[0]
            post_upper = wilson(after[numerator], after[denominator])[1]
            history_pre_upper = wilson(historical_before[numerator], historical_before[denominator])[1]
            history_post_low = wilson(historical_after[numerator], historical_after[denominator])[0]
            expected_low = min(1.0, pre_low * history_post_low / history_pre_upper) if history_pre_upper else 0.0
            check.update(expected_lower=expected_low, observed_upper=post_upper,
                         material_harm=post_upper + margin < expected_low)
        checks[metric] = check
    return {"material_harm": any(value["material_harm"] for value in checks.values()), "checks": checks,
            "method": "live pre/post with conservative historical clock-hour ratio adjustment"}
