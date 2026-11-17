"""Validated configuration shared by future phase entry points."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import math
import yaml


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


def validate_config(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("configuration must be a mapping")
    result = deepcopy(data)
    for key in ("project", "phase", "region", "scenario", "strategy"):
        if not isinstance(result.get(key), str) or not result[key].strip():
            raise ValueError(f"{key} must be a nonempty string")
    if result["phase"] not in {f"{n:02d}" for n in range(14)}:
        raise ValueError("phase must be a string between 00 and 13")
    seed = result.get("seed")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be an integer in [0, 2**32)")
    if type(result.get("workers")) is not int or result["workers"] < 1:
        raise ValueError("workers must be a positive integer")
    for section in ("outputs", "simulation", "units", "crs", "models"):
        if not isinstance(result.get(section), dict):
            raise ValueError(f"{section} must be a mapping")
    output = result["outputs"]
    if not isinstance(output.get("root"), str) or not output["root"]:
        raise ValueError("outputs.root must be a path string")
    _positive(output.get("dpi"), "outputs.dpi")
    if output.get("retention") != "key-figures-and-screenshots":
        raise ValueError("unsupported retention policy")
    sim = result["simulation"]
    _positive(sim.get("duration_hours"), "duration_hours")
    _positive(sim.get("interval_minutes"), "interval_minutes")
    steps = sim["duration_hours"] * 60 / sim["interval_minutes"]
    if not math.isclose(steps, round(steps), abs_tol=1e-9):
        raise ValueError("simulation window must contain whole intervals")
    expected = {"distance": "m", "time": "s", "flow": "veh/h", "capacity": "veh/h", "flood_depth": "m"}
    if result["units"] != expected:
        raise ValueError(f"units must be {expected}")
    if result["crs"] != {"source": "EPSG:4326", "projected": "EPSG:32650"}:
        raise ValueError("initial Shenzhen CRS convention is EPSG:4326 / EPSG:32650")
    model = result["models"]
    for key in ("closure_depth_m", "bpr_alpha", "bpr_beta", "relative_gap_target"):
        _positive(model.get(key), key)
    weights = model.get("resilience_weights", {})
    if set(weights) != {"structure", "performance", "functionality"}:
        raise ValueError("three resilience weights are required")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in weights.values()):
        raise ValueError("weights must be finite and nonnegative")
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise ValueError("resilience weights must sum to 1")
    return result


def load_config(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as stream:
        return validate_config(yaml.safe_load(stream))


def time_grid(config: dict) -> list[float]:
    """Return seconds at endpoints; demand belongs to the intervening intervals."""
    sim = config["simulation"]
    count = round(sim["duration_hours"] * 60 / sim["interval_minutes"])
    return [i * sim["interval_minutes"] * 60 for i in range(count + 1)]
