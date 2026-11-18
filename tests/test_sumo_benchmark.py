"""Whole-trip sampling and direction/connectivity checks for the district baseline."""
import numpy as np
import pandas as pd
from uftr.sumo_benchmark import sample_full_od, sampled_source_routes


def test_full_od_sampling_retains_intrazonal_draws_and_is_reproducible():
    matrix = np.array([[10000., 5000.], [0., 10000.]])
    settings = {'departure_seconds': 1800, 'demand_fraction': .05}
    plan, expected = sample_full_od([matrix]*3, 10*3600, settings, 42)
    assert expected == 625
    assert plan == sample_full_od([matrix]*3, 10*3600, settings, 42)[0]
    assert any(r['origin_zone'] == r['destination_zone'] for r in plan)
    assert all(0 <= r['depart_s'] < 1800 for r in plan)
    assert len({r['vehicle_id'] for r in plan}) == len(plan)
    assert [r['depart_s'] for r in plan] == sorted(r['depart_s'] for r in plan)


def test_sampled_whole_routes_keep_all_arcs_and_explain_invalid_pairs():
    corridors = pd.DataFrame({'u': [0, 1, 2], 'v': [1, 2, 3], 'normal_time_s': [1., 1., 1.]})
    routes = sampled_source_routes(corridors, [np.array([5, 6]), np.array([7]), np.array([8])],
                                   [0, 3, -1], {(0, 1), (1, 0), (0, 0), (0, 2)})
    assert routes[0, 1] == ([5, 6, 7, 8], 'source_reachable')
    assert routes[1, 0] == ([], 'source_disconnected')
    assert routes[0, 0] == ([], 'intrazonal_not_loaded')
    assert routes[0, 2] == ([], 'missing_connector')


def test_parallel_corridors_use_lower_time_without_summing_weights():
    corridors = pd.DataFrame({'u': [0, 0, 1], 'v': [1, 1, 2], 'normal_time_s': [9., 1., 1.]})
    routes = sampled_source_routes(corridors, [np.array([0]), np.array([1]), np.array([2])],
                                   [0, 2], {(0, 1)})
    assert routes[0, 1][0] == [1, 2]
