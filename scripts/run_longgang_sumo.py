"""Build and run a frozen, scaled Longgang SUMO/OSG pilot; separate historical data."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import pickle
import shutil
import subprocess
import time
import traceback
import uuid
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import yaml
from pyproj import Transformer
from uftr.adaptive import road_factors
from uftr.sumo_run import sumo_binary
from uftr.sumo_dynamic import (write_json, read_nodes, route_stage_paths, make_plan,
                               window_start, tau_proxy, prefer_route, accounting)

ROOT = Path(__file__).resolve().parents[1]
CASES = {'dry': (0, False, False), 'rain_departure': (0, True, False),
         'rain_rolling': (0, True, True), 'governed_departure': (9, True, False),
         'governed_rolling': (9, True, True)}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def prepare(out, cfg):
    import sumolib
    adaptive = ROOT/cfg['adaptive_package']; od = ROOT/cfg['od_package']
    raw = out/'raw'; raw.mkdir()
    print('Reading frozen source coordinates', flush=True)
    coords = read_nodes(od/'inferred_source_network.graphml')
    ids = np.array(list(coords), int); xy = np.array(list(coords.values()))
    transformer = Transformer.from_crs(4326, 32650, always_xy=True)
    x, y = transformer.transform(xy[:, 0], xy[:, 1]); a = cfg['area']
    cx, cy = transformer.transform(a['centre_lon'], a['centre_lat']); w = a['half_width_m']
    inside_nodes = set(map(int, ids[(abs(x-cx) <= w) & (abs(y-cy) <= w)]))
    projected = {int(n): (float(xx-cx+w), float(yy-cy+w)) for n, xx, yy in zip(ids, x, y) if n in inside_nodes}
    edges = pd.read_parquet(adaptive/'raw/source_edges.parquet')
    keep = (edges.u.isin(inside_nodes) & edges.v.isin(inside_nodes) & (edges.u != edges.v) & (edges.length_m > .1)).to_numpy()
    local = edges.loc[keep].copy(); local['source_arc_position'] = np.flatnonzero(keep)
    local.to_csv(raw/'source_sumo_mapping.csv', index=False)
    nodes_xml = ET.Element('nodes'); edges_xml = ET.Element('edges')
    used = set(local.u)|set(local.v)
    for node in sorted(used):
        xx, yy = projected[int(node)]
        ET.SubElement(nodes_xml, 'node', id=str(node), x=str(xx), y=str(yy), z='0', type='priority')
    for row in local.itertuples():
        ET.SubElement(edges_xml, 'edge', id=row.edge_id, **{'from': str(row.u), 'to': str(row.v),
                      'numLanes': '1', 'speed': str(row.speed_kph/3.6), 'length': str(row.length_m), 'allow': 'passenger'})
    ET.ElementTree(nodes_xml).write(raw/'network.nod.xml', encoding='utf-8', xml_declaration=True)
    ET.ElementTree(edges_xml).write(raw/'network.edg.xml', encoding='utf-8', xml_declaration=True)
    command = [str(sumo_binary('netconvert')), '--node-files', str(raw/'network.nod.xml'),
               '--edge-files', str(raw/'network.edg.xml'), '--output-file', str(raw/'network.net.xml'),
               '--no-turnarounds', 'false', '--junctions.corner-detail', '0', '--offset.disable-normalization', 'true']
    done = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
    (raw/'netconvert.log').write_text(done.stdout+'\n'+done.stderr, encoding='utf-8')
    if done.returncode: raise RuntimeError(done.stderr[-3000:])
    net = sumolib.net.readNet(str(raw/'network.net.xml'))
    if {e.getID() for e in net.getEdges()} != set(local.edge_id): raise ValueError('SUMO source edge identity mismatch')
    print('SUMO network:', len(local), 'arcs', len(used), 'nodes', flush=True)
    with (adaptive/'raw/network.pkl').open('rb') as stream: source, corridors, chains = pickle.load(stream)
    if not np.array_equal(source.edge_id.to_numpy(), edges.edge_id.to_numpy()): raise ValueError('frozen arc order mismatch')
    connectors = pd.read_csv(od/'zone_connectors.csv'); n = connectors.node_id.fillna(-1).to_numpy(int)
    matrix_file = np.load(od/'od_sensitivity_veh_h.npz')
    if not np.array_equal(matrix_file['zone_ids'].astype(str), connectors.zone_id.astype(str)): raise ValueError('OD zone mismatch')
    matrices = [matrix_file['base__'+p] for p in ['offpeak', 'morning_peak', 'evening_peak']]
    visits, demand_audit = route_stage_paths(corridors, chains, keep, n, matrices)
    write_json(raw/'boundary_visits.json', visits); write_json(raw/'boundary_demand_audit.json', demand_audit)
    print('Boundary OD visits:', len(visits), flush=True)
    # Feature order in the frozen adaptive depth files comes from its frozen grid.
    adaptive_cfg = yaml.safe_load((ROOT/'configs/longgang_adaptive.yaml').read_text(encoding='utf-8'))
    grid_path = ROOT/adaptive_cfg['surface_package']/'raw/routing_grid.npz'
    features = np.load(grid_path)['source_feature_positions']
    lookup = {int(f): i for i, f in enumerate(features)}
    columns = np.array([lookup.get(int(f), -1) for f in local.depth_feature_position])
    all_depths = {}
    for mask in [0, 9]:
        data = np.load(adaptive/'cases'/f'mask{mask:02d}_rain130_water.npz')['depth_m']
        h = np.full((len(data), len(local)), np.nan, np.float32)
        valid = columns >= 0; h[:, valid] = data[:, columns[valid]]
        all_depths[mask] = h
    s = cfg['simulation']; start, peak, count = window_start(all_depths[0], s['duration_seconds'], s['closure_depth_m'])
    end = start+s['duration_seconds']//900+1
    np.savez_compressed(raw/'road_states.npz', baseline=all_depths[0][start:end], governed=all_depths[9][start:end])
    plan, plan_report = make_plan(visits, edges.edge_id.to_numpy(), net, start*900, s, cfg['seed'])
    if not plan: raise ValueError('empty pilot vehicle plan')
    pd.DataFrame(plan).to_csv(raw/'departure_plan.csv', index=False)
    write_json(raw/'plan_report.json', plan_report)
    view = ET.Element('viewsettings'); ET.SubElement(view, 'viewport', zoom='100', x=str(w), y=str(w), z='0')
    ET.ElementTree(view).write(raw/'view.xml', encoding='utf-8', xml_declaration=True)
    route_xml = ET.Element('routes')
    ET.SubElement(route_xml, 'vType', id='car', vClass='passenger', guiShape='passenger', color='0.1,0.5,0.9',
                  length='5', minGap='2.5', tau='1.4', accel='2.6', decel='4.5', sigma='0.5')
    ET.ElementTree(route_xml).write(raw/'types.rou.xml', encoding='utf-8', xml_declaration=True)
    window = {'start_interval': int(start), 'start_hour_since_2023_09_06': start/4,
              'duration_seconds': s['duration_seconds'], 'departure_seconds': s['departure_seconds'],
              'peak_interval': peak, 'peak_closed_source_arcs': int(count[peak]),
              'selection': 'Centred on first maximum closed-arc endpoint in untreated 1.3x rain, clamped to input window; no traffic outcomes used',
              'initial_state': 'Empty network; no queues inherited from preceding hours',
              'roi_bounds_local_m': [0, 0, 2*w, 2*w], 'projection': 'EPSG:32650 translated by ROI southwest corner',
              'source_nodes': len(used), 'source_arcs': len(local), 'signals': 'All junctions priority; uncalibrated',
              'geometry': 'Frozen inferred nodes/segments, flat z=0; no certified road surface elevation',
              'unknown_depth_arcs': int(np.count_nonzero(~np.isfinite(all_depths[0][0])))}
    write_json(raw/'window.json', window)
    sources = [ROOT/'configs/longgang_sumo.yaml', ROOT/'scripts/run_longgang_sumo.py', ROOT/'src/uftr/sumo_dynamic.py',
               ROOT/'src/uftr/adaptive.py', adaptive/'raw/source_edges.parquet', adaptive/'raw/network.pkl',
               od/'inferred_source_network.graphml', od/'od_sensitivity_veh_h.npz', od/'zone_connectors.csv', grid_path]
    sources += [adaptive/'cases'/f'mask{m:02d}_rain130_water.npz' for m in [0, 9]]
    write_json(out/'inputs.json', [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for p in sources])
    for p in sources[:4]: shutil.copy2(p, out/'provenance'/p.name)
    return window


def simulate(out, cfg, scenario, gui=False):
    import traci
    import traci.constants as tc
    s = cfg['simulation']; mask, wet, rolling = CASES[scenario]
    raw = out/'raw'; local = pd.read_csv(raw/'source_sumo_mapping.csv')
    plan = pd.read_csv(raw/'departure_plan.csv').to_dict('records')
    road_ids = local.edge_id.astype(str).to_numpy(); index = {e: i for i, e in enumerate(road_ids)}
    states = np.load(raw/'road_states.npz')['governed' if mask else 'baseline']
    if not wet: states = np.where(np.isfinite(states), 0., np.nan)
    speeds, factors, _ = road_factors(states, local.speed_kph.to_numpy()[None, :],
                                     local.capacity_loss.to_numpy()[None, :], s['closure_depth_m'])
    folder = out/('preview_'+scenario+'_'+uuid.uuid4().hex[:6] if gui else 'cases/'+scenario)
    folder.mkdir(parents=True)
    config_xml = ET.Element('configuration'); inp = ET.SubElement(config_xml, 'input')
    ET.SubElement(inp, 'net-file', value=str((raw/'network.net.xml').resolve()))
    ET.SubElement(inp, 'route-files', value=str((raw/'types.rou.xml').resolve()))
    ET.ElementTree(config_xml).write(folder/'longgang.sumocfg', encoding='utf-8', xml_declaration=True)
    command = [str(sumo_binary('sumo-gui' if gui else 'sumo')), '-c', str(folder/'longgang.sumocfg'),
               '--begin', '0', '--end', str(s['duration_seconds']), '--step-length', str(s['step_seconds']),
               '--seed', str(cfg['seed']), '--time-to-teleport', '-1', '--max-depart-delay', '-1',
               '--collision.action', 'warn', '--no-step-log', 'true', '--duration-log.disable', 'true',
               '--tripinfo-output', str(folder/'tripinfo.xml'), '--tripinfo-output.write-unfinished', 'true',
               '--summary-output', str(folder/'summary.xml'), '--error-log', str(folder/'warnings.log')]
    if gui: command += ['--osg-view', 'true', '--start', '--delay', '15', '--gui-settings-file', str(raw/'view.xml')]
    (folder/'command.json').write_text(json.dumps(command, indent=2), encoding='utf-8')
    label = 'lg_'+scenario+'_'+uuid.uuid4().hex[:8]
    traci.start(command, label=label, stdout=subprocess.DEVNULL); conn = traci.getConnection(label)
    queue = []; pointer = 0; injected = set(); known_routes = {}; destination = {}; arrived = 0
    tau_cache = {}; held = set(); changes = []; controls = []; series = []; events = []
    reroutes = attempts = no_route = teleports = collisions = safety_stops = 0
    occupancy = external_area = 0.; max_balance = 0; start_wall = time.perf_counter()
    weights = {str(e): float(l*3.6/v) for e, l, v in zip(road_ids, local.length_m, local.speed_kph)}
    estimates = dict(weights); changed_weights = set(); closed = set(); k = 0; route_cache = {}
    def find_route(source, target, now):
        key = (source, target)
        if key not in route_cache:
            route_cache[key] = conn.simulation.findRoute(source, target, vType='car', depart=now).edges
        return route_cache[key]
    try:
        for now in range(0, s['duration_seconds'], s['step_seconds']):
            if now % 900 == 0:
                k = now//900; closed = set(road_ids[factors[k] <= 0])
                for i, edge in enumerate(road_ids):
                    conn.edge.setDisallowed(edge, ['passenger'] if edge in closed else [])
                    conn.edge.setAllowed(edge, [] if edge in closed else ['passenger'])
                    if edge in closed: conn.edge.setDisallowed(edge, ['passenger'])
                    limit = max(.1, float(speeds[k, i]/3.6))
                    conn.edge.setMaxSpeed(edge, limit)
                    conn.edge.setParameter(edge, 'flood_depth_m', str(float(states[k, i])) if np.isfinite(states[k, i]) else 'unknown_assumed_normal')
                    weights[edge] = float(local.length_m.iloc[i]/limit)
                controls.append({'time_s': now, 'closed_arcs': len(closed), 'wet_arcs': int(np.count_nonzero(states[k] > 0))})
            subs = conn.vehicle.getAllSubscriptionResults()
            if now % s['route_seconds'] == 0 or now % 900 == 0:
                route_cache.clear()
                grouped = {}
                for value in subs.values():
                    edge = value.get(tc.VAR_ROAD_ID, '')
                    if edge in index: grouped.setdefault(edge, []).append(value.get(tc.VAR_SPEED, 0.))
                current_changed = set(grouped)|changed_weights
                for edge in current_changed:
                    measured = weights[edge]
                    if edge in grouped:
                        mean_speed = max(s['observed_speed_floor_m_s'], float(np.mean(grouped[edge])))
                        measured = max(measured, float(local.length_m.iloc[index[edge]])/mean_speed)
                    estimate = s['travel_time_smoothing']*measured+(1-s['travel_time_smoothing'])*estimates[edge]
                    estimates[edge] = max(weights[edge], estimate)
                    conn.edge.adaptTraveltime(edge, estimates[edge])
                # Flood free-flow changes also apply to empty, unobserved edges.
                if now % 900 == 0:
                    for edge in road_ids:
                        estimates[edge] = max(weights[edge], estimates[edge])
                        if edge not in current_changed: conn.edge.adaptTraveltime(edge, weights[edge]); estimates[edge] = weights[edge]
                changed_weights = set(grouped)
                if rolling:
                    for vid, value in subs.items():
                        edge = value.get(tc.VAR_ROAD_ID, '')
                        if edge not in index or edge in closed: continue
                        route_index = int(value.get(tc.VAR_ROUTE_INDEX, 0)); old = known_routes[vid][route_index:]
                        attempts += 1
                        route = find_route(edge, destination[vid], now)
                        if not route: no_route += 1; continue
                        if tuple(old) != tuple(route) and prefer_route(old, route, estimates, closed,
                                s['minimum_reroute_saving_seconds'], s['minimum_reroute_saving_fraction']):
                            conn.vehicle.setRoute(vid, route); known_routes[vid] = list(route)
                            reroutes += 1; value[tc.VAR_ROUTE_INDEX] = 0
                            changes.append({'time_s': now, 'vehicle_id': vid, 'old': list(old), 'new': list(route),
                                            'forced_by_closure': any(e in closed for e in old)})
            if now % s['output_seconds'] == 0:
                while pointer < len(plan) and plan[pointer]['depart_s'] <= now:
                    if plan[pointer]['valid']: queue.append(plan[pointer])
                    pointer += 1
                remaining = []
                for row in queue:
                    normal = row['normal_route'].split(); source, target = normal[0], normal[-1]
                    if source in closed or target in closed: remaining.append(row); continue
                    route = find_route(source, target, now)
                    if not route or any(e in closed for e in route): remaining.append(row); continue
                    vid = row['vehicle_id']; conn.route.add('r_'+vid, route)
                    conn.vehicle.add(vid, 'r_'+vid, typeID='car', depart=str(now), departLane='best')
                    injected.add(vid); known_routes[vid] = list(route); destination[vid] = target
                    events.append({'vehicle_id': vid, 'planned_depart_s': row['depart_s'], 'injection_s': now,
                                   'external_wait_seconds': now-row['depart_s']})
                queue = remaining
            if now % s['safety_seconds'] == 0:
                for vid, value in subs.items():
                    edge = value.get(tc.VAR_ROAD_ID, '')
                    if edge not in index: continue
                    i = index[edge]; route_index = int(value.get(tc.VAR_ROUTE_INDEX, 0)); route = known_routes[vid]
                    next_edge = route[route_index+1] if route_index+1 < len(route) else None
                    stop = edge in closed or next_edge in closed
                    if stop and vid not in held:
                        conn.vehicle.setSpeed(vid, 0); held.add(vid); safety_stops += 1
                    elif not stop and vid in held:
                        conn.vehicle.setSpeed(vid, -1); held.remove(vid)
                    tau = tau_proxy(float(local.capacity_veh_h.iloc[i]), float(local.speed_kph.iloc[i]/3.6), float(factors[k, i]))
                    if abs(tau_cache.get(vid, -1)-tau) > 1e-6:
                        conn.vehicle.setTau(vid, tau); tau_cache[vid] = tau
            conn.simulationStep(float(now+s['step_seconds']))
            departed_ids = conn.simulation.getDepartedIDList()
            for vid in departed_ids:
                conn.vehicle.subscribe(vid, [tc.VAR_ROAD_ID, tc.VAR_SPEED, tc.VAR_ROUTE_INDEX])
            arrived_ids = conn.simulation.getArrivedIDList(); arrived += len(arrived_ids)
            for vid in arrived_ids:
                known_routes.pop(vid, None); destination.pop(vid, None); tau_cache.pop(vid, None); held.discard(vid)
            teleports += conn.simulation.getStartingTeleportNumber(); collisions += conn.simulation.getCollidingVehiclesNumber()
            running = conn.vehicle.getIDCount(); pending = len(conn.simulation.getPendingVehicles())
            due = sum(r['valid'] and r['depart_s'] <= now+s['step_seconds'] for r in plan)
            external = due-len(injected)
            balance = len(injected)-pending-running-arrived
            max_balance = max(max_balance, abs(balance))
            occupancy += (running+pending+external)*s['step_seconds']; external_area += external*s['step_seconds']
            if (now+s['step_seconds']) % s['output_seconds'] == 0:
                series.append({'time_s': now+s['step_seconds'], 'released_valid': due, 'injected': len(injected),
                               'arrived': arrived, 'running': running, 'sumo_pending': pending, 'external_pending': external,
                               'unfinished_released': running+pending+external, 'held': len(held),
                               'balance_error': balance, 'vehicle_seconds': occupancy})
            if (now+s['step_seconds']) % 1800 == 0:
                print(scenario, now+s['step_seconds'], 'arrived', arrived, 'running', running, 'external', external, flush=True)
        final_running = conn.vehicle.getIDCount(); final_pending = len(conn.simulation.getPendingVehicles())
    finally:
        conn.close()
    invalid = sum(not r['valid'] for r in plan)
    result = accounting(len(plan), invalid, len(plan)-invalid-len(injected), len(injected), final_pending, final_running, arrived)
    unfinished = result['external_pending']+result['sumo_pending']+result['running']
    trips = [e.attrib for e in ET.parse(folder/'tripinfo.xml').getroot().findall('tripinfo')]
    completed = [r for r in trips if float(r['arrival']) >= 0]
    result.update(scenario=scenario, rolling=rolling, governance_mask=mask, duration_seconds=s['duration_seconds'],
                  unfinished=unfinished, reroute_attempts=attempts, route_changes=reroutes, no_route_attempts=no_route,
                  safety_stops=safety_stops, teleports=teleports, collision_vehicle_events=collisions,
                  vehicle_seconds=occupancy, external_wait_vehicle_seconds=external_area,
                  generalized_vehicle_seconds=occupancy+s['terminal_penalty_seconds']*(unfinished+invalid),
                  completed_mean_duration_seconds=float(np.mean([float(r['duration']) for r in completed])) if completed else None,
                  maximum_injected_balance_error=max_balance, wall_seconds=time.perf_counter()-start_wall,
                  capacity_model='Uncalibrated road-class / wet-factor per-vehicle tau proxy, not exact veh/h control',
                  geometry='Flat road/car OSG; no buildings, measured elevations or flood hydraulics')
    pd.DataFrame(series).to_csv(folder/'traffic_series.csv', index=False)
    pd.DataFrame(events).to_csv(folder/'injections.csv', index=False)
    pd.DataFrame(controls).to_csv(folder/'controls.csv', index=False)
    write_json(folder/'route_changes.json', changes); write_json(folder/'result.json', result)
    if max_balance or result['balance_error'] or result['injected_balance_error']: raise ValueError('SUMO vehicle accounting failed')
    if teleports: raise ValueError('unexpected SUMO teleport')
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--config', default='configs/longgang_sumo.yaml')
    parser.add_argument('--prepared'); parser.add_argument('--scenario', choices=list(CASES)); parser.add_argument('--gui', action='store_true')
    args = parser.parse_args(); cfg = yaml.safe_load((ROOT/args.config).read_text(encoding='utf-8'))
    if cfg['region'] != 'longgang' or cfg['include_dapeng'] is not False: raise ValueError('invalid scope')
    if args.prepared:
        out = (ROOT/args.prepared).resolve()
        stored = yaml.safe_load((out/'config.yaml').read_text(encoding='utf-8'))
        if cfg != stored: raise ValueError('prepared configuration changed')
        for item in json.loads((out/'inputs.json').read_text(encoding='utf-8')):
            if sha(ROOT/item['path']) != item['sha256']: raise ValueError('prepared input/source changed: '+item['path'])
    else:
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_sumo_'+uuid.uuid4().hex[:8]
        out = ROOT/cfg['output_root']/run_id; out.mkdir(parents=True); (out/'provenance').mkdir()
        (out/'config.yaml').write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding='utf-8')
        write_json(out/'status.json', {'status': 'preparing'}); print('RUN', out, flush=True)
        try: prepare(out, cfg)
        except Exception:
            write_json(out/'status.json', {'status': 'failed_preparation', 'traceback': traceback.format_exc()}); raise
    try:
        reports = []
        for case in [args.scenario] if args.scenario else list(CASES):
            reports.append(simulate(out, cfg, case, gui=args.gui))
            if not args.gui: pd.DataFrame(reports).to_csv(out/'comparison.csv', index=False)
        if not args.gui:
            write_json(out/'status.json', {'status': 'complete', 'scenarios': [r['scenario'] for r in reports]})
        print('DONE', out, flush=True)
    except BaseException:
        if not args.gui: write_json(out/'status.json', {'status': 'failed_simulation', 'traceback': traceback.format_exc()})
        raise


if __name__ == '__main__': main()
