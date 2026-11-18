"""Independent array/ledger/arithmetic audit; not field validation or new UE."""
from pathlib import Path
import argparse
import math
import numpy as np
import pandas as pd
import yaml
from migrate_5090 import read, write, sha, inside

ROOT = Path(__file__).resolve().parents[1]


def close(a, b, name, rtol=1e-7, atol=1e-7):
    if not np.allclose(a, b, rtol=rtol, atol=atol, equal_nan=False):
        raise ValueError('Audit mismatch: '+name)


def audit(root, run, output=None):
    root = Path(root).resolve(); run = inside(root, run)
    cfg = yaml.safe_load((run/'config.yaml').read_text(encoding='utf-8')); s = cfg['model']
    for row in read(run/'inputs.json'):
        if sha(inside(root, row['path'])) != row['sha256']: raise ValueError('Input SHA mismatch: '+row['path'])
    for row in read(run/'raw_manifest.json'):
        if sha(inside(run, row['path'])) != row['sha256']: raise ValueError('Prepared input SHA mismatch')
    edges = pd.read_parquet(inside(root, cfg['adaptive_package'])/'raw/source_edges.parquet')
    origins = pd.read_csv(run/'raw/population_origins.csv')
    matrices = np.load(inside(root, cfg['od_package'])/'od_sensitivity_veh_h.npz')
    nodes, ui = np.unique(np.r_[edges.u, edges.v], return_inverse=True)
    u, v = ui[:len(edges)], ui[len(edges):]; node_index = {n: i for i, n in enumerate(nodes)}
    ods = {}
    for period in ['offpeak', 'morning_peak', 'evening_peak']:
        matrix = matrices['base__'+period]*s['demand_fraction']; i, j = np.nonzero(matrix)
        ods[period] = (matrix[i, j], origins.node_id.to_numpy()[i], origins.node_id.to_numpy()[j], i == j)
    states = {}; arrays_checked = 0
    for f in sorted((run/'states').glob('*.json')):
        if f.name.endswith('.failed.json'): continue
        m = read(f); states[m['state_key']] = m
        if not m['converged'] or not 0 <= m['relative_gap'] <= s['gap_target']+1e-12:
            raise ValueError('Unconverged state')
        close(m['total_veh_h'], m['served_veh_h']+m['unserved_veh_h']+m['intrazonal_veh_h'], 'OD ledger')
        close(m['cost_veh_s_h'], m['travel_veh_s_h']+s['rho_seconds']*m['unserved_veh_h'], 'PPT cost')
        for artifact in m['artifacts']:
            if sha(inside(run, artifact['path'])) != artifact['sha256']: raise ValueError('State artifact SHA mismatch')
        array_path = f.with_suffix('.npz')
        if not array_path.is_file():
            if s['save_edge_arrays']: raise ValueError('Missing edge arrays')
            continue
        with np.load(array_path) as a:
            x = a['flow']; times = a['time_s']; cap = a['capacity_veh_h']; t0 = a['t0_s']; closed = a['closed']
            if len(x) != len(edges) or not np.isfinite(x).all() or (x < -1e-8).any() or (cap[~closed] <= 0).any():
                raise ValueError('Invalid edge arrays')
            close(x[closed], 0, 'closed-edge flow'); close(cap[closed], 0, 'closed-edge capacity')
            close(times[~closed], t0[~closed]*(1+s['bpr_alpha']*(x[~closed]/cap[~closed])**s['bpr_beta']), 'BPR')
            if not np.isinf(times[closed]).all(): raise ValueError('Closed-edge times must be infinite')
            close(np.dot(x[~closed], times[~closed]), m['travel_veh_s_h'], 'travel cost')
            q, origin, destination, intra = ods[m['period']]; served = a['od_served']; shortest = a['od_cost_s']
            if len(q) != len(served) or (served & intra).any(): raise ValueError('Invalid OD array order/ledger')
            close(q[served].sum(), m['served_veh_h'], 'served demand')
            close(q[intra].sum(), m['intrazonal_veh_h'], 'intrazonal demand')
            close(q[~served & ~intra].sum(), m['unserved_veh_h'], 'unserved demand')
            actual = np.bincount(u, weights=x, minlength=len(nodes))-np.bincount(v, weights=x, minlength=len(nodes))
            oi = [node_index[n] for n in origin[served]]; di = [node_index[n] for n in destination[served]]
            expected = np.bincount(oi, weights=q[served], minlength=len(nodes))-np.bincount(di, weights=q[served], minlength=len(nodes))
            residual = np.abs(actual-expected).max(initial=0)
            if residual > max(1e-6, m['total_veh_h']*1e-8): raise ValueError('Node conservation failed')
            close(residual, m['node_balance_error'], 'recorded node residual', atol=1e-6)
            total = m['travel_veh_s_h']; lower = float(np.dot(q[served], shortest[served]))
            close(max(0, (total-lower)/total) if total else 0, m['relative_gap'], 'gap using recorded shortest costs', atol=1e-8)
            if 'depth_m' in a:
                h = a['depth_m']; w = np.where(np.isfinite(h), h, 0)*1000
                expected_closed = np.isfinite(h) & (h >= s['closure_depth_m'])
                close(closed, expected_closed, 'depth closure')
                speed = np.where(w == 0, edges.speed_kph, np.minimum(edges.speed_kph, np.maximum(0, .0009*w*w-.5529*w+86.9448)))
                speed = np.where(closed, edges.speed_kph, speed)
                close(t0, edges.length_m*3.6/speed, 'depth free-flow time')
                factor = np.where(closed, 0, np.maximum(.2, 1-edges.capacity_loss*w/(s['closure_depth_m']*1000)))
                close(cap, edges.capacity_veh_h*factor, 'depth capacity')
            arrays_checked += 1
    summaries = {}; skeys = ['available_edge_fraction', 'weak_fraction', 'strong_fraction', 'time_efficiency']
    for f in sorted((run/'cases').glob('*/summary.json')):
        obj = read(f); curve_file = f.parent/'curve.csv'
        if sha(curve_file) != obj['curve_sha256']: raise ValueError('Curve SHA mismatch')
        frame = pd.read_csv(curve_file); close(frame.time_s, np.arange(97)*900, 'endpoint times')
        for row in frame.itertuples():
            wet = states[row.state_key]; dry = states[row.dry_state_key]
            qs = np.mean([wet[k]/dry[k] for k in skeys]); qp = dry['cost_veh_s_h']/wet['cost_veh_s_h']
            f15, f30 = [np.mean([wet[f'{c}_{t}min']/dry[f'{c}_{t}min'] for c in ['hospital', 'fire_station']]) for t in [15, 30]]
            close([row.Qs, row.Qp, row.Qf15, row.Qf30, row.Qf], [qs, qp, f15, f30, (f15+f30)/2], 'Q components')
            close(row.Q, np.dot(s['weights'], [qs, qp, (f15+f30)/2]), 'weighted Q')
        for key, q in [('R', frame.Q), ('R15', .27*frame.Qs+.41*frame.Qp+.32*frame.Qf15), ('R30', .27*frame.Qs+.41*frame.Qp+.32*frame.Qf30)]:
            close(obj[key], np.sum((np.asarray(q)[:-1]+np.asarray(q)[1:])*.5*900)/86400, key)
        summaries[f.parent.name] = obj
    ranking = run/'critical_road_R_ranking.csv'
    if ranking.is_file():
        frame = pd.read_csv(ranking)
        for r in frame.itertuples():
            gains = [summaries[f'mask00_{c}_restore{r.source_feature_position}']['R']-summaries[f'mask00_{c}']['R'] for c in s['scenarios']]
            close(r.mean_delta_R, np.mean(gains), 'road mean delta R')
            close(r.minimum_delta_R, min(gains), 'road minimum delta R')
        if not frame.mean_delta_R.is_monotonic_decreasing: raise ValueError('Invalid road ranking order')
    combo_path = run/'governance_R_combinations.csv'
    if combo_path.is_file():
        table = pd.read_csv(combo_path); sites = pd.read_csv(inside(root, cfg['adaptive_package'])/'raw/candidates.csv')
        if set(table['mask']) != set(cfg['optimization']['masks']): raise ValueError('Incomplete governance combinations')
        for r in table.itertuples():
            values = [summaries[f'mask{r.mask:02d}_{c}']['R'] for c in s['scenarios']]
            close(r.worst_R, min(values), 'combination worst R'); close(r.mean_R, np.mean(values), 'combination mean R')
            close(r.relative_cost, sum(p.relative_cost for p in sites.itertuples() if r.mask & (1 << p.site)), 'combination budget')
        for r in pd.read_csv(run/'budget_R_recommendations.csv').itertuples():
            feasible = table.loc[table.relative_cost <= r.budget+1e-9]
            best = feasible.sort_values(['worst_R', 'mean_R', 'relative_cost', 'mask'], ascending=[False, False, True, True]).iloc[0]
            if r.mask != best['mask']: raise ValueError('Budget recommendation is not exact optimum')
    result = {'status': 'passed', 'states_checked': len(states), 'state_arrays_checked': arrays_checked,
        'curves_checked': len(summaries), 'scope': 'SHA, BPR, depth response, OD/node ledgers, recorded-gap arithmetic, Q/R, candidate delta R and budget optimum.',
        'limits': 'No new shortest-path solve, structural efficiency recalculation, field calibration or OSM completeness validation.'}
    if output is not None: write(output, result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--run', required=True); args = p.parse_args()
    print(audit(args.root, args.run, inside(args.root, args.run)/'independent_audit.json'))


if __name__ == '__main__': main()
