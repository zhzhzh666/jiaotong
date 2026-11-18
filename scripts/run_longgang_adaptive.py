"""Run a fully enumerated four-site NSGA-II pilot with coupled water/traffic."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import json
import pickle
import shutil
import time
import traceback
import uuid
import zipfile
import networkx as nx
import numpy as np
import pandas as pd
import rasterio
import yaml
from scipy.sparse.csgraph import dijkstra
from uftr.adaptive import surface_route, sample_od, point_queue, nsga2, fronts, feasible_masks
from uftr.adaptive_network import contract, corridor_states, route_library, pack_paths
from acquire_longgang_era5 import ROOT, sha, write


def run(config, landcover, resume=None, reuse_water=None):
    cfg = yaml.safe_load(config.read_text(encoding='utf-8'))
    if cfg['region'] != 'longgang' or cfg['include_dapeng'] is not False:
        raise ValueError('scope must exclude Dapeng')
    od = ROOT/cfg['od_package']; surface = ROOT/cfg['surface_package']; rain = ROOT/cfg['rainfall_package']
    source_files = [config, Path(__file__), ROOT/'src/uftr/adaptive.py', ROOT/'src/uftr/adaptive_network.py',
                    ROOT/'scripts/acquire_longgang_worldcover.py', landcover/'manifest.json',
                    landcover/'landcover_parameters.npz', landcover/'source.json',
                    surface/'manifest.json', surface/'raw/routing_grid.npz', surface/'raw/road_sample_cells.parquet',
                    surface/'gis/terrain_dsm_mean_150m.tif', surface/'raw/road_feature_status.csv',
                    surface/'raw/od_graph_arc_mapping.csv',
                    rain/'manifest.json', rain/'hourly_rainfall.npz',
                    od/'manifest.json', od/'inferred_source_network.graphml', od/'zone_connectors.csv',
                    od/'od_sensitivity_veh_h.npz', od/'interval_totals.csv']
    reusable = []
    if reuse_water:
        old_inputs_path = reuse_water/'provenance/inputs.json'
        old_inputs = json.loads(old_inputs_path.read_text(encoding='utf-8'))
        exclusions = {'scripts/run_longgang_adaptive.py', 'src/uftr/adaptive_network.py', 'src/uftr/adaptive.py'}
        for record in old_inputs:
            if record['path'] not in exclusions and sha(ROOT/record['path']) != record['sha256']:
                raise ValueError('water reuse input changed: '+record['path'])
        old_tree = ast.parse((reuse_water/'provenance/run_longgang_adaptive.py').read_text(encoding='utf-8'))
        new_tree = ast.parse(Path(__file__).read_text(encoding='utf-8'))
        for name in ['hydro', 'aggregate']:
            def signature(tree):
                return ast.dump(next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name), include_attributes=False)
            if signature(old_tree) != signature(new_tree): raise ValueError('water reuse computation changed')
        old_kernel = ast.parse((reuse_water/'provenance/adaptive.py').read_text(encoding='utf-8'))
        new_kernel = ast.parse((ROOT/'src/uftr/adaptive.py').read_text(encoding='utf-8'))
        def kernel_signature(tree):
            return ast.dump(next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'surface_route'), include_attributes=False)
        if kernel_signature(old_kernel) != kernel_signature(new_kernel): raise ValueError('water routing kernel changed')
        for path in sorted(reuse_water.glob('cases/*_water.npz')):
            try:
                with np.load(path) as data:
                    if data['depth_m'].shape != (481, 7800) or data['ledger'].shape != (481, 6): continue
                    if not np.isfinite(data['ledger']).all(): continue
                reusable.append(path)
            except (ValueError, OSError, zipfile.BadZipFile):
                continue
        source_files.extend([old_inputs_path, reuse_water/'provenance/run_longgang_adaptive.py', *reusable])
    inputs = [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in source_files]
    if resume:
        out = resume
        pinned = json.loads((out/'provenance/inputs.json').read_text(encoding='utf-8'))
        if pinned != inputs: raise ValueError('resume requires identical sources, parameters and data')
        rid = out.name
    else:
        rid = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_adaptive_'+uuid.uuid4().hex[:8]
        out = ROOT/cfg['output_root']/rid
        for folder in ['provenance', 'raw', 'cases', 'figures']:
            (out/folder).mkdir(parents=True, exist_ok=False)
        write(out/'provenance/inputs.json', inputs)
        for p in source_files[:5]: shutil.copy2(p, out/'provenance'/p.name)
        shutil.copy2(landcover/'source.json', out/'provenance/worldcover_source.json')
        if reusable:
            for p in reusable: shutil.copy2(p, out/'cases'/p.name)
            write(out/'provenance/water_reuse.json', {'source_run': reuse_water.relative_to(ROOT).as_posix(),
                  'files': [{'path': p.name, 'sha256': sha(p)} for p in reusable],
                  'validation': 'Identical hydrology kernel/aggregate/hydro AST and config/data SHAs; traffic and route libraries rebuilt.'})
    print('OUTPUT '+out.relative_to(ROOT).as_posix(), flush=True)
    started = time.perf_counter()
    write(out/'status.json', {'status': 'running', 'run_id': rid})
    try:
        # Validate direct inputs against their existing frozen packages.
        for package, selected in [(od, ['inferred_source_network.graphml', 'zone_connectors.csv', 'od_sensitivity_veh_h.npz', 'interval_totals.csv']),
                                  (surface, ['raw/routing_grid.npz', 'raw/road_sample_cells.parquet', 'raw/road_feature_status.csv', 'gis/terrain_dsm_mean_150m.tif', 'raw/od_graph_arc_mapping.csv']),
                                  (rain, ['hourly_rainfall.npz']), (landcover, ['landcover_parameters.npz'])]:
            records = {r['path']: r['sha256'] for r in json.loads((package/'manifest.json').read_text(encoding='utf-8'))['outputs']}
            for name in selected:
                if sha(package/name) != records[name]: raise ValueError('frozen input mismatch: '+name)
        grid = dict(np.load(surface/'raw/routing_grid.npz'))
        hourly = np.load(rain/'hourly_rainfall.npz')['precipitation_mm']
        losses = np.load(landcover/'landcover_parameters.npz')['loss_mm_h']
        with rasterio.open(surface/'gis/terrain_dsm_mean_150m.tif') as terrain:
            shape = terrain.shape; transform = terrain.transform
        rr, cc = np.indices(shape)
        x = transform.c+(cc.ravel()+.5)*transform.a
        y = transform.f+(rr.ravel()+.5)*transform.e
        road_cells = grid['road_cells']; feature_ids = grid['source_feature_positions']
        samples = pd.read_parquet(surface/'raw/road_sample_cells.parquet')
        samples = samples[['source_feature_position', 'cell']].drop_duplicates().sort_values(['source_feature_position', 'cell'])
        cell_lookup = {int(c): j for j, c in enumerate(road_cells)}
        sample_columns = np.array([cell_lookup[int(c)] for c in samples.cell], int)
        sf = samples.source_feature_position.to_numpy()
        reduce_starts = np.flatnonzero(np.r_[True, np.diff(sf) != 0])
        reduced_features = sf[reduce_starts]
        feature_lookup = {int(f): j for j, f in enumerate(feature_ids)}
        reduced_columns = np.array([feature_lookup[int(f)] for f in reduced_features])
        def aggregate(result):
            values = np.maximum.reduceat(result['sample_depth_m'][:, sample_columns], reduce_starts, axis=1)
            depth = np.full((len(values), len(feature_ids)), np.nan, np.float32)
            depth[:, reduced_columns] = values
            return depth
        def hydro(mask, scenario, site_masks):
            path = out/'cases'/f'mask{mask:02d}_{scenario}_water.npz'
            if path.exists():
                data = np.load(path)
                return {k: data[k] for k in data.files}
            print(f'SURFACE mask={mask} scenario={scenario}', flush=True)
            modified = losses.copy()
            # Overlapping site footprints are a union; no double-counted upgrade.
            if mask:
                footprint = np.any([site_masks[j] for j in range(len(site_masks)) if mask & (1 << j)], axis=0)
                modified += footprint*grid['district_weights']*cfg['optimization']['extra_loss_mm_h']
            r = surface_route(grid, hourly, modified, cfg['surface']['scenarios'][scenario], road_cells, cfg['surface'])
            depth = aggregate(r)
            result = {'depth_m': depth, 'ledger': r['ledger'], 'peak_depth_m': r['peak_depth_m'],
                      'final_depth_m': r['final_depth_m']}
            np.savez_compressed(path, **result)
            return result
        scenarios = list(cfg['surface']['scenarios'])
        base = {name: hydro(0, name, []) for name in scenarios}
        peak = base['rain100']['peak_depth_m']
        # Candidate selection uses flood exposure at road cells, not optimized traffic results.
        counts = np.bincount(samples.cell, minlength=len(losses))
        eligible = (grid['district_weights'] > 0) & (counts > 0)
        score = np.where(eligible, peak*np.sqrt(counts), -1.)
        ranked = np.argsort(-score, kind='stable'); centers = []
        for cell in ranked:
            if score[cell] <= 0: break
            if all(np.hypot(x[cell]-x[c], y[cell]-y[c]) >= cfg['optimization']['minimum_site_separation_m'] for c in centers):
                centers.append(int(cell))
            if len(centers) == cfg['optimization']['candidates']: break
        if len(centers) != cfg['optimization']['candidates']: raise ValueError('insufficient separated candidates')
        site_masks = [((x-x[c])**2+(y-y[c])**2 <= cfg['optimization']['radius_m']**2) & (grid['district_weights'] > 0) for c in centers]
        costs = np.array([grid['district_weights'][m].sum()*cfg['surface']['cell_size_m']**2/1e6*
                          cfg['optimization']['relative_cost_per_km2'] for m in site_masks])
        pd.DataFrame([{'site': j, 'cell': c, 'x_m': x[c], 'y_m': y[c], 'baseline_peak_m': peak[c],
                       'relative_cost': costs[j], 'footprint_cells': int(site_masks[j].sum()),
                       'radius_m': cfg['optimization']['radius_m']} for j, c in enumerate(centers)]).to_csv(out/'raw/candidates.csv', index=False)
        np.savez_compressed(out/'raw/spatial_parameters.npz', base_loss_mm_h=losses,
                            site_masks=np.asarray(site_masks), site_cells=centers, x_m=x, y_m=y)
        print('Loading frozen directed graph and contracting source-preserving corridors', flush=True)
        connectors = pd.read_csv(od/'zone_connectors.csv')
        connector_nodes = connectors.node_id.fillna(-1).to_numpy(int)
        prep = out/'raw/network.pkl'
        if prep.exists():
            with prep.open('rb') as stream: edges, corridors, chains = pickle.load(stream)
        else:
            graph = nx.read_graphml(od/'inferred_source_network.graphml', node_type=int, force_multigraph=True)
            edges, corridors, chains = contract(graph, connector_nodes[connector_nodes >= 0], cfg['roads'])
            with prep.open('wb') as stream: pickle.dump((edges, corridors, chains), stream, protocol=5)
            del graph
        frozen_arcs = pd.read_csv(surface/'raw/od_graph_arc_mapping.csv')
        identity = edges.set_index('edge_id').loc[frozen_arcs.edge_id]
        for column in ['u', 'v', 'key', 'source_feature_position']:
            if not np.array_equal(identity[column].to_numpy(), frozen_arcs[column].to_numpy()):
                raise ValueError('frozen road depth directed identity mismatch: '+column)
        edges['depth_feature_position'] = np.where(edges.edge_id.isin(frozen_arcs.edge_id),
                                                   edges.source_feature_position, -1)
        # Persist the corrected spatial applicability, preserving original IDs.
        with prep.open('wb') as stream: pickle.dump((edges, corridors, chains), stream, protocol=5)
        edges.to_parquet(out/'raw/source_edges.parquet', index=False)
        corridors.to_csv(out/'raw/corridors.csv', index=False)
        np.savez_compressed(out/'raw/corridor_source_arc_index.npz', flat=np.concatenate(chains),
                            offsets=np.r_[0, np.cumsum([len(p) for p in chains])])
        matrices_npz = np.load(od/'od_sensitivity_veh_h.npz')
        if not np.array_equal(matrices_npz['zone_ids'].astype(str), connectors.zone_id.astype(str)):
            raise ValueError('OD/connector zone order mismatch')
        matrices = [matrices_npz['base__'+period] for period in ['offpeak', 'morning_peak', 'evening_peak']]
        periods = np.array([1 if 7 <= (k%96)/4 < 10 else (2 if 17 <= (k%96)/4 < 20 else 0)
                            for k in range(len(hourly)*4)], int)
        global_positions = np.arange(len(corridors))
        states = [(corridors.normal_time_s.to_numpy(), corridors.normal_capacity_veh_h.to_numpy())]
        for name in ['rain100', 'rain130']:
            depth = np.nanmax(np.where(np.isfinite(base[name]['depth_m']), base[name]['depth_m'], -np.inf), axis=0)
            depth[~grid['modelled_features']] = np.nan
            t, cf = corridor_states(edges, chains, global_positions, depth[None, :], feature_lookup, cfg['roads'])
            states.append((t[0], cf[0]*corridors.normal_capacity_veh_h.to_numpy()))
        def prepare_sample(count):
            path = out/'raw'/f'routes_sample{count}.pkl'
            if path.exists():
                with path.open('rb') as stream: return pickle.load(stream)
            sample = sample_od(matrices, connector_nodes, count, cfg['seed'])
            origins = connector_nodes[sample['origin_zone']]; destinations = connector_nodes[sample['destination_zone']]
            routes = route_library(corridors, states, origins, destinations)
            direct = np.flatnonzero(origins == destinations)
            packed = pack_paths(routes, direct)
            access_distance = connectors.connector_distance_m.fillna(0).to_numpy()
            access = (access_distance[sample['origin_zone']]+access_distance[sample['destination_zone']])/(cfg['traffic']['access_speed_kph']/3.6)
            packed['access_seconds'] = access
            # Exact sample strata weights, pair nodes and path library are archived.
            record = {'sample': sample, 'packed': packed}
            with path.open('wb') as stream: pickle.dump(record, stream, protocol=5)
            pd.DataFrame({'origin_zone': sample['origin_zone'], 'destination_zone': sample['destination_zone'],
                          'origin_node': origins, 'destination_node': destinations,
                          'offpeak_veh_h': sample['rates'][0], 'library_paths': [len(r) for r in routes],
                          'coincident_connector': origins == destinations}).to_csv(out/'raw'/f'sample{count}_pairs.csv', index=False)
            write(out/'raw'/f'sample{count}_library.json', {'original_corridor_paths': routes, 'direct_pairs': direct.tolist(),
                  'corridor_union': packed['corridor_union'].tolist(), 'n_path_stages': len(packed['edge_for_stage'])})
            return record
        traffic_cache = {}
        def traffic(depth, label, count=None, dt=None):
            count = count or cfg['traffic']['destinations_per_origin']; dt = dt or cfg['traffic']['internal_seconds']
            key = f'{label}_sample{count}_dt{dt}'; path = out/'cases'/(key+'_traffic.json')
            if path.exists(): return json.loads(path.read_text(encoding='utf-8'))
            record = prepare_sample(count); packed = record['packed']; sample = record['sample']
            positions = packed['corridor_union']
            tt, cf = corridor_states(edges, chains, positions, depth, feature_lookup, cfg['roads'])
            cap = corridors.normal_capacity_veh_h.to_numpy()[positions]
            normal = corridors.normal_time_s.to_numpy()[positions]
            direct = packed['direct_pairs']
            if len(direct):
                tt = np.column_stack([tt, np.full((len(tt), len(direct)), 1.)])
                cf = np.column_stack([cf, np.ones((len(cf), len(direct)))])
                cap = np.r_[cap, np.full(len(direct), 1e12)]; normal = np.r_[normal, np.ones(len(direct))]
            result = point_queue(**{k: packed[k] for k in ['paths', 'pair_for_path', 'edge_for_stage', 'next_stage', 'first_stage', 'last_stage']},
                    base_time=normal, capacity=cap, times=tt, capacity_factors=cf,
                    pair_rates=sample['rates'], periods=periods,
                    access_seconds=packed['access_seconds'], settings=cfg['traffic'], dt=dt)
            series = result.pop('series'); edge_peak = result.pop('edge_peak_queue_veh')
            pd.DataFrame(series, columns=['time_h', 'released', 'completed', 'queue', 'transit', 'origin_backlog', 'unfinished', 'conservation_error', 'cumulative_vehicle_seconds']).to_csv(out/'cases'/(key+'_traffic_series.csv'), index=False)
            np.savez_compressed(out/'cases'/(key+'_queue_peaks.npz'), corridor_union=positions, peak_queue_veh=edge_peak)
            unlinked = float(sum(sample['unlinked_rates'][p]*.25 for p in periods))
            intra = float(sum(sample['intrazonal_rates'][p]*.25 for p in periods))
            result.update({'unlinked_trips_not_road_loaded': unlinked, 'intrazonal_trips_not_road_loaded': intra,
                           'total_trips': result['released_trips']+unlinked+intra,
                           'total_completed_trips': result['completed_trips']+intra,
                           'total_unfinished_trips': result['unfinished_trips']+unlinked,
                           'generalized_vehicle_seconds': result['penalized_vehicle_seconds']+
                                unlinked*cfg['traffic']['terminal_penalty_seconds']+intra*cfg['traffic']['intrazonal_seconds'],
                           'sample_pairs': len(sample['origin_zone']), 'sample_destinations_per_origin': count,
                           'internal_seconds': dt, 'active_corridors': len(positions), 'path_stages': len(packed['edge_for_stage'])})
            write(path, result)
            return result
        zero = np.where(grid['modelled_features'][None, :], np.zeros_like(base['rain100']['depth_m']), np.nan)
        dry = traffic(zero, 'dry')
        write(out/'raw/dry_reference.json', dry)
        rows = []; objectives = {}
        def evaluate(mask):
            if mask in objectives: return objectives[mask]
            print(f'EVALUATE mask={mask} selected={mask.bit_count()}', flush=True)
            scores = []
            for scenario in scenarios:
                water = hydro(mask, scenario, site_masks)
                metrics = traffic(water['depth_m'], f'mask{mask:02d}_{scenario}')
                relative = metrics['generalized_vehicle_seconds']-dry['generalized_vehicle_seconds']
                score = {'mask': mask, 'sites': mask.bit_count(), 'scenario': scenario,
                         'extra_generalized_vehicle_hours_vs_dry': relative/3600,
                         'unfinished_trips': metrics['total_unfinished_trips'],
                         'completed_trips': metrics['total_completed_trips'],
                         'peak_modelled_road_depth_m': float(np.nanmax(water['depth_m'])),
                         'max_water_balance_residual_m3': float(np.abs(water['ledger'][:, -1]).max()),
                         'max_vehicle_conservation_error': metrics['maximum_conservation_error_veh'],
                         'relative_cost': float(sum(costs[j] for j in range(len(costs)) if mask & (1 << j)))}
                rows.append(score); scores.append(score)
            value = [max(s['extra_generalized_vehicle_hours_vs_dry'] for s in scores),
                     max(s['unfinished_trips'] for s in scores), scores[0]['relative_cost']]
            objectives[mask] = value
            pd.DataFrame(rows).to_csv(out/'raw/scenario_results.csv', index=False)
            write(out/'raw/objectives_checkpoint.json', {str(m): v for m, v in objectives.items()})
            return value
        search = []
        for seed in cfg['optimization']['verification_seeds']:
            result = nsga2(len(centers), cfg['optimization']['max_sites'], evaluate,
                           cfg['optimization']['population'], cfg['optimization']['generations'], seed)
            search.append(result)
        masks = feasible_masks(len(centers), cfg['optimization']['max_sites'])
        values = np.asarray([evaluate(m) for m in masks])
        pareto = [masks[j] for j in fronts(values)[0]]
        for result in search:
            result['exact_front_recall'] = len(set(result['pareto_masks']) & set(pareto))/len(pareto)
            result['exact_front_precision'] = len(set(result['pareto_masks']) & set(pareto))/len(result['pareto_masks'])
        pv = np.array([objectives[m] for m in pareto]); span = np.ptp(pv, axis=0)
        normalized = np.divide(pv-pv.min(axis=0), span, out=np.zeros_like(pv), where=span > 0)
        recommendation = int(pareto[int(np.argmin(normalized.sum(axis=1)))])
        write(out/'raw/nsga2_search.json', search)
        write(out/'raw/pareto.json', {'exact_pareto_masks': pareto, 'recommended_mask': recommendation,
              'recommendation_rule': 'equal-weight normalized distance sum to ideal on enumerated front; heuristic, not official preference',
              'objectives': {str(m): objectives[m] for m in masks}})
        pd.DataFrame([{'mask': m, 'selected_sites': ','.join(str(j) for j in range(len(centers)) if m & (1 << j)),
                       'worst_extra_generalized_vehicle_hours': objectives[m][0],
                       'worst_unfinished_trips': objectives[m][1], 'relative_cost': objectives[m][2],
                       'pareto': m in pareto, 'recommended': m == recommendation} for m in masks]).to_csv(out/'raw/optimization_results.csv', index=False)
        print('Running time-step and destination-strata sensitivities', flush=True)
        sensitivities = []
        for mask in sorted(set([0, recommendation])):
            depth = hydro(mask, 'rain130', site_masks)['depth_m']
            main = traffic(depth, f'mask{mask:02d}_rain130')
            for count, dt in [(cfg['traffic']['destinations_per_origin'], cfg['traffic']['verification_seconds']),
                              (cfg['traffic']['verification_destinations_per_origin'], cfg['traffic']['internal_seconds'])]:
                refined = traffic(depth, f'mask{mask:02d}_rain130', count, dt)
                refined_dry = traffic(zero, 'dry', count, dt)
                sensitivities.append({'mask': mask, 'destinations_per_origin': count, 'step_seconds': dt,
                     'extra_generalized_vehicle_hours': (refined['generalized_vehicle_seconds']-refined_dry['generalized_vehicle_seconds'])/3600,
                     'unfinished_trips': refined['total_unfinished_trips'],
                     'generalized_hours_difference_from_main': (refined['generalized_vehicle_seconds']-main['generalized_vehicle_seconds'])/3600,
                     'unfinished_difference_from_main': refined['total_unfinished_trips']-main['total_unfinished_trips']})
        pd.DataFrame(sensitivities).to_csv(out/'raw/traffic_sensitivities.csv', index=False)
        frame = pd.DataFrame(rows)
        footprint = np.any([site_masks[j] for j in range(len(centers)) if recommendation & (1 << j)], axis=0) if recommendation else np.zeros(len(losses), bool)
        report = {'run_id': rid, 'region': 'longgang', 'include_dapeng': False,
                  'method': 'WorldCover-spatial-loss D8 + directed-corridor proportional point queues + departure-route choice + NSGA-II pilot',
                  'calibrated': False, 'landcover_package': landcover.relative_to(ROOT).as_posix(),
                  'scenarios': cfg['surface']['scenarios'], 'departure_hours': len(hourly),
                  'synthetic_daily_demand_repeated': True, 'dry_reference': dry,
                  'source_directed_arcs': len(edges), 'corridors': len(corridors),
                  'frozen_depth_mapped_arcs': len(frozen_arcs),
                  'candidate_count': len(centers), 'max_selected_sites': cfg['optimization']['max_sites'],
                  'feasible_combinations_exhaustively_checked': len(masks), 'exact_pareto_masks': pareto,
                  'recommended_mask': recommendation, 'recommended_sites': [j for j in range(len(centers)) if recommendation & (1 << j)],
                  'recommended_treatment_area_km2': float(grid['district_weights'][footprint].sum()*22500/1e6),
                  'nsga2_front_recall_by_seed': {str(r['seed']): r['exact_front_recall'] for r in search},
                  'worst_case_base_objectives': objectives[0], 'worst_case_recommended_objectives': objectives[recommendation],
                  'maximum_water_balance_residual_m3': float(frame.max_water_balance_residual_m3.max()),
                  'maximum_vehicle_conservation_error_veh': float(frame.max_vehicle_conservation_error.max()),
                  'traffic_sensitivities': sensitivities, 'elapsed_seconds': time.perf_counter()-started,
                  'limitations': ['Uncalibrated ERA5/DSM hydrology; WorldCover 2021 mapped cover, not observed hydraulic parameters',
                    'Loss capacities, +4mm/h treatment, 750m circular footprint, relative costs and scenarios are assumptions',
                    'Full upstream catchment, sewer network and river backwater not resolved; candidate sites are screening locations',
                    'Source graph topology inferred, one effective directional lane/capacity assumed; no turn restrictions or signals',
                    'All source arcs retained in corridor provenance; serial time sum and minimum capacity approximate internal queues',
                    'Origin-stratified weighted destinations, not exact full-OD loading; 24h synthetic demand repeated for five days',
                    'Finite route library and departure-time choice; no en-route rerouting or dynamic equilibrium convergence',
                    'Fluid queues use proportional commodity service, not guaranteed FIFO; unlimited storage, no physical spillback',
                    'Unknown bridge/tunnel and outside-flood-coverage roads assumed normal in traffic, not asserted dry',
                    'Three scenarios use worst case, no measured probabilities; terminal 2h penalty is an assumed cost, not trip completion',
                    'Four-site <=3 selection pilot globally verified only over these candidates; not full-district engineering optimization']}
        write(out/'provenance/validation_report.json', report)
        make_figures(out, frame, values, masks, pareto, recommendation, x, y, grid, site_masks, peak)
        # Inputs must still equal their pinned bytes after long computation.
        if any(sha(ROOT/f['path']) != f['sha256'] for f in inputs):
            raise ValueError('input changed during run')
        write(out/'status.json', {'status': 'complete_uncalibrated_pilot', 'run_id': rid})
        write(out/'manifest.json', {'run_id': rid, 'inputs': inputs,
              'outputs': [{'path': p.relative_to(out).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size}
                          for p in sorted(out.rglob('*')) if p.is_file()]})
        # Full source graph and large per-case caches stay local; compact zip excludes them.
        with zipfile.ZipFile(str(out)+'.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=4) as archive:
            for p in sorted(out.rglob('*')):
                if p.is_file() and p.suffix not in {'.pkl', '.npz', '.parquet'}:
                    archive.write(p, p.relative_to(out).as_posix())
        print('COMPLETE '+out.relative_to(ROOT).as_posix(), flush=True)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        return out
    except Exception:
        write(out/'status.json', {'status': 'failed', 'traceback': traceback.format_exc()})
        raise


def make_figures(out, frame, values, masks, pareto, recommendation, x, y, grid, site_masks, peak):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False, 'svg.fonttype': 'none'})
    def save(fig, name):
        for ext in ['png', 'svg']: fig.savefig(out/'figures'/f'{name}.{ext}', dpi=150)
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    color = np.array([m in pareto for m in masks])
    axes[0].scatter(values[:, 2], values[:, 0], c=np.where(color, '#d36c36', '#5297a9'))
    axes[0].set_xlabel('相对治理成本（非人民币）'); axes[0].set_ylabel('最坏情景相对无雨广义成本增加 veh·h')
    axes[1].scatter(values[:, 2], values[:, 1], c=np.where(color, '#d36c36', '#5297a9'))
    axes[1].set_xlabel('相对治理成本（非人民币）'); axes[1].set_ylabel('最坏情景时窗末未完成车次')
    for ax in axes:
        for j, m in enumerate(masks): ax.annotate(str(m), (values[j, 2], values[j, 0 if ax is axes[0] else 1]), fontsize=7)
        ax.grid(alpha=.2)
    fig.suptitle('4处候选、最多3处：NSGA-II与全部15组合核验\n橙色为精确非支配集；未标定方法实验，编号为组合mask')
    save(fig, 'adaptive_pareto')
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), layout='constrained', sharex=True)
    for mask in sorted(set([0, recommendation])):
        p = out/'cases'/f'mask{mask:02d}_rain130_sample2_dt60_traffic_series.csv'
        a = pd.read_csv(p)
        axes[0].plot(a.time_h, a.queue, label=f'mask={mask} 道路点队列')
        axes[0].plot(a.time_h, a.origin_backlog, '--', label=f'mask={mask} 起点等待')
        axes[1].plot(a.time_h, a.completed, label=f'mask={mask} 累计完成')
    axes[0].set_ylabel('带权车次'); axes[1].set_ylabel('带权完成车次'); axes[1].set_xlabel('自2023-09-06 00:00起 小时')
    for ax in axes: ax.legend(); ax.grid(alpha=.2)
    fig.suptitle('1.3倍雨量：跨时段点队列与起点等待\n按起点分层抽样目的地；比例服务、固定路径库，非动态用户均衡')
    save(fig, 'adaptive_queues')
    fig, ax = plt.subplots(figsize=(9, 7), layout='constrained')
    inside = grid['district_weights'] > 0
    im = ax.scatter(x[inside], y[inside], c=np.minimum(peak[inside], .5), s=2, cmap='YlOrRd', vmin=0, vmax=.5)
    for j, footprint in enumerate(site_masks):
        xx = x[footprint].mean(); yy = y[footprint].mean()
        ax.add_patch(plt.Circle((xx, yy), 750, fill=False, color='#176e91' if recommendation & (1 << j) else '#666666'))
        ax.text(xx, yy, f'S{j}', fontsize=10)
    ax.set_aspect('equal'); ax.set_xlabel('UTM 50N 东向 m'); ax.set_ylabel('北向 m')
    fig.colorbar(im, ax=ax, label='无治理各格峰值 m（颜色截于0.5m）')
    ax.set_title('WorldCover分区损失＋D8原型：4处候选位置\n蓝色为推荐组合；圆形排水提升和成本均为研究假设')
    save(fig, 'adaptive_sites')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='configs/longgang_adaptive.yaml')
    parser.add_argument('--landcover', required=True)
    parser.add_argument('--resume')
    parser.add_argument('--reuse-water')
    args = parser.parse_args()
    run(ROOT/args.config, ROOT/args.landcover, ROOT/args.resume if args.resume else None,
        ROOT/args.reuse_water if args.reuse_water else None)
