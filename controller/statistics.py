"""Fixed-look inference for pickup/engagement ratios with person-clustered errors."""

import math
from collections import defaultdict
from statistics import NormalDist


METRICS = {"pickup_rate": ("connected", "dials"), "engagement_rate": ("engaged", "connected")}


def comparison(rows: list[dict], control: str, challenger: str, metric: str, alpha: float) -> dict:
    numerator, denominator = METRICS[metric]
    totals = {arm: {"numerator": 0, "denominator": 0, "people": set()} for arm in (control, challenger)}
    for row in rows:
        if row["voice"] not in totals:
            raise ValueError("Unexpected experiment arm")
        arm = totals[row["voice"]]
        if not 0 <= row["engaged"] <= row["connected"] <= row["dials"]:
            raise ValueError("Invalid exposure counts")
        arm["numerator"] += row[numerator]
        arm["denominator"] += row[denominator]
        if row[denominator]:
            arm["people"].add(row["person_id"])
    summary = {key: {"successes": value["numerator"], "observations": value["denominator"],
                     "people": len(value["people"]),
                     "rate": value["numerator"] / value["denominator"] if value["denominator"] else None}
               for key, value in totals.items()}
    result = {"metric": metric, "alpha": alpha, "arms": summary, "difference": None, "lower": None, "upper": None}
    if any(not value["denominator"] for value in totals.values()):
        return result
    rates = {arm: summary[arm]["rate"] for arm in totals}
    difference = rates[challenger] - rates[control]
    result["difference"] = difference
    # Boundary rates do not justify a zero-width normal interval.
    if any(rate in (0, 1) for rate in rates.values()):
        return result
    scores = defaultdict(float)
    for row in rows:
        arm = row["voice"]
        sign = 1 if arm == challenger else -1
        scores[row["person_id"]] += sign * (row[numerator] - rates[arm] * row[denominator]) / totals[arm]["denominator"]
    clusters = len(scores)
    if clusters < 2:
        return result
    variance = clusters / (clusters - 1) * math.fsum(score * score for score in scores.values())
    if variance <= 0:
        return result
    error = math.sqrt(variance)
    critical = NormalDist().inv_cdf(1 - alpha)
    result.update(standard_error=error, clusters=clusters,
                  lower=max(-1.0, difference - critical * error),
                  upper=min(1.0, difference + critical * error))
    return result


def evaluate(rows: list[dict], plan: dict, *, alpha: float | None = None,
             minimum: int | None = None, people: int = 100) -> dict:
    alpha = plan["alpha"] if alpha is None else alpha
    minimum = plan["min_primary"] if minimum is None else minimum
    primary = plan["objective"]["primary"]
    guardrail = "pickup_rate" if primary == "engagement_rate" else "engagement_rate"
    margin = plan["objective"]["guardrail"][f"{guardrail}_max_drop"]
    contrasts = {metric: comparison(rows, plan["control"], plan["challenger"], metric, alpha)
                 for metric in (primary, guardrail)}
    enough = all(item["lower"] is not None and all(arm["people"] >= people and
                 arm["observations"] >= (minimum if metric == primary else 50)
                 for arm in item["arms"].values()) for metric, item in contrasts.items())
    status = "inconclusive"
    if enough:
        main, guard = contrasts[primary], contrasts[guardrail]
        if main["lower"] > 0 and main["difference"] >= plan["minimum_lift"] and guard["lower"] > -margin:
            status = "winner"
        elif main["upper"] < 0 or guard["upper"] < -margin:
            status = "lost"
    return {"decision": status, "enough_evidence": enough, "primary": contrasts[primary],
            "guardrail": contrasts[guardrail], "guardrail_margin": margin,
            "method": "person-clustered delta-method normal intervals"}


def planned_samples(rate: float, alpha: float, share: float = 0.2, lift: float = 0.08) -> int:
    """Challenger target for primary positivity; independent-binomial approximation.

    Total N = z²*p*(1-p)/(lift²*share*(1-share)); multiplying by share
    gives this target, not total N. This is not power for the joint winner rule;
    final clustered inference, effect-size/guardrail gates and the fixed horizon govern.
    """
    z = NormalDist().inv_cdf(1 - alpha) + NormalDist().inv_cdf(0.8)
    return max(200, math.ceil(z * z * rate * (1 - rate) / (lift * lift * (1 - share))))
