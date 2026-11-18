"""Numerical/network tests for desktop SUMO preparation, no mobile UI tests."""
import numpy as np
import pandas as pd
from uftr.sumo_dynamic import (contiguous_visits, prefer_route, accounting,
                              window_start, tau_proxy, route_stage_paths)


def test_boundary_visits_keep_through_traffic_and_reentry():
    assert contiguous_visits([0, 1, 2, 3, 4], [False, True, True, False, True]) == [[1, 2], [4]]
    assert contiguous_visits([0, 3], [False]*4) == []


def test_route_change_threshold_and_closed_route_replacement():
    weights = {'a': 100., 'b': 80., 'c': 20.}
    assert not prefer_route(['a'], ['b'], weights, set(), 60, .1)
    assert prefer_route(['a'], ['c'], weights, set(), 60, .1)
    assert prefer_route(['a'], ['b'], weights, {'a'}, 60, .1)
    assert not prefer_route(['a'], ['b'], weights, {'a', 'b'}, 60, .1)


def test_all_vehicle_outcomes_are_disjoint():
    result = accounting(100, 3, 7, 90, 10, 30, 50)
    assert result['balance_error'] == result['injected_balance_error'] == 0
    assert accounting(100, 3, 7, 90, 10, 29, 50)['balance_error'] == 1


def test_exposure_window_clamps_and_ignores_unknown_depths():
    depth = np.zeros((20, 3)); depth[:, 2] = np.nan; depth[19, :2] = .4
    start, peak, count = window_start(depth, 3600, .3)
    assert start == 15 and peak == 19 and count[19] == 2


def test_tau_proxy_increases_headway_and_respects_step_floor():
    assert tau_proxy(1600, 50/3.6, .5) == 2*tau_proxy(1600, 50/3.6, 1)
    assert tau_proxy(10000, 10, 1) >= 1


def test_full_od_boundary_extraction_uses_direction_and_keeps_external_pairs():
    corridors = pd.DataFrame({'u': [0, 1, 2], 'v': [1, 2, 3], 'normal_time_s': [1., 1., 1.]})
    matrices = np.array([[0., 10.], [20., 0.]])
    rows, report = route_stage_paths(corridors, [np.array([0]), np.array([1]), np.array([2])],
                                     np.array([False, True, False]), [0, 3], [matrices]*3)
    assert len(rows) == 1 and rows[0]['source_arc_positions'] == [1]
    assert rows[0]['rates_veh_h'] == [10., 10., 10.]
    assert report['disconnected_offpeak_veh_h'] == 20
