"""Measured routing/control probes plus explicitly conditional future run budgets.

Only the dry baseline is a full traffic run. Probes do not establish wet runtime
or dynamic-assignment convergence, and forecast ranges are not confidence bounds.
"""
from pathlib import Path
import argparse
import json
import subprocess
import time
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import yaml
from uftr.adaptive import road_factors
from uftr.sumo_dynamic import write_json
from uftr.sumo_run import sumo_binary

ROOT = Path(__file__).resolve().parents[1]


def run(out):
    import traci
    cfg = yaml.safe_load((out/'config.yaml').read_text(encoding='utf-8'))
    result = json.loads((out/'cases/dry/result.json').read_text(encoding='utf-8'))
    prep = json.loads((out/'preparation.json').read_text(encoding='utf-8'))
    folder = out/'budget_probes'; folder.mkdir(exist_ok=False)
    local = pd.read_csv(out/'raw/source_sumo_mapping.csv')
    plan = pd.read_csv(out/'raw/departure_plan.csv')
    valid = plan.loc[plan.valid]
    network = out/'raw/network.net.xml'
    command = [str(sumo_binary('sumo')), '-n', str(network), '-r', str(out/'raw/types.rou.xml'),
               '--no-step-log', 'true', '--duration-log.disable', 'true', '--time-to-teleport', '-1']
    traci.start(command, label='whole_longgang_budget', stdout=subprocess.DEVNULL)
    conn = traci.getConnection('whole_longgang_budget')
    samples = []; control_wall = []
    try:
        indices = np.linspace(0, len(local)-1, min(1000, len(local)), dtype=int)
        for row in local.iloc[indices].itertuples():
            started = time.perf_counter()
            conn.edge.setAllowed(row.edge_id, ['passenger'])
            conn.edge.setMaxSpeed(row.edge_id, row.speed_kph/3.6)
            conn.edge.adaptTraveltime(row.edge_id, row.length_m*3.6/row.speed_kph)
            control_wall.append((time.perf_counter()-started)/3)
        positions = np.linspace(0, len(valid)-1, min(128, len(valid)), dtype=int)
        for row in valid.iloc[positions].itertuples():
            path = row.normal_route.split()
            started = time.perf_counter()
            route = conn.simulation.findRoute(path[0], path[-1], vType='car', depart=0).edges
            samples.append({'source': path[0], 'target': path[-1], 'wall_seconds': time.perf_counter()-started,
                            'route_edges': len(route), 'reachable': bool(route)})
    finally:
        conn.close()
    pd.DataFrame(samples).to_csv(folder/'route_queries.csv', index=False)
    pd.DataFrame({'wall_seconds_per_command': control_wall}).to_csv(folder/'control_commands.csv', index=False)
    controls = {}
    water = np.load(out/'raw/road_states.npz')
    for key in ['baseline', 'governed']:
        speeds, factors, _ = road_factors(water[key], local.speed_kph.to_numpy()[None, :],
            local.capacity_loss.to_numpy()[None, :], cfg['simulation']['closure_depth_m'])
        updates = len(speeds)-1
        changed = len(local)+sum(int(np.count_nonzero((speeds[k] != speeds[k-1]) | (factors[k] != factors[k-1])))
                                for k in range(1, updates))
        # Two permission/speed commands per changed edge; one travel-time write
        # per edge per flood update in the archived full controller.
        commands = 2*changed+updates*len(local)
        controls[key] = {'changed_edge_updates': changed, 'commands': commands,
                         'estimated_wall_seconds': commands*float(np.mean(control_wall))}
    # Measure one complete time-dependent path-refresh pass on the same trips.
    routes = ET.Element('routes')
    ET.SubElement(routes, 'vType', id='car', vClass='passenger')
    for row in valid.itertuples():
        path = row.normal_route.split()
        ET.SubElement(routes, 'trip', id=row.vehicle_id, type='car', depart=str(row.depart_s),
                      **{'from': path[0], 'to': path[-1]})
    ET.ElementTree(routes).write(folder/'whole_demand.trips.xml', encoding='utf-8', xml_declaration=True)
    command = [str(sumo_binary('duarouter')), '-n', str(network), '-r', str(folder/'whole_demand.trips.xml'),
               '-w', str(out/'cases/dry/edge_costs.xml.gz'), '-o', str(folder/'refreshed.rou.xml.gz'),
               '--routing-algorithm', 'dijkstra', '--bulk-routing', 'true', '--seed', str(cfg['seed']),
               '--no-step-log', 'true']
    write_json(folder/'duarouter_command.json', command)
    started = time.perf_counter()
    with (folder/'duarouter.log').open('w', encoding='utf-8') as log:
        completed = subprocess.run(command, stdout=log, stderr=log, timeout=1800)
    router_wall = time.perf_counter()-started
    if completed.returncode:
        raise RuntimeError('duarouter budget probe failed; see retained log')
    series = pd.read_csv(out/'cases/dry/traffic_series.csv')
    slots = series.loc[(series.time_s % cfg['simulation']['route_seconds'] == 0) &
                       (series.time_s < cfg['simulation']['duration_seconds'])]
    dry_active_checks = int(slots.running.sum())
    conservative_active_checks = len(valid)*(cfg['simulation']['duration_seconds']//cfg['simulation']['route_seconds']-1)
    query_mean = float(np.mean([r['wall_seconds'] for r in samples]))
    measured_loop = result['wall_seconds']
    one_case = measured_loop+result['sumo_startup_wall_seconds']
    preparation = prep['total_wall_seconds']
    wet_controls = 2*(controls['baseline']['estimated_wall_seconds']+controls['governed']['estimated_wall_seconds'])
    five_nominal = preparation+5*one_case+wet_controls+2*dry_active_checks*query_mean
    five_stress = preparation+10*one_case+wet_controls+2*conservative_active_checks*query_mean
    iterations = []
    for n in [10, 20, 30, 50]:
        nominal = preparation+n*(one_case+router_wall)
        contingency = preparation+n*(2*one_case+router_wall)
        iterations.append({'iterations': n, 'nominal_seconds': nominal, 'contingency_seconds': contingency})
    report = {'measured_baseline': {'preparation_seconds': preparation, 'sumo_startup_seconds': result['sumo_startup_wall_seconds'],
                 'controller_loop_and_shutdown_seconds': measured_loop, 'one_prepared_case_seconds': one_case,
                 'planned': len(plan), 'valid_planned': len(valid)},
        'measured_probes': {'control_commands': 3*len(control_wall), 'mean_control_command_seconds': float(np.mean(control_wall)),
            'route_queries': len(samples), 'mean_route_query_seconds': query_mean,
            'p90_route_query_seconds': float(np.quantile([r['wall_seconds'] for r in samples], .9)),
            'duarouter_one_full_refresh_seconds': router_wall, 'duarouter_returncode': completed.returncode},
        'wet_control_extrapolation': controls,
        'rolling_query_extrapolation': {'dry_active_checks_per_rolling_case': dry_active_checks,
                                       'all_valid_active_all_slots_upper_count': conservative_active_checks},
        'five_case_forecast': {'from_scratch_nominal_seconds': five_nominal, 'contingency_seconds': five_stress,
                              'additional_four_after_baseline_nominal_seconds': max(0., five_nominal-preparation-one_case),
                              'additional_four_contingency_seconds': max(0., five_stress-preparation-one_case)},
        'dry_assignment_iteration_forecasts': iterations,
        'limitations': ['Only one dry whole-district traffic case was measured; four wet/control cases are forecasts.',
            'Probes measure empty-network control writes and routing; wet congestion, repeated failures, cache hits and paging can change wall time.',
            'Nominal uses dry active-vehicle checks; contingency assumes twice dry simulation time and all valid vehicles active at every routing slot. Neither is a confidence interval or a guaranteed bound.',
            'The router probe is one complete path refresh, not a converged Gawron/SDTA iteration. Forecasts omit unmeasured alternative-route probability-update overhead.',
            'Iteration counts are planning scenarios; convergence and the required iteration count were not measured.',
            'Budgets apply to this CPU/RAM, 5% demand and four simulated hours, with GUI disabled; they do not apply to 100% demand or 24 hours.']}
    write_json(out/'runtime_budget.json', report)
    print(json.dumps(report, indent=2), flush=True)
    return report


def assignment_forecast(out):
    """Remove timed online departure searches before adding an offline refresh.

    Standard preassigned-route SDTA does not also query every departing vehicle
    online. The residual is a conditional estimate, not a measured fixed-route run.
    """
    report = json.loads((out/'runtime_budget.json').read_text(encoding='utf-8'))
    result = json.loads((out/'cases/dry/result.json').read_text(encoding='utf-8'))
    query = result['route_query_stats']['wall_seconds']
    baseline = report['measured_baseline']
    residual = baseline['one_prepared_case_seconds']-query
    refresh = report['measured_probes']['duarouter_one_full_refresh_seconds']
    baseline['timed_online_departure_route_queries_seconds'] = query
    baseline['case_seconds_excluding_timed_route_queries'] = residual
    five = report['five_case_forecast']
    five['planning_allowance_seconds'] = baseline['preparation_seconds']+2*(five['from_scratch_nominal_seconds']-baseline['preparation_seconds'])
    five['additional_four_planning_allowance_seconds'] = five['planning_allowance_seconds']-baseline['preparation_seconds']-baseline['one_prepared_case_seconds']
    report['dry_assignment_iteration_forecasts'] = [
        {'iterations': n, 'nominal_seconds': baseline['preparation_seconds']+n*(residual+refresh),
         'contingency_seconds': baseline['preparation_seconds']+n*(2*residual+refresh)}
        for n in [10, 20, 30, 50]]
    report['assignment_forecast_formula'] = 'P + N * (B - timed_online_departure_queries + measured_offline_refresh); contingency doubles the non-query traffic portion'
    report['limitations'] += [
        'Assignment forecasts remove timed online departure-route queries before adding the offline router refresh, avoiding double-counting routing. A preassigned-route SUMO run was not separately measured.',
        'Only a single full path-refresh runtime is measured, and probability updates for alternative routes remain unmeasured.',
        'Sparse observed edge-cost intervals use normal free-flow fallback in duarouter where no matching measured interval exists.']
    report['limitations'].append('Five-case planning allowance is twice the nominal variable runtime, a scheduling choice; the separate all-active stress scenario is much more pessimistic and is neither an observed runtime nor a guaranteed upper bound.')
    write_json(out/'runtime_budget.json', report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('run')
    parser.add_argument('--recalculate-assignment', action='store_true')
    args = parser.parse_args(); out = (ROOT/args.run).resolve()
    if not args.recalculate_assignment:
        run(out)
    assignment_forecast(out)
