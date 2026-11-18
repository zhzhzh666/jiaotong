"""Checkpointed PPT-resilience road identification and four-site governance.

Full OD BPR user equilibrium in independent time slices; not dynamic equilibrium.
"""
from pathlib import Path
import argparse
import gc
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(_key, '1')
os.environ.setdefault('MPLBACKEND', 'Agg')

import numpy as np
import pandas as pd
import yaml
from scipy.spatial import cKDTree
from pyproj import Transformer
from uftr.adaptive import road_factors
from uftr.resilience_ppt import BatchedTrafficNetwork, structure_metrics, facility_coverage, ppt_quality, integrate_quality
from uftr.sumo_dynamic import read_nodes
from uftr.sumo_benchmark import ResourceMonitor
from migrate_5090 import sha, read, write, inside, stamp


class Study:
    def __init__(self, root, config_path, resume=None):
        self.root = Path(root).resolve(); self.config_path = inside(self.root, config_path)
        self.cfg = yaml.safe_load(self.config_path.read_text(encoding='utf-8'))
        cfg = self.cfg; self.s = cfg['model']; s = self.s
        if cfg['region'] != 'longgang' or cfg['include_dapeng'] is not False:
            raise ValueError('Longgang excluding Dapeng required')
        if s['interval_seconds'] != 900 or s['intervals'] != 96:
            raise ValueError('PPT production model requires 97 endpoints spanning 24 hours')
        if s['start_interval'] < 0 or not 0 < s['demand_fraction'] <= 1:
            raise ValueError('Invalid time window/demand fraction')
        if s['functional_threshold_minutes'] != [15, 30]:
            raise ValueError('This implementation reports both PPT thresholds: 15/30 minutes')
        if not np.allclose(s['weights'], [.27, .41, .32], rtol=0, atol=1e-12):
            raise ValueError('This PPT implementation fixes weights to 0.27/0.41/0.32')
        self.od_path = inside(self.root, cfg['od_package'])
        self.adaptive = inside(self.root, cfg['adaptive_package'])
        self.surface = inside(self.root, cfg['surface_package'])
        self.screening = inside(self.root, cfg['screening_package'])
        self.poi = inside(self.root, cfg['facilities_package'])
        files = [self.config_path, inside(self.root, cfg['model_reference']),
            self.root/'scripts/run_resilience_4090.py', self.root/'src/uftr/resilience_ppt.py',
            self.root/'src/uftr/assignment.py', self.root/'src/uftr/adaptive.py',
            self.root/'src/uftr/sumo_dynamic.py', self.root/'src/uftr/sumo_benchmark.py',
            self.root/'scripts/migrate_5090.py',
            self.adaptive/'raw/source_edges.parquet', self.adaptive/'raw/candidates.csv',
            self.od_path/'zone_connectors.csv', self.od_path/'zone_population.csv',
            self.od_path/'od_sensitivity_veh_h.npz', self.od_path/'inferred_source_network.graphml',
            self.surface/'raw/routing_grid.npz', self.screening/'critical_road_ranking.csv',
            self.poi/'facilities_wgs84.csv', self.poi/'source.json', self.poi/'overpass_response.json']
        files += sorted((self.root/'src/uftr').glob('*.py'))
        files += [self.root/'scripts/run_longgang_full_benchmark.py', self.root/'scripts/audit_resilience_4090.py']
        masks = cfg['optimization']['masks']
        if len(set(masks)) != len(masks) or 0 not in masks or any(int(m).bit_count() > cfg['optimization']['max_sites'] for m in masks):
            raise ValueError('Unique feasible masks including zero required')
        for mask in masks:
            for scenario in s['scenarios']:
                files.append(self.adaptive/f'cases/mask{mask:02d}_{scenario}_water.npz')
        # Validate data against the previously frozen packages before making a
        # new input manifest. A newly computed hash alone is not validation.
        for package in [self.adaptive, self.od_path, self.surface, self.screening]:
            manifest_path = package/'manifest.json'
            records = {r['path'].replace('\\', '/'): r['sha256'] for r in read(manifest_path)['outputs']}
            for f in files.copy():
                if f.is_relative_to(package):
                    key = f.relative_to(package).as_posix()
                    if key not in records or sha(f) != records[key]: raise ValueError('Frozen package input changed: '+key)
            files.append(manifest_path)
        self.inputs = [{'path': f.relative_to(self.root).as_posix(), 'sha256': sha(f), 'bytes': f.stat().st_size}
                       for f in dict.fromkeys(files)]
        self.fingerprint = hashlib.sha256(json.dumps(self.inputs, sort_keys=True).encode()).hexdigest()
        if resume:
            self.out = inside(self.root, resume)
            if read(self.out/'inputs.json') != self.inputs:
                raise ValueError('Resume requires identical source, model, configuration and frozen inputs')
            for row in read(self.out/'raw_manifest.json'):
                if sha(inside(self.out, row['path'])) != row['sha256']:
                    raise ValueError('Prepared run input changed: '+row['path'])
        else:
            self.out = inside(self.root, cfg['output_root'])/('ppt_'+stamp())
            for d in ['raw', 'states', 'cases', 'provenance', 'figures']:
                (self.out/d).mkdir(parents=True, exist_ok=False)
            write(self.out/'status.json', {'status': 'preparing'})
            write(self.out/'inputs.json', self.inputs)
            (self.out/'config.yaml').write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding='utf-8')
            for f in files[:8]: shutil.copy2(f, self.out/'provenance'/f.name)
            from run_longgang_full_benchmark import hardware
            write(self.out/'hardware.json', hardware())
            (self.out/'python_packages.txt').write_bytes(subprocess.check_output([sys.executable, '-m', 'pip', 'freeze']))
        write(self.out/'study_kind.json', {'kind': 'ppt_resilience', 'source_fingerprint': self.fingerprint,
            'weights': s['weights'], 'rho_seconds': s['rho_seconds'], 'gap_target': s['gap_target'],
            'scope': 'Full OD independent BPR time slices; sampled structural efficiency unless configured all'})
        edges = pd.read_parquet(self.adaptive/'raw/source_edges.parquet')
        if len(edges) != cfg['expected_source_arcs'] or not edges.edge_id.is_unique:
            raise ValueError('Frozen source edge identity/count mismatch')
        self.edges = edges.reset_index(drop=True)
        net_edges = edges.rename(columns={'normal_time_s': 'free_flow_time_s'}).copy()
        net_edges['free_flow_time_s'] = edges.length_m*3.6/edges.speed_kph
        self.network = BatchedTrafficNetwork(net_edges)
        self.structural_mask = edges.depth_feature_position.to_numpy() >= 0
        if s['structure_scope'] == 'full_source_network': self.structural_mask[:] = True
        elif s['structure_scope'] != 'longgang_source_features': raise ValueError('Unknown structural scope')
        if not self.structural_mask.any(): raise ValueError('Empty structural graph')
        self.structure = BatchedTrafficNetwork(net_edges.loc[self.structural_mask].reset_index(drop=True))
        k = s['efficiency_origins']
        rng = np.random.default_rng(cfg['seed'])
        self.eff_origins = self.structure.nodes if k == 'all' else rng.choice(self.structure.nodes, min(int(k), len(self.structure.nodes)), replace=False)
        self.connectors = pd.read_csv(self.od_path/'zone_connectors.csv')
        pop = pd.read_csv(self.od_path/'zone_population.csv')
        self.origins = self.connectors.merge(pop[['zone_id', 'population_estimate']], how='left', on='zone_id', validate='one_to_one')
        self.origins['population_estimate'] = self.origins.population_estimate.fillna(0)
        self.origins['node_id'] = self.origins.node_id.fillna(-1).astype(np.int64)
        self.origins['access_time_s'] = self.origins.connector_distance_m.fillna(0)*3.6/s['connector_speed_kph']
        matrix_file = np.load(self.od_path/'od_sensitivity_veh_h.npz')
        if not np.array_equal(matrix_file['zone_ids'].astype(str), self.origins.zone_id.astype(str)):
            raise ValueError('Matrix and population/connector order differ')
        if len(self.origins) != cfg['expected_zones']: raise ValueError('Unexpected OD dimension')
        self.ods = {}
        for period in ['offpeak', 'morning_peak', 'evening_peak']:
            matrix = matrix_file['base__'+period]*s['demand_fraction']
            i, j = np.nonzero(matrix)
            self.ods[period] = pd.DataFrame({'origin_node': self.origins.node_id.to_numpy()[i],
                'destination_node': self.origins.node_id.to_numpy()[j], 'flow_veh_h': matrix[i, j],
                'route_status': np.where(i == j, 'intrazonal_not_graph_loaded', 'network')})
        grid = np.load(self.surface/'raw/routing_grid.npz')
        self.features = grid['source_feature_positions'].astype(int)
        self.feature_lookup = {int(f): j for j, f in enumerate(self.features)}
        self.columns = np.array([self.feature_lookup.get(int(f), -1) for f in edges.depth_feature_position], int)
        self.facilities = self.prepare_facilities()
        self.selected = pd.read_csv(self.screening/'critical_road_ranking.csv', dtype={'osm_id': str}).head(cfg['identification']['candidate_limit']).copy()
        if self.selected.empty or not set(self.selected.source_feature_position) <= set(self.features):
            raise ValueError('Invalid diagnostic shortlist')
        self.sites = pd.read_csv(self.adaptive/'raw/candidates.csv').sort_values('site')
        if self.sites.site.tolist() != [0, 1, 2, 3]: raise ValueError('Four frozen treatment sites required')
        self.origins.to_csv(self.out/'raw/population_origins.csv', index=False)
        pd.DataFrame({'node_id': self.eff_origins}).to_csv(self.out/'raw/efficiency_origins.csv', index=False)
        self.selected.to_csv(self.out/'raw/diagnostic_shortlist.csv', index=False)
        self.edges[['edge_id', 'u', 'v', 'depth_feature_position']].to_parquet(self.out/'raw/source_edge_identity.parquet', index=False)
        write(self.out/'raw_manifest.json', [{'path': p.relative_to(self.out).as_posix(), 'sha256': sha(p)}
            for p in sorted((self.out/'raw').glob('*'))])
        write(self.out/'preflight.json', {'source_arcs': len(edges), 'source_nodes': len(self.network.nodes),
            'structural_arcs': int(self.structural_mask.sum()), 'structural_nodes': len(self.structure.nodes),
            'efficiency_origin_count': len(self.eff_origins), 'efficiency_is_sampled': len(self.eff_origins) < len(self.structure.nodes),
            'population_denominator': float(self.origins.population_estimate.sum()),
            'facility_objects': self.facilities.groupby('category').size().to_dict(),
            'connected_facility_objects': self.facilities.loc[self.facilities.connected].groupby('category').size().to_dict(),
            'od_zones': len(self.origins), 'candidate_roads': len(self.selected), 'solver_uses_cuda': False})
        self.dry = {}; self.state_calls = 0; self.state_cache_hits = 0

    def prepare_facilities(self):
        target = self.out/'raw/connected_facilities.csv'
        if target.is_file():
            return pd.read_csv(target)
        coordinates = read_nodes(self.od_path/'inferred_source_network.graphml')
        ids = np.array([n for n in self.network.nodes if int(n) in coordinates])
        xy = np.array([coordinates[int(n)] for n in ids])
        transform = Transformer.from_crs(4326, 32650, always_xy=True)
        x, y = transform.transform(xy[:, 0], xy[:, 1]); tree = cKDTree(np.column_stack([x, y]))
        frame = pd.read_csv(self.poi/'facilities_wgs84.csv')
        px, py = transform.transform(frame.longitude.to_numpy(), frame.latitude.to_numpy())
        distance, index = tree.query(np.column_stack([px, py]))
        frame['node_id'] = ids[index]; frame['connector_distance_m'] = distance
        frame['connected'] = distance <= self.s['facility_max_snap_m']
        frame['access_time_s'] = distance*3.6/self.s['connector_speed_kph']
        for c in ['hospital', 'fire_station']:
            if not ((frame.category == c) & frame.connected).any():
                raise ValueError('No connected OSM '+c+'; facility reference must be corrected')
        frame.to_csv(target, index=False, encoding='utf-8-sig')
        return frame

    def period(self, seconds):
        hour = ((self.s['start_interval']*900+seconds)/3600) % 24
        return 'morning_peak' if 7 <= hour < 10 else ('evening_peak' if 17 <= hour < 20 else 'offpeak')

    def state(self, depth, period):
        depth = np.asarray(depth, dtype='<f4')
        key = hashlib.sha256(self.fingerprint.encode()+period.encode()+depth.tobytes()).hexdigest()[:32]
        target = self.out/'states'/key
        self.state_calls += 1
        if target.with_suffix('.json').is_file():
            metric = read(target.with_suffix('.json'))
            if metric['source_fingerprint'] != self.fingerprint or not metric['converged']:
                raise ValueError('Invalid state checkpoint')
            for r in metric['artifacts']:
                if sha(self.out/r['path']) != r['sha256']: raise ValueError('State artifact changed')
            self.state_cache_hits += 1
            return metric
        started = time.perf_counter()
        h = np.full(len(self.edges), np.nan); known = self.columns >= 0
        h[known] = depth[self.columns[known]]
        speed, factor, _ = road_factors(h, self.edges.speed_kph.to_numpy(), self.edges.capacity_loss.to_numpy(), self.s['closure_depth_m'])
        closed = factor <= 0
        t0 = self.edges.length_m.to_numpy()*3.6/np.where(closed, self.edges.speed_kph.to_numpy(), speed)
        capacity = self.edges.capacity_veh_h.to_numpy()*factor
        print('STATE', key[:10], period, 'closed', int(closed.sum()), flush=True)
        result = self.network.solve(self.ods[period], t0=t0, capacity=capacity, closed=closed,
            tolerance=self.s['gap_target'], max_iterations=self.s['max_iterations'],
            alpha=self.s['bpr_alpha'], beta=self.s['bpr_beta'])
        trace = target.with_suffix('.csv'); result.trace.to_csv(trace, index=False)
        if not result.converged or result.node_balance_max_error > max(1e-6, result.total_veh_h*1e-8):
            write(target.with_suffix('.failed.json'), {'relative_gap': result.relative_gap,
                'node_balance_error': result.node_balance_max_error, 'converged': result.converged})
            raise RuntimeError('UE state did not pass convergence/conservation; trace retained: '+key)
        metric = structure_metrics(self.structure, result.time[self.structural_mask], closed[self.structural_mask],
            self.eff_origins, self.s['efficiency_batch_size'])
        metric.update(facility_coverage(self.network, result.time, closed, self.origins, self.facilities))
        travel = float(np.dot(result.flow[~closed], result.time[~closed]))
        metric.update(cost_veh_s_h=travel+self.s['rho_seconds']*result.unserved_veh_h,
            travel_veh_s_h=travel, served_veh_h=result.served_veh_h, unserved_veh_h=result.unserved_veh_h,
            intrazonal_veh_h=result.intrazonal_veh_h, total_veh_h=result.total_veh_h,
            relative_gap=result.relative_gap, converged=result.converged,
            node_balance_error=result.node_balance_max_error, state_key=key, period=period,
            source_fingerprint=self.fingerprint, wall_seconds=time.perf_counter()-started)
        artifacts = [trace]
        if self.s['save_edge_arrays']:
            arrays = target.with_suffix('.npz')
            np.savez_compressed(arrays, depth_m=h, flow=result.flow, time_s=result.time, t0_s=t0,
                capacity_veh_h=capacity, closed=closed, od_served=result.od_served, od_cost_s=result.od_cost_s)
            artifacts.append(arrays)
        metric['artifacts'] = [{'path': p.relative_to(self.out).as_posix(), 'sha256': sha(p)} for p in artifacts]
        pending = target.with_suffix('.json.partial')
        write(pending, metric); pending.replace(target.with_suffix('.json'))
        print('STATE_DONE', key[:10], round(metric['wall_seconds'], 3), 's gap', result.relative_gap, flush=True)
        return metric

    def dry_state(self, period):
        if period not in self.dry: self.dry[period] = self.state(np.zeros(len(self.features), np.float32), period)
        return self.dry[period]

    def water(self, mask, scenario):
        path = self.adaptive/f'cases/mask{mask:02d}_{scenario}_water.npz'
        with np.load(path) as loaded: data = loaded['depth_m']
        start = self.s['start_interval']; stop = start+self.s['intervals']+1
        if data.shape[1] != len(self.features) or len(data) < stop: raise ValueError('Water window/dimension mismatch')
        return data[start:stop].copy()

    def case(self, mask, scenario, feature=None):
        name = f'mask{mask:02d}_{scenario}'+(f'_restore{feature}' if feature is not None else '')
        folder = self.out/'cases'/name; folder.mkdir(exist_ok=True)
        water = self.water(mask, scenario)
        if feature is not None: water[:, self.feature_lookup[int(feature)]] = 0
        target = folder/'curve.csv'
        # Reuse only complete endpoint rows whose state checkpoints still validate.
        rows = []
        for k, depth in enumerate(water):
            seconds = k*self.s['interval_seconds']; period = self.period(seconds)
            base = self.dry_state(period); metric = self.state(depth, period)
            quality = ppt_quality(metric, base, self.s['weights'])
            row = {'time_s': seconds, 'state_key': metric['state_key'], 'dry_state_key': base['state_key'],
                   'period': period, **quality, 'relative_gap': metric['relative_gap'],
                   'unserved_veh_h': metric['unserved_veh_h'], 'cost_veh_s_h': metric['cost_veh_s_h']}
            rows.append(row)
            if k % 4 == 0 or k == len(water)-1:
                pd.DataFrame(rows).to_csv(target, index=False)
                print('CURVE', name, k, '/', len(water)-1, flush=True)
        curve = pd.DataFrame(rows)
        summary = {'case': name, 'mask': int(mask), 'scenario': scenario, 'restored_feature': feature,
            'R': integrate_quality(curve.time_s, curve.Q), 'R15': integrate_quality(curve.time_s,
                .27*curve.Qs+.41*curve.Qp+.32*curve.Qf15),
            'R30': integrate_quality(curve.time_s, .27*curve.Qs+.41*curve.Qp+.32*curve.Qf30),
            'minimum_Q': float(curve.Q.min()), 'endpoint_count': len(curve),
            'Q_above_one_endpoints': int(curve.above_one.sum()),
            'curve_sha256': sha(target), 'source_fingerprint': self.fingerprint}
        write(folder/'summary.json', summary)
        return summary

    def identify(self):
        rows = []
        baselines = {s: self.case(0, s) for s in self.s['scenarios']}
        for feature in self.selected.source_feature_position:
            gains = []
            for scenario in self.s['scenarios']:
                value = self.case(0, scenario, int(feature))
                gains.append(value['R']-baselines[scenario]['R'])
            original = self.selected.loc[self.selected.source_feature_position == feature].iloc[0]
            rows.append({'source_feature_position': int(feature), 'osm_id': str(original.osm_id),
                **{k: original[k] for k in ['source_feature_id', 'road_class', 'road_label'] if k in original.index},
                'mean_delta_R': float(np.mean(gains)), 'minimum_delta_R': float(np.min(gains)),
                **{s+'_delta_R': v for s, v in zip(self.s['scenarios'], gains)}})
            ranking = pd.DataFrame(rows).sort_values(['mean_delta_R', 'source_feature_position'], ascending=[False, True])
            ranking.to_csv(self.out/'critical_road_R_ranking.csv', index=False, encoding='utf-8-sig')
        ranking.insert(0, 'rank', np.arange(1, len(ranking)+1))
        ranking.to_csv(self.out/'critical_road_R_ranking.csv', index=False, encoding='utf-8-sig')
        return ranking

    def optimize(self):
        rows = []
        for mask in self.cfg['optimization']['masks']:
            values = [self.case(mask, s)['R'] for s in self.s['scenarios']]
            rows.append({'mask': int(mask), 'worst_R': min(values), 'mean_R': float(np.mean(values)),
                'relative_cost': float(sum(r.relative_cost for r in self.sites.itertuples() if mask & (1 << r.site))),
                'selected_sites': ','.join(f'S{j}' for j in range(4) if mask & (1 << j)),
                **{s+'_R': v for s, v in zip(self.s['scenarios'], values)}})
            pd.DataFrame(rows).to_csv(self.out/'governance_R_combinations.csv', index=False, encoding='utf-8-sig')
        table = pd.DataFrame(rows); recommendations = []
        for budget in self.cfg['optimization']['budgets']:
            feasible = table.loc[table.relative_cost <= budget+1e-9]
            best = feasible.sort_values(['worst_R', 'mean_R', 'relative_cost', 'mask'], ascending=[False, False, True, True]).iloc[0]
            recommendations.append({'budget': budget, **best.to_dict()})
        pd.DataFrame(recommendations).to_csv(self.out/'budget_R_recommendations.csv', index=False, encoding='utf-8-sig')
        lookup = table.set_index('mask'); costs = self.sites.relative_cost.to_numpy()
        comparisons = []; greedy_trace = []
        for budget in self.cfg['optimization']['budgets']:
            def feasible(mask):
                return mask in lookup.index and sum(costs[j] for j in range(4) if mask & (1 << j)) <= budget+1e-9
            def fixed(order):
                mask = 0
                for j in order:
                    candidate = mask | (1 << int(j))
                    if feasible(candidate): mask = candidate
                return mask
            best = next(int(r['mask']) for r in recommendations if r['budget'] == budget)
            selected = [('no_intervention', 0, None), ('exact_enumeration', best, None)]
            selected.append(('depth_first', fixed(self.sites.sort_values(['baseline_peak_m', 'site'], ascending=[False, True]).site), None))
            current = 0
            while True:
                options = [j for j in range(4) if not current & (1 << j) and feasible(current | (1 << j))]
                if not options: break
                gains = [(lookup.loc[current | (1 << j), 'worst_R']-lookup.loc[current, 'worst_R'])/costs[j] for j in options]
                chosen = options[int(np.argmax(gains))]
                if max(gains) <= 1e-12: break
                updated = current | (1 << chosen)
                greedy_trace.append({'budget': budget, 'before_mask': current, 'after_mask': updated,
                    'added_site': chosen, 'delta_worst_R': float(lookup.loc[updated, 'worst_R']-lookup.loc[current, 'worst_R'])})
                current = updated
            selected.append(('marginal_greedy', current, None))
            for seed in self.cfg['optimization']['random_seeds']:
                selected.append(('random', fixed(np.random.default_rng(seed).permutation(4)), seed))
            for strategy, mask, seed in selected:
                comparisons.append({'budget': budget, 'strategy': strategy, 'seed': seed,
                    **lookup.loc[mask].to_dict(), 'mask': mask,
                    'delta_worst_R': float(lookup.loc[mask, 'worst_R']-lookup.loc[0, 'worst_R']),
                    'R_gap_to_exact': float(lookup.loc[best, 'worst_R']-lookup.loc[mask, 'worst_R'])})
        pd.DataFrame(comparisons).to_csv(self.out/'governance_R_strategy_comparison.csv', index=False, encoding='utf-8-sig')
        pd.DataFrame(greedy_trace, columns=['budget', 'before_mask', 'after_mask', 'added_site', 'delta_worst_R']).to_csv(self.out/'greedy_R_trace.csv', index=False)
        return table

    def execute(self, phase):
        write(self.out/'status.json', {'status': 'running', 'phase': phase})
        if phase == 'preflight':
            pass
        elif phase == 'pilot':
            self.dry_state('offpeak')
            data = self.water(0, self.s['scenarios'][-1]); peak = int(np.argmax((data >= self.s['closure_depth_m']).sum(axis=1)))
            self.state(data[peak], self.period(peak*900))
            times = [read(f)['wall_seconds'] for f in (self.out/'states').glob('*.json') if not f.name.endswith('.failed.json')]
            endpoint_calls = (len(self.selected)+len(self.cfg['optimization']['masks']))*len(self.s['scenarios'])*97
            write(self.out/'pilot_budget.json', {'measured_state_wall_seconds': times,
                'distinct_case_endpoints_before_state_cache': endpoint_calls,
                'uncached_all_states_hours_if_mean_pilot_cost': endpoint_calls*np.mean(times)/3600,
                'limitation': 'Conditional forecast only. Cache hits, high congestion and convergence iterations can change cost substantially.'})
        else:
            if phase == 'baseline':
                for scenario in self.s['scenarios']: self.case(0, scenario)
            if phase in ['identify', 'all']: self.identify()
            if phase in ['optimize', 'all']: self.optimize()
        for r in self.inputs:
            if sha(self.root/r['path']) != r['sha256']: raise ValueError('Input changed while calculating: '+r['path'])
        self.write_report(phase)
        self.figures()
        from audit_resilience_4090 import audit
        audit(self.root, self.out.relative_to(self.root).as_posix(), self.out/'independent_audit.json')
        write(self.out/'status.json', {'status': 'complete', 'phase': phase, 'study_kind': 'ppt_resilience',
            'complete_full_study': phase == 'all', 'state_calls': self.state_calls, 'state_cache_hits': self.state_cache_hits})

    def figures(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        def save(fig, name):
            for suffix in ['png', 'svg']: fig.savefig(self.out/'figures'/(name+'.'+suffix), dpi=160)
            plt.close(fig)
        curves = [self.out/'cases'/f'mask00_{s}'/'curve.csv' for s in self.s['scenarios']]
        curves = [p for p in curves if p.is_file()]
        if curves:
            fig, ax = plt.subplots(figsize=(9, 4.5), layout='constrained')
            for f in sorted(curves):
                frame = pd.read_csv(f); ax.plot(frame.time_s/3600, frame.Q, label=f.parent.name)
            ax.axhline(1, color='#777', linestyle='--', label='Dry reference')
            ax.set(xlabel='Hours in selected 24h window', ylabel='Q(t)', title='PPT resilience | untreated rainfall cases')
            ax.legend(); ax.grid(alpha=.2); save(fig, 'resilience_curves')
        ranking = self.out/'critical_road_R_ranking.csv'
        if ranking.is_file():
            frame = pd.read_csv(ranking, dtype={'osm_id': str})
            fig, ax = plt.subplots(figsize=(9, 5), layout='constrained')
            ax.barh(frame.osm_id.iloc[::-1], frame.mean_delta_R.iloc[::-1], color='#167c92')
            ax.set(xlabel='Mean delta R across rainfall cases', ylabel='OSM source object ID',
                   title='Candidate-road dry restoration diagnostic')
            save(fig, 'critical_road_R_ranking')
        path = self.out/'budget_R_recommendations.csv'
        if path.is_file():
            frame = pd.read_csv(path)
            fig, ax = plt.subplots(figsize=(8, 4.5), layout='constrained')
            ax.plot(frame.budget, frame.worst_R, marker='o')
            ax.set(xlabel='Relative budget (not currency)', ylabel='Minimum 24h R across rainfalls',
                   title='Exact optimum among four frozen treatment sites')
            ax.grid(alpha=.2); save(fig, 'budget_R_frontier')

    def write_report(self, phase):
        text = f'''# PPT模型：龙岗韧性、关键道路与治理\n\n本次完成阶段：{phase}。\n\nQ=0.27Qs+0.41Qp+0.32Qf；Qs为可用边、弱/强连通比例及时间效率的基准比值均值；Qp=C0/C，C=Σxₑtₑ+{self.s["rho_seconds"]}D未服务。Qf为医院/消防两类15分钟归一化覆盖率的均值与30分钟对应均值再平均；另存R15/R30。R按97个端点梯形积分/24小时。\n\n路网分配使用完整源图承载龙岗完整OD的{self.s["demand_fraction"]:.1%}比例需求；区内短途未道路加载，单独记账，不额外加入PPT未列的300秒成本。结构指标仅在冻结龙岗源道路及其固定节点上计算。默认时间效率采用固定{len(self.eff_origins)}起点估计，因此R是该抽样设置下的估计；设置efficiency_origins: all可算全起点。\n\n道路排名仅针对既有静态筛查的{len(self.selected)}候选，按三档雨量的平均ΔR排序；单道路水深归零是诊断反事实，不是可施工排水效果。治理仅在四处冻结空间候选最多三处的15组合内穷举，按三雨型最小R最大选择，相对预算不是人民币。治理重新计算BPR交通指标，使用已逐组合重算的冻结积水。独立时片不传递队列，不称动态用户均衡。\n\n医院/消防来自公开OSM，完整性、运营和道路入口未经实测核实；中心点用{self.s["facility_max_snap_m"]}m限距接入，全部龙岗人口含未接入分区保留在覆盖分母。基准覆盖率为0时停止，不悄悄改权重。Q/R超过1会原值报告，不强行截断。权重直接采用PPT给值，未在当前样本重新估计熵权。\n\ncheckpoint按完整状态保存；同一源码/配置/数据可恢复，未收敛状态不作为完成结果。修改配置必须新建run。结果CSV、原始状态数组、收敛轨迹、源码和输入SHA一起回传。全部数据与参数未经实测标定。\n'''
        (self.out/'REPORT.md').write_text(text, encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default='configs/longgang_resilience_4090.yaml')
    p.add_argument('--resume'); p.add_argument('--phase', choices=['preflight', 'pilot', 'baseline', 'identify', 'optimize', 'all'], default='pilot')
    args = p.parse_args()
    study = Study(ROOT, args.config, args.resume)
    relative = study.out.relative_to(ROOT).as_posix()
    (ROOT/'results/resilience_runs').mkdir(parents=True, exist_ok=True)
    (ROOT/'results/resilience_runs/LATEST.txt').write_text(relative+'\n', encoding='utf-8')
    print('RUN', relative, flush=True)
    monitor = ResourceMonitor(study.out/('resources_'+stamp()+'.csv'), 1).start()
    try: study.execute(args.phase)
    except BaseException:
        write(study.out/'status.json', {'status': 'failed', 'phase': args.phase, 'traceback': traceback.format_exc()})
        raise
    finally:
        monitor.close(); write(study.out/'resources_last_summary.json', monitor.summary())
    print('DONE', relative, flush=True)


if __name__ == '__main__': main()
