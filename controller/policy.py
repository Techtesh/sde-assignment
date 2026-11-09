"""Shared cohort matching and deterministic configuration/governance rules."""

import copy
import math


ALLOCATION_DIMS = ("welcome_message", "voice", "caller_id")
FEATURES = {"lang", "city_tier", "age_band", "value_band"}


def cohort_id(config: dict, features: dict) -> str:
    for cohort in config["cohorts"]:
        if all(features.get(key) in values for key, values in cohort["where"].items()):
            return cohort["id"]
    return "default"


def distribution(config: dict, cohort: str, dimension: str) -> dict:
    allocations = config["allocations"]
    weights = allocations.get(cohort, {}).get(dimension, allocations["default"][dimension])
    total = sum(weights.values())
    return {option: weight / total for option, weight in weights.items() if weight > 0}


def finite_weight(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def validate_config(workflow: dict, config: dict) -> None:
    if not isinstance(config, dict) or set(config) != {"cohorts", "allocations", "prompt_version", "schedule"}:
        raise ValueError("Only cohorts, allocations, prompt_version and schedule are configurable")
    cohorts = config["cohorts"]
    if not isinstance(cohorts, list) or len(cohorts) > 20:
        raise ValueError("At most 20 cohorts are permitted")
    ids = {"default"}
    for cohort in cohorts:
        if not isinstance(cohort, dict) or set(cohort) != {"id", "where"}:
            raise ValueError("Cohort requires id and where")
        name, where = cohort["id"], cohort["where"]
        if not isinstance(name, str) or not name or name in ids:
            raise ValueError("Cohort IDs must be unique and cannot be default")
        if not isinstance(where, dict) or not set(where) <= FEATURES:
            raise ValueError("Cohort filters must use lead features")
        if any(not isinstance(values, list) or not values or
               any(not isinstance(value, str) for value in values) for values in where.values()):
            raise ValueError("Cohort feature values must be nonempty string lists")
        ids.add(name)
    allocations = config["allocations"]
    if not isinstance(allocations, dict) or "default" not in allocations or not set(allocations) <= ids:
        raise ValueError("Allocations require default and known cohort IDs")
    for name, dimensions in allocations.items():
        if not isinstance(dimensions, dict) or not set(dimensions) <= set(ALLOCATION_DIMS):
            raise ValueError("Unknown allocation dimension")
        if name == "default" and set(dimensions) != set(ALLOCATION_DIMS):
            raise ValueError("Default allocations require all three dimensions")
        for dim, weights in dimensions.items():
            if not isinstance(weights, dict) or not weights or not set(weights) <= set(workflow["options"][dim]):
                raise ValueError("Allocation uses an unavailable option")
            if any(not finite_weight(weight) for weight in weights.values()) or not finite_weight(sum(weights.values())) or sum(weights.values()) <= 0:
                raise ValueError("Allocation weights must be finite, nonnegative, and sum above zero")
    if config["prompt_version"] not in workflow["options"]["prompt_version"]:
        raise ValueError("Unavailable prompt version")
    schedule = config["schedule"]
    if not isinstance(schedule, dict) or set(schedule) != {"hour_weights", "lead_preferred_hour"}:
        raise ValueError("Schedule requires hour_weights and lead_preferred_hour")
    hours, preferred = schedule["hour_weights"], schedule["lead_preferred_hour"]
    start, end = workflow["dialling_window"]
    if not isinstance(hours, dict) or not set(hours) <= ids:
        raise ValueError("Hour weights require known cohort IDs")
    for table in hours.values():
        if not isinstance(table, dict) or any(
            not isinstance(hour, str) or not hour.isdigit() or not start <= int(hour) < end
            or not finite_weight(weight) for hour, weight in table.items()
        ):
            raise ValueError("Hour weights must be finite and within the business window")
    if not isinstance(preferred, dict) or len(preferred) > 200_000 or any(
        not isinstance(person, str) or type(hour) is not int or not start <= hour < end
        for person, hour in preferred.items()
    ):
        raise ValueError("Invalid preferred-hour entries")


def config_diff(old: dict, new: dict) -> list[dict]:
    """Treat each allocation distribution as atomic when preserving supervisor edits."""
    changes = []
    for key in ("cohorts", "prompt_version", "schedule"):
        if old[key] != new[key]:
            changes.append({"path": [key], "before": old[key], "after": new[key]})
    for name in sorted(set(old["allocations"]) | set(new["allocations"])):
        for dim in ALLOCATION_DIMS:
            before = old["allocations"].get(name, {}).get(dim)
            after = new["allocations"].get(name, {}).get(dim)
            if before != after:
                changes.append({"path": ["allocations", name, dim], "before": before, "after": after})
    return changes


def changed_dimensions(old: dict, new: dict) -> set[str]:
    return {change["path"][-1] for change in config_diff(old, new)}


def decide_route(workflow: dict, old: dict, new: dict) -> str:
    validate_config(workflow, new)
    changed = changed_dimensions(old, new)
    if not changed:
        raise ValueError("Proposal does not change the configuration")
    policy = workflow["governance"]["auto_apply"]
    if old["prompt_version"] != new["prompt_version"]:
        return "approval"
    if not policy["enabled"] or not changed <= set(policy["allowed_dims"]):
        return "approval"
    names = {"default"} | {c["id"] for c in old["cohorts"] + new["cohorts"]}
    for name in sorted(names):
        for dim in ALLOCATION_DIMS:
            before, after = distribution(old, name, dim), distribution(new, name, dim)
            shift = sum(abs(before.get(key, 0) - after.get(key, 0)) for key in before.keys() | after.keys()) / 2
            if shift > policy["max_shift"] + 1e-12:
                return "approval"
    return "auto"


def rebase_config(base: dict, desired: dict, current: dict) -> dict:
    """Carry only non-conflicting intended changes onto the current configuration."""
    merged = copy.deepcopy(current)
    for change in config_diff(base, desired):
        path = change["path"]
        target = merged
        if len(path) == 3:
            target = merged["allocations"].setdefault(path[1], {})
        key = path[-1]
        actual = target.get(key)
        if actual == change["after"]:
            continue
        if actual != change["before"]:
            raise ValueError(f"Supervisor conflict at {'.'.join(path)}; fresh decision required")
        if change["after"] is None:
            target.pop(key, None)
        else:
            target[key] = copy.deepcopy(change["after"])
    merged["allocations"] = {key: value for key, value in merged["allocations"].items() if value}
    return merged
