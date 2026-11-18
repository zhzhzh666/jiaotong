"""Independent bookkeeping, brute-force dominance and scatter-add water replay."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from acquire_longgang_era5 import ROOT, sha, write


def audit(out):
    manifest = json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    cfg = yaml.safe_load((out/'provenance/longgang_adaptive.yaml').read_text(encoding='utf-8'))
    report = json.loads((out/'provenance/validation_report.json').read_text(encoding='utf-8'))
    for record in manifest['inputs']:
        if sha(ROOT/record['path']) != record['sha256']: raise ValueError('input SHA mismatch: '+record['path'])
    for record in manifest['outputs']:
        if sha(out/record['path']) != record['sha256']: raise ValueError('output SHA mismatch: '+record['path'])
    landcover = ROOT/report['landcover_package']
    parameters = np.load(landcover/'landcover_parameters.npz')
    categories = parameters['categorical_30m']; shape = parameters['shape']
    groups = {'built': [50], 'vegetation': [10, 20, 30, 40, 90, 95, 100], 'bare': [60, 70], 'water': [80]}
    loss = np.zeros(int(np.prod(shape))); fraction_sum = loss.copy()
    for name, codes in groups.items():
        fraction = np.isin(categories, codes).reshape(shape[0], 5, shape[1], 5).sum(axis=(1, 3)).ravel()/25
        if not np.array_equal(fraction, parameters[name]): raise ValueError('land-cover fraction mismatch')
        fraction_sum += fraction; loss += fraction*cfg['landcover']['loss_mm_h'][name]
    if not np.allclose(fraction_sum, 1, rtol=0, atol=1e-15): raise ValueError('land-cover fractions incomplete')
    if not np.array_equal(loss, parameters['loss_mm_h']): raise ValueError('land-cover loss mismatch')
    surface = ROOT/cfg['surface_package']; od = ROOT/cfg['od_package']
    grid = dict(np.load(surface/'raw/routing_grid.npz')); spatial = dict(np.load(out/'raw/spatial_parameters.npz'))
    features = grid['source_feature_positions']; known = grid['modelled_features']
    samples = pd.read_parquet(surface/'raw/road_sample_cells.parquet')[['source_feature_position', 'cell']].drop_duplicates()
    groups_cells = {int(f): g.cell.to_numpy(int) for f, g in samples.groupby('source_feature_position')}
    hourly = np.load(ROOT/cfg['rainfall_package']/'hourly_rainfall.npz')['precipitation_mm']
    receiver = grid['receiver']; internal = receiver >= 0; dt = cfg['surface']['internal_seconds']
    factor = 1-np.exp(-dt/grid['tau_s']); area = cfg['surface']['cell_size_m']**2
    selected_masks = sorted(set([0, report['recommended_mask']]))
    max_water_difference = max_ledger_difference = 0.; values_replayed = 0
    for mask in selected_masks:
        footprint = np.any([spatial['site_masks'][j] for j in range(len(spatial['site_masks'])) if mask & (1 << j)], axis=0) if mask else np.zeros(len(loss), bool)
        capacity = loss+footprint*grid['district_weights']*cfg['optimization']['extra_loss_mm_h']
        for scenario, multiplier in cfg['surface']['scenarios'].items():
            stored = np.load(out/'cases'/f'mask{mask:02d}_{scenario}_water.npz')
            h = np.zeros(len(loss)); cumulative = np.zeros(3); index = 0
            for step in range(len(hourly)*3600//dt):
                incoming = hourly[step*dt//3600, grid['rain_grid_id']]*multiplier*(dt/3600)/1000
                available = h+incoming
                removed = np.minimum(available, capacity*(dt/3600)/1000)
                after_loss = available-removed
                transfer = np.maximum(after_loss-grid['spill_depth_m'], 0)*factor
                h = after_loss-transfer
                # Different reduction implementation from solver's bincount.
                np.add.at(h, receiver[internal], transfer[internal])
                cumulative += [incoming.sum()*area, removed.sum()*area, transfer[~internal].sum()*area]
                if (step+1)*dt % 900 == 0:
                    index += 1
                    expected = np.array([h[groups_cells[int(fid)]].max() for fid in features[known]], np.float32)
                    actual = stored['depth_m'][index, known]
                    difference = float(np.max(np.abs(expected-actual), initial=0))
                    max_water_difference = max(max_water_difference, difference)
                    values_replayed += len(expected)
                    independent = np.r_[cumulative, h.sum()*area]
                    max_ledger_difference = max(max_ledger_difference, float(np.max(np.abs(independent-stored['ledger'][index, 1:5]))))
            print(f'Independent water replay mask={mask} {scenario} checked', flush=True)
    if max_water_difference > 1e-5 or max_ledger_difference > .001:
        raise ValueError('independent water replay mismatch')
    frame = pd.read_csv(out/'raw/scenario_results.csv')
    masks = sorted(frame['mask'].unique()); monotonic = 0
    feasible = {m for m in range(1 << cfg['optimization']['candidates']) if m.bit_count() <= cfg['optimization']['max_sites']}
    if set(map(int, masks)) != feasible or len(frame) != len(feasible)*len(cfg['surface']['scenarios']):
        raise ValueError('not all feasible candidate/scenario combinations were evaluated')
    if frame.duplicated(['mask', 'scenario']).any(): raise ValueError('duplicate scenario evaluation')
    for scenario in cfg['surface']['scenarios']:
        data = {mask: np.load(out/'cases'/f'mask{mask:02d}_{scenario}_water.npz')['depth_m'] for mask in masks}
        for mask in masks:
            if not np.isnan(data[mask][:, ~known]).all(): raise ValueError('unknown road lost NaN')
            for bit in range(cfg['optimization']['candidates']):
                other = mask | (1 << bit)
                if other != mask and other in data:
                    if np.any(data[other][:, known] > data[mask][:, known]+1e-6):
                        raise ValueError('drainage treatment increased cellwise road depth')
                    monotonic += 1
    # Full source arc coverage and directed path continuity.
    edges = pd.read_parquet(out/'raw/source_edges.parquet'); corridors = pd.read_csv(out/'raw/corridors.csv')
    mapping = pd.read_csv(surface/'raw/od_graph_arc_mapping.csv')
    if set(edges.loc[edges.depth_feature_position >= 0, 'edge_id']) != set(mapping.edge_id):
        raise ValueError('flood mapping extended outside frozen directed arc coverage')
    chain = dict(np.load(out/'raw/corridor_source_arc_index.npz'))
    if not np.array_equal(np.sort(chain['flat']), np.arange(len(edges))): raise ValueError('arc coverage mismatch')
    u = edges.u.to_numpy(); v = edges.v.to_numpy(); total_paths = 0
    for start, end, record in zip(chain['offsets'][:-1], chain['offsets'][1:], corridors.itertuples()):
        indices = chain['flat'][start:end]
        if u[indices[0]] != record.u or v[indices[-1]] != record.v or not np.array_equal(v[indices[:-1]], u[indices[1:]]):
            raise ValueError('corridor directed continuity mismatch')
    all_periods = [np.load(od/'od_sensitivity_veh_h.npz')['base__'+p] for p in ['offpeak', 'morning_peak', 'evening_peak']]
    conn = pd.read_csv(od/'zone_connectors.csv'); connected = conn.connected.to_numpy(bool)
    allowed = connected[:, None] & connected[None, :] & ~np.eye(len(conn), dtype=bool)
    for path in out.glob('raw/sample*_pairs.csv'):
        pairs = pd.read_csv(path)
        expected = np.where(allowed, all_periods[0], 0).sum(axis=1)
        actual = np.bincount(pairs.origin_zone.to_numpy(int), weights=pairs.offpeak_veh_h, minlength=len(conn))
        if not np.allclose(actual, expected, rtol=1e-12, atol=1e-8): raise ValueError('origin row totals changed by sampling')
    skims = np.load(od/'network_skims.npz')['travel_time_with_access_s']
    maximum_skim_difference = 0.; skims_checked = 0
    for path in out.glob('raw/sample*_library.json'):
        library = json.loads(path.read_text(encoding='utf-8'))
        pairs = pd.read_csv(path.with_name(path.name.replace('_library.json', '_pairs.csv')))
        for pair_index, alternatives in enumerate(library['original_corridor_paths']):
            pair = pairs.iloc[pair_index]
            expected = skims[int(pair.origin_zone), int(pair.destination_zone)]
            coincident = bool(pair.coincident_connector)
            if np.isfinite(expected) != bool(alternatives or coincident):
                raise ValueError('contracted route reachability differs from frozen original skim')
            if np.isfinite(expected):
                access = (conn.connector_distance_m.iloc[int(pair.origin_zone)]+
                          conn.connector_distance_m.iloc[int(pair.destination_zone)])/(cfg['traffic']['access_speed_kph']/3.6)
                actual = (float(corridors.normal_time_s.iloc[list(alternatives[0])].sum()) if alternatives else 0.)+access
                maximum_skim_difference = max(maximum_skim_difference, abs(actual-expected)); skims_checked += 1
            for route in alternatives:
                route = np.asarray(route, int)
                if len(route) > 1 and not np.array_equal(corridors.v.to_numpy()[route[:-1]], corridors.u.to_numpy()[route[1:]]):
                    raise ValueError('route directed continuity mismatch')
                total_paths += 1
    if maximum_skim_difference > 1e-5: raise ValueError('corridor contraction changed free-flow OD path cost')
    expected_total = float(pd.read_csv(od/'interval_totals.csv').expected_vehicle_trips.sum()*len(hourly)/24)
    traffic_files = list(out.glob('cases/*_traffic.json')); max_traffic_residual = 0.
    for path in traffic_files:
        record = json.loads(path.read_text(encoding='utf-8'))
        series = pd.read_csv(path.with_name(path.stem+'_series.csv'))
        residual = series.released-series.completed-series.queue-series.transit-series.origin_backlog
        max_traffic_residual = max(max_traffic_residual, float(np.abs(residual).max()))
        if (series.completed.diff().dropna() < -1e-7).any() or (series[['queue', 'transit', 'origin_backlog']].min().min() < -1e-5):
            raise ValueError('invalid vehicle ledger')
        last = series.iloc[-1]
        if not np.isclose(last.cumulative_vehicle_seconds, record['vehicle_seconds'], rtol=1e-12): raise ValueError('occupancy cost mismatch')
        if abs(record['total_trips']-expected_total) > 1e-5: raise ValueError('five-day full demand total not conserved')
        if abs(record['total_trips']-record['total_completed_trips']-record['total_unfinished_trips']) > 1e-5:
            raise ValueError('total completed/unfinished bookkeeping failure')
        if abs(record['transit_ring_remaining_veh']-record['transit_counter_veh']) > 1e-5:
            raise ValueError('transit ring vs occupancy counter mismatch')
    if max_traffic_residual > 1e-4: raise ValueError('vehicle ledger residual')
    # Independent objective reconstruction and brute-force Pareto dominance.
    dry = json.loads((out/'raw/dry_reference.json').read_text(encoding='utf-8'))
    costs = pd.read_csv(out/'raw/candidates.csv').relative_cost.to_numpy()
    objective = {}
    for mask in masks:
        evaluated = []
        for scenario in cfg['surface']['scenarios']:
            p = out/'cases'/f'mask{mask:02d}_{scenario}_sample{cfg["traffic"]["destinations_per_origin"]}_dt{cfg["traffic"]["internal_seconds"]}_traffic.json'
            r = json.loads(p.read_text(encoding='utf-8'))
            evaluated.append([(r['generalized_vehicle_seconds']-dry['generalized_vehicle_seconds'])/3600,
                              r['total_unfinished_trips']])
        objective[int(mask)] = [max(v[0] for v in evaluated), max(v[1] for v in evaluated),
                               sum(costs[j] for j in range(len(costs)) if mask & (1 << j))]
    exact = []
    for mask in masks:
        a = objective[int(mask)]
        if not any(all(b[j] <= a[j] for j in range(3)) and any(b[j] < a[j] for j in range(3))
                   for other, b in objective.items() if other != mask): exact.append(int(mask))
    pareto = json.loads((out/'raw/pareto.json').read_text(encoding='utf-8'))
    if sorted(exact) != sorted(pareto['exact_pareto_masks']): raise ValueError('Pareto set mismatch')
    for mask, values in objective.items():
        if not np.allclose(values, pareto['objectives'][str(mask)], rtol=1e-12, atol=1e-8): raise ValueError('objective mismatch')
    result = {'run_id': out.name, 'passed': True, 'audit_script_sha256': sha(Path(__file__)),
              'input_hashes': len(manifest['inputs']),
              'output_hashes': len(manifest['outputs']), 'landcover_fraction_cells_checked': len(loss),
              'independent_scatter_add_road_depth_values': values_replayed,
              'maximum_replayed_road_difference_m': max_water_difference,
              'maximum_replayed_volume_difference_m3': max_ledger_difference,
              'drainage_subset_monotonicity_checks': monotonic, 'source_arcs_partitioned_once': len(edges),
              'frozen_depth_mapped_arcs_checked': len(mapping),
              'directed_library_paths_checked': total_paths, 'traffic_ledgers_checked': len(traffic_files),
              'original_skim_pairs_checked': skims_checked,
              'maximum_contracted_vs_original_skim_difference_s': maximum_skim_difference,
              'maximum_vehicle_ledger_residual': max_traffic_residual,
              'exact_feasible_combinations': len(masks), 'independent_pareto_masks': exact,
              'full_synthetic_demand_total_5days': expected_total,
              'note': 'Numerical bookkeeping and small candidate-set optimality only; no observed calibration or full-OD dynamic equilibrium validation.'}
    # Sidecar audit leaves the frozen run and its manifest untouched.
    write(Path(str(out)+'_audit.json'), result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('run')
    audit(ROOT/parser.parse_args().run)
