from copy import deepcopy
from pathlib import Path
import pytest
from uftr.config import load_config, time_grid, validate_config

ROOT = Path(__file__).resolve().parents[1]


def test_default_has_97_endpoints_and_96_intervals():
    config = load_config(ROOT / "configs/phase00.yaml")
    grid = time_grid(config)
    assert len(grid) == 97
    assert grid[0] == 0 and grid[-1] == 86400
    assert all(b - a == 900 for a, b in zip(grid, grid[1:]))


@pytest.mark.parametrize("section,key,value", [
    ("simulation", "interval_minutes", 17),
    ("simulation", "duration_hours", 0),
    ("models", "closure_depth_m", -0.3),
    ("models", "bpr_alpha", float("nan")),
    ("units", "time", "minutes"),
    ("crs", "projected", "EPSG:4326"),
])
def test_invalid_physical_configuration_is_rejected(section, key, value):
    config = load_config(ROOT / "configs/phase00.yaml")
    config[section][key] = value
    with pytest.raises(ValueError):
        validate_config(config)


def test_weights_and_seed_are_validated():
    config = load_config(ROOT / "configs/phase00.yaml")
    changed = deepcopy(config)
    changed["models"]["resilience_weights"]["performance"] = .9
    with pytest.raises(ValueError):
        validate_config(changed)
    config["seed"] = True
    with pytest.raises(ValueError):
        validate_config(config)
