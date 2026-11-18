import numpy as np
import networkx as nx
import pytest
from uftr.adaptive import surface_route, road_factors, sample_od, point_queue, nsga2, fronts, feasible_masks
from uftr.adaptive_network import pack_paths, contract, corridor_states, route_library


def test_spatial_loss_and_water_conservation():
    grid = {'receiver': np.array([1, -1]), 'tau_s': np.array([300., 300.]),
            'spill_depth_m': np.array([0., 0.]), 'rain_grid_id': np.array([0, 0])}
    s = {'internal_seconds': 180, 'output_seconds': 900, 'cell_size_m': 150}
    r = surface_route(grid, np.array([[10.]]), np.array([0., 20.]), 1., [0, 1], s)
    assert abs(r['ledger'][-1, -1]) < 1e-7
    assert r['ledger'][-1, 2] > 0
    assert r['sample_depth_m'][-1, 0] > 0
    assert r['sample_depth_m'].shape == (5, 2)
    with pytest.raises(ValueError): surface_route(grid, np.array([[1.]]), [-1., 0.], 1., [0], s)


def test_road_closure_unknown_and_class_capacity():
    speed, capacity, known = road_factors([0, .1, .3, np.nan], np.array([60]*4), np.array([.8]*4))
    assert speed[0] == 60 and speed[2] == capacity[2] == 0
    assert 0 < speed[1] < 60 and 0 < capacity[1] < 1
    assert not known[3] and speed[3] == 60
    with pytest.raises(ValueError): road_factors([-.1], [60], [.8])


def test_stratification_preserves_each_origin_and_unloaded_demand():
    a = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9.]])
    s = sample_od([a, a*2], [10, 20, -1], 4)
    assert np.allclose(np.bincount(s['origin_zone'], weights=s['rates'][0], minlength=3), [2, 4, 0])
    assert s['rates'][0].sum()+s['unlinked_rates'][0]+s['intrazonal_rates'][0] == a.sum()
    assert np.allclose(s['rates'][1], s['rates'][0]*2)


def queue_run(routes, rates, caps, cf, dt=60):
    packed = pack_paths(routes)
    edges = len(caps); t = np.full((len(cf), edges), 60.)
    settings = {'internal_seconds': 60, 'routing_delay_weight': 1., 'terminal_penalty_seconds': 7200}
    return point_queue(**{k: v for k, v in packed.items() if k not in ['corridor_union', 'direct_pairs']},
                       base_time=np.full(edges, 60.), capacity=np.array(caps), times=t,
                       capacity_factors=np.asarray(cf, float), pair_rates=np.array([rates], float),
                       periods=np.zeros(len(cf)-1, int), access_seconds=np.zeros(len(rates)), settings=settings, dt=dt)


def test_queue_carries_mass_and_recovers_after_closure():
    result = queue_run([[(0, 1)]], [120.], [60., 60.], [[1, 0], [1, 1], [1, 1]])
    assert result['released_trips'] == 60
    assert result['completed_trips'] > 0
    assert result['unfinished_trips'] > 0
    assert result['series'][0, 2] == 0
    assert result['maximum_conservation_error_veh'] < 1e-8
    assert result['transit_ring_remaining_veh'] == pytest.approx(result['transit_counter_veh'])


def test_closed_origin_backlog_and_departure_rerouting():
    a = queue_run([[(0,), (1,)]], [40.], [10000., 10000.], [[0, 1], [0, 1]])
    b = queue_run([[(0,)]], [40.], [10000.], [[0], [1]])
    assert a['completed_trips'] == 10
    assert b['completed_trips'] == 0 and b['origin_backlog_trips'] == 10


def test_shared_link_capacity_not_duplicated_by_paths():
    r = queue_run([[(0,)], [(0,)]], [400., 400.], [60.], [[1], [1]])
    assert r['completed_trips'] <= 15
    assert r['released_trips'] == 200
    assert r['released_trips'] == pytest.approx(r['completed_trips']+r['unfinished_trips'])


def test_free_flow_lag_and_step_refinement():
    a = queue_run([[(0, 1)]], [4.], [1e6, 1e6], [[1, 1], [1, 1]], 60)
    b = queue_run([[(0, 1)]], [4.], [1e6, 1e6], [[1, 1], [1, 1]], 30)
    assert a['completed_trips'] == b['completed_trips'] == 1
    assert a['vehicle_seconds'] == b['vehicle_seconds'] == 120


def test_nsga_elitism_feasibility_and_exact_fronts():
    def evaluate(m): return [10-m.bit_count(), m.bit_count(), float(m & 1)]
    result = nsga2(4, 3, evaluate, population=12, generations=8)
    assert all(m.bit_count() <= 3 for m in result['evaluated_masks'])
    masks = feasible_masks(4, 3)
    assert len(masks) == 15
    exact = {masks[j] for j in fronts([evaluate(m) for m in masks])[0]}
    assert set(result['pareto_masks']) <= exact


def test_corridor_contraction_preserves_directed_parallel_arcs():
    graph = nx.MultiDiGraph()
    for j, (u, v) in enumerate([(0, 1), (1, 2), (2, 1), (1, 0), (2, 3), (2, 3)]):
        graph.add_edge(u, v, edge_id=str(j), source_feature_position=j,
                       length_m=100, speed_kph=30, highway='primary')
    settings = {'capacity_per_direction_veh_h': {'primary': 1000, 'fallback': 500},
                'capacity_loss': {'primary': .8, 'fallback': .9}}
    edges, corridors, chains = contract(graph, [0, 3], settings)
    assert sorted(np.concatenate(chains)) == list(range(6))
    assert len(corridors[(corridors.u == 2) & (corridors.v == 3)]) == 2
    assert sum(corridors.normal_time_s) == pytest.approx(sum(edges.length_m*3.6/edges.speed_kph))


def test_candidate_drainage_intervention_replays_and_reduces_storage():
    grid = {'receiver': np.array([1, -1]), 'tau_s': np.array([900., 900.]),
            'spill_depth_m': np.array([.1, .1]), 'rain_grid_id': np.array([0, 0])}
    settings = {'internal_seconds': 180, 'output_seconds': 900, 'cell_size_m': 150}
    rain = np.array([[20.], [0.]])
    base = surface_route(grid, rain, [2, 2], 1, [0, 1], settings)
    improved = surface_route(grid, rain, [6, 2], 1, [0, 1], settings)
    assert np.all(improved['sample_depth_m'] <= base['sample_depth_m']+1e-10)
    assert improved['final_depth_m'].sum() < base['final_depth_m'].sum()


def test_parallel_route_library_keeps_alternative_after_closure():
    import pandas as pd
    corridors = pd.DataFrame({'u': [0, 0, 1], 'v': [1, 1, 2]})
    states = [(np.array([1., 2., 1.]), np.array([1., 1., 1.])),
              (np.array([1., 2., 1.]), np.array([0., 1., 1.]))]
    library = route_library(corridors, states, [0], [2])
    assert library == [[(0, 2), (1, 2)]]


def test_serial_corridor_closure_and_unknown_state():
    import pandas as pd
    edges = pd.DataFrame({'source_feature_position': [10, 11], 'length_m': [100., 100.],
                          'speed_kph': [30., 30.], 'capacity_veh_h': [1000., 800.], 'capacity_loss': [.8, .8]})
    t, cf = corridor_states(edges, [np.array([0, 1])], [0],
                            np.array([[np.nan, 0.], [0., .3]]), {10: 0, 11: 1}, {'closure_depth_m': .3})
    assert t[0, 0] == 24 and cf[0, 0] == 1 and cf[1, 0] == 0


def test_capacity_bound_has_analytical_discharge_and_backlog():
    result = queue_run([[(0,)]], [120.], [60.], [[1], [1]])
    # First 60s is transit; 14 remaining discharge steps each serve one vehicle.
    assert result['released_trips'] == 30
    assert result['completed_trips'] == 14
    assert result['unfinished_trips'] == 16
    assert result['edge_peak_queue_veh'][0] == 29


def test_flood_mapping_does_not_extend_source_feature_outside_frozen_arcs():
    import pandas as pd
    edges = pd.DataFrame({'source_feature_position': [10, 10], 'depth_feature_position': [10, -1],
                          'length_m': [100., 100.], 'speed_kph': [30., 30.],
                          'capacity_veh_h': [1000., 1000.], 'capacity_loss': [.8, .8]})
    t, cf = corridor_states(edges, [np.array([0]), np.array([1])], [0, 1],
                            np.array([[.4]]), {10: 0}, {'closure_depth_m': .3})
    assert cf[0, 0] == 0 and cf[0, 1] == 1
    assert t[0, 1] == 12
