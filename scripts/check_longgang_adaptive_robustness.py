"""New immutable sidecar: loss/closure/capacity sensitivities of selected plan.

This reuses the frozen pilot's weighted route library for controlled comparison;
it does not claim to re-optimize the Pareto set under all uncertainty cases.
"""
from pathlib import Path
import argparse
import json
import pickle
import uuid
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import yaml
from uftr.adaptive import surface_route, point_queue
from uftr.adaptive_network import corridor_states
from acquire_longgang_era5 import ROOT, sha, write


def check(run):
    report = json.loads((run/'provenance/validation_report.json').read_text(encoding='utf-8'))
    cfg = yaml.safe_load((run/'provenance/longgang_adaptive.yaml').read_text(encoding='utf-8'))
    rid = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_robustness_'+uuid.uuid4().hex[:8]
    out = run.parent/rid; out.mkdir()
    inputs = [Path(__file__), ROOT/'src/uftr/adaptive.py', ROOT/'src/uftr/adaptive_network.py',
              run/'manifest.json', run/'raw/pareto.json', run/'raw/network.pkl',
              run/'raw/routes_sample2.pkl', run/'raw/spatial_parameters.npz']
    parent_manifest = json.loads((run/'manifest.json').read_text(encoding='utf-8'))
    for r in parent_manifest['inputs']:
        if sha(ROOT/r['path']) != r['sha256']: raise ValueError('parent input changed: '+r['path'])
        inputs.append(ROOT/r['path'])
    output_sha = {r['path']: r['sha256'] for r in parent_manifest['outputs']}
    masks = sorted(set([0, report['recommended_mask']]))
    for path in [run/'raw/network.pkl', run/'raw/routes_sample2.pkl', run/'raw/spatial_parameters.npz']+[
                 run/'cases'/f'mask{mask:02d}_rain130_water.npz' for mask in masks]:
        if sha(path) != output_sha[path.relative_to(run).as_posix()]: raise ValueError('parent output changed')
        inputs.append(path)
    inputs = list(dict.fromkeys(inputs))
    pinned = [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for p in inputs]
    write(out/'status.json', {'status': 'running'})
    shutil_source = out/Path(__file__).name
    shutil_source.write_bytes(Path(__file__).read_bytes())
    with (run/'raw/network.pkl').open('rb') as stream: edges, corridors, chains = pickle.load(stream)
    with (run/'raw/routes_sample2.pkl').open('rb') as stream: record = pickle.load(stream)
    sample = record['sample']; packed = record['packed']; positions = packed['corridor_union']
    grid = np.load(ROOT/cfg['surface_package']/'raw/routing_grid.npz')
    spatial = np.load(run/'raw/spatial_parameters.npz')
    hourly = np.load(ROOT/cfg['rainfall_package']/'hourly_rainfall.npz')['precipitation_mm']
    sf = grid['source_feature_positions']; lookup = {int(f): j for j, f in enumerate(sf)}
    cells = grid['road_cells']; cell_lookup = {int(c): j for j, c in enumerate(cells)}
    links = pd.read_parquet(ROOT/cfg['surface_package']/'raw/road_sample_cells.parquet')
    links = links[['source_feature_position', 'cell']].drop_duplicates().sort_values(['source_feature_position', 'cell'])
    columns = np.array([cell_lookup[int(c)] for c in links.cell])
    fid = links.source_feature_position.to_numpy(); starts = np.flatnonzero(np.r_[True, np.diff(fid) != 0])
    output_columns = np.array([lookup[int(f)] for f in fid[starts]])
    periods = np.array([1 if 7 <= (k%96)/4 < 10 else (2 if 17 <= (k%96)/4 < 20 else 0) for k in range(480)])
    dry = report['dry_reference']
    results = []
    scenarios = [('loss_half', .5, .3, 1.), ('loss_double', 2., .3, 1.),
                 ('closure_020', 1., .2, 1.), ('capacity_double', 1., .3, 2.)]
    def traffic(depth, closure, capacity_multiplier):
        road_settings = dict(cfg['roads']); road_settings['closure_depth_m'] = closure
        tt, cf = corridor_states(edges, chains, positions, depth, lookup, road_settings)
        capacity = corridors.normal_capacity_veh_h.to_numpy()[positions]*capacity_multiplier
        normal = corridors.normal_time_s.to_numpy()[positions]
        direct = packed['direct_pairs']
        if len(direct):
            tt = np.column_stack([tt, np.ones((len(tt), len(direct)))])
            cf = np.column_stack([cf, np.ones((len(cf), len(direct)))])
            capacity = np.r_[capacity, np.full(len(direct), 1e12)]; normal = np.r_[normal, np.ones(len(direct))]
        r = point_queue(**{k: packed[k] for k in ['paths', 'pair_for_path', 'edge_for_stage', 'next_stage', 'first_stage', 'last_stage']},
              base_time=normal, capacity=capacity, times=tt, capacity_factors=cf, pair_rates=sample['rates'],
              periods=periods, access_seconds=packed['access_seconds'], settings=cfg['traffic'], save_series=False)
        r.pop('series'); r.pop('edge_peak_queue_veh')
        unlinked = dry['unlinked_trips_not_road_loaded']; intra = dry['intrazonal_trips_not_road_loaded']
        r['total_unfinished_trips'] = r['unfinished_trips']+unlinked
        r['generalized_vehicle_seconds'] = r['penalized_vehicle_seconds']+unlinked*7200+intra*300
        return r
    zero = np.where(grid['modelled_features'][None, :], np.zeros((481, len(sf)), np.float32), np.nan)
    dry_double = traffic(zero, .3, 2.)
    write(out/'dry_capacity_double.json', dry_double)
    for name, loss_multiplier, closure, capacity_multiplier in scenarios:
        for mask in masks:
            print(f'ROBUSTNESS {name} mask={mask}', flush=True)
            if loss_multiplier != 1:
                footprint = np.any([spatial['site_masks'][j] for j in range(len(spatial['site_masks'])) if mask & (1 << j)], axis=0) if mask else np.zeros(len(spatial['base_loss_mm_h']), bool)
                # Uncertainty applies to background losses. The separately
                # hypothesized +4mm/h intervention is held fixed.
                loss = spatial['base_loss_mm_h']*loss_multiplier+footprint*grid['district_weights']*cfg['optimization']['extra_loss_mm_h']
                hydro = surface_route(grid, hourly, loss, 1.3, cells, cfg['surface'])
                depth = np.full((481, len(sf)), np.nan, np.float32)
                depth[:, output_columns] = np.maximum.reduceat(hydro['sample_depth_m'][:, columns], starts, axis=1)
                np.savez_compressed(out/f'{name}_mask{mask:02d}_water.npz', depth_m=depth, ledger=hydro['ledger'])
                residual = float(np.abs(hydro['ledger'][:, -1]).max())
            else:
                depth = np.load(run/'cases'/f'mask{mask:02d}_rain130_water.npz')['depth_m']; residual = 0.
            r = traffic(depth, closure, capacity_multiplier)
            reference = dry_double if capacity_multiplier == 2 else dry
            rows = {'scenario': name, 'mask': mask, 'background_loss_multiplier': loss_multiplier,
                    'closure_depth_m': closure, 'capacity_multiplier': capacity_multiplier,
                    'extra_generalized_vehicle_hours': (r['generalized_vehicle_seconds']-reference['generalized_vehicle_seconds'])/3600,
                    'total_unfinished_trips': r['total_unfinished_trips'], 'peak_road_depth_m': float(np.nanmax(depth)),
                    'max_water_residual_m3': residual, 'max_vehicle_residual_veh': r['maximum_conservation_error_veh']}
            results.append(rows); write(out/f'{name}_mask{mask:02d}_traffic.json', r)
            pd.DataFrame(results).to_csv(out/'robustness_results.csv', index=False)
    comparison = []
    for name, *_ in scenarios:
        pair = [r for r in results if r['scenario'] == name]
        baseline = next(r for r in pair if r['mask'] == 0)
        selected = next(r for r in pair if r['mask'] == report['recommended_mask'])
        comparison.append({'scenario': name,
             'extra_cost_reduction_vehicle_hours': baseline['extra_generalized_vehicle_hours']-selected['extra_generalized_vehicle_hours'],
             'unfinished_reduction_trips': baseline['total_unfinished_trips']-selected['total_unfinished_trips']})
    result = {'run_id': rid, 'source_run': run.relative_to(ROOT).as_posix(), 'recommended_mask': report['recommended_mask'],
              'comparison': comparison, 'results': results,
              'note': 'Controlled paired sensitivities with fixed weighted route library; not re-optimization across uncertainty cases or field validation.'}
    write(out/'report.json', result)
    if any(sha(ROOT/r['path']) != r['sha256'] for r in pinned): raise ValueError('input changed')
    write(out/'status.json', {'status': 'complete'})
    write(out/'manifest.json', {'run_id': rid, 'inputs': pinned,
          'outputs': [{'path': p.relative_to(out).as_posix(), 'sha256': sha(p)} for p in sorted(out.iterdir()) if p.is_file()]})
    print('ROBUSTNESS_COMPLETE '+out.relative_to(ROOT).as_posix(), flush=True)
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('run')
    check(ROOT/parser.parse_args().run)
