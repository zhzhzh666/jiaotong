"""Headless whole-Longgang 5% baseline with hourly wall-time and memory evidence."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import gc
import hashlib
import json
import pickle
import platform
import shutil
import subprocess
import time
import traceback
import uuid
import xml.etree.ElementTree as ET

import geopandas as gpd
import numpy as np
import pandas as pd
import psutil
import shapely
import yaml
from pyproj import Transformer
from uftr.adaptive import road_factors
from uftr.sumo_run import sumo_binary
from uftr.sumo_dynamic import write_json, read_nodes, tau_proxy, prefer_route, accounting
from uftr.sumo_benchmark import ResourceMonitor, sample_full_od, sampled_source_routes

ROOT = Path(__file__).resolve().parents[1]
CASES = {'dry': (0, False, False), 'rain_departure': (0, True, False),
         'rain_rolling': (0, True, True), 'governed_departure': (9, True, False),
         'governed_rolling': (9, True, True)}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def prepare(out, cfg):
    import sumolib
    started = time.perf_counter()
    raw = out/'raw'; raw.mkdir()
    od = ROOT/cfg['od_package']; adaptive = ROOT/cfg['adaptive_package']
    boundary_file = od/'study_boundary.geojson'
    boundary_frame = gpd.read_file(boundary_file).to_crs(32650)
    if boundary_frame.include_dapeng.any():
        raise ValueError('Dapeng was not excluded from the study boundary')
    boundary = boundary_frame.geometry.union_all()
    buffered = boundary.buffer(cfg['area']['surrounding_buffer_m'])
    boundary_frame.to_crs(4326).to_file(raw/'study_boundary.geojson', driver='GeoJSON')
    connectors = pd.read_csv(od/'zone_connectors.csv')
    matrix_file = np.load(od/'od_sensitivity_veh_h.npz')
    if not np.array_equal(matrix_file['zone_ids'].astype(str), connectors.zone_id.astype(str)):
        raise ValueError('OD order changed')
    matrices = [matrix_file['base__'+p] for p in ['offpeak', 'morning_peak', 'evening_peak']]
    settings = cfg['simulation']; start = settings['start_interval']
    plan, expected = sample_full_od(matrices, start*900, settings, cfg['seed'])
    pairs = {(r['origin_zone'], r['destination_zone']) for r in plan}
    print('Full-OD planned trips:', len(plan), 'sampled pairs:', len(pairs), flush=True)
    with (adaptive/'raw/network.pkl').open('rb') as stream:
        source, corridors, chains = pickle.load(stream)
    routes = sampled_source_routes(corridors, chains, connectors.node_id.fillna(-1).to_numpy(int), pairs)
    edge_ids = source.edge_id.astype(str).to_numpy()
    for row in plan:
        path, reason = routes[row['origin_zone'], row['destination_zone']]
        row.update(normal_route=' '.join(edge_ids[path]), valid=bool(path), route_status=reason)
    path_union = {e for path, _ in routes.values() for e in path}
    del routes, corridors, chains
    gc.collect()
    coords = read_nodes(od/'inferred_source_network.graphml')
    nodes = np.array(list(coords), int); xy = np.array(list(coords.values()))
    transformer = Transformer.from_crs(4326, 32650, always_xy=True)
    x, y = transformer.transform(xy[:, 0], xy[:, 1])
    # IDs are not assumed contiguous; mapping to vector positions is explicit.
    lookup = {int(n): i for i, n in enumerate(nodes)}
    u = np.array([lookup[int(n)] for n in source.u]); v = np.array([lookup[int(n)] for n in source.v])
    segments = shapely.linestrings(np.stack([np.column_stack([x[u], y[u]]), np.column_stack([x[v], y[v]])], axis=1))
    district_mask = shapely.intersects(segments, boundary)
    surrounding_mask = shapely.intersects(segments, buffered)
    keep = surrounding_mask.copy()
    keep[list(path_union)] = True
    usable = (source.u != source.v).to_numpy() & (source.length_m.to_numpy() > .1)
    excluded_inside = int(np.count_nonzero(district_mask & ~usable))
    keep &= usable
    local = source.loc[keep].copy()
    local['source_arc_position'] = np.flatnonzero(keep)
    local['intersects_district'] = district_mask[keep]
    local.to_csv(raw/'source_sumo_mapping.csv', index=False)
    used = set(local.u)|set(local.v)
    xmin, ymin, xmax, ymax = buffered.bounds
    nodes_xml = ET.Element('nodes'); edges_xml = ET.Element('edges')
    for node in sorted(used):
        pos = lookup[int(node)]
        ET.SubElement(nodes_xml, 'node', id=str(node), x=str(float(x[pos]-xmin)),
                      y=str(float(y[pos]-ymin)), z='0', type='priority')
    for row in local.itertuples():
        ET.SubElement(edges_xml, 'edge', id=row.edge_id, **{'from': str(row.u), 'to': str(row.v),
            'numLanes': '1', 'speed': str(row.speed_kph/3.6), 'length': str(row.length_m), 'allow': 'passenger'})
    ET.ElementTree(nodes_xml).write(raw/'network.nod.xml', encoding='utf-8', xml_declaration=True)
    ET.ElementTree(edges_xml).write(raw/'network.edg.xml', encoding='utf-8', xml_declaration=True)
    scope = {'district_source_arcs': int(np.count_nonzero(district_mask & usable)),
             'district_arcs_in_sumo': int(local.intersects_district.sum()),
             'excluded_district_degenerate_arcs': excluded_inside,
             'surrounding_buffer_m': cfg['area']['surrounding_buffer_m'],
             'source_arcs': len(local), 'source_nodes': len(used),
             'retained_sampled_source_path_arcs': len(path_union),
             'whole_trips_not_roi_visits': True,
             'scope': 'Every usable source segment intersecting Longgang excluding Dapeng, 3km surrounding buffer, plus complete sampled dry source paths. Surroundings are connectors, not an expanded administrative study area.',
             'outside_routing_limit': 'New alternatives outside the buffer and sampled dry-path union are not represented; no external-external OD demand exists in the source synthetic matrices.'}
    if scope['district_source_arcs'] != scope['district_arcs_in_sumo']:
        raise ValueError('Whole-district road coverage failed')
    write_json(raw/'scope.json', scope)
    print('Whole district source arcs:', scope['district_source_arcs'], 'SUMO with surroundings:', len(local), flush=True)
    grid_path = ROOT/cfg['surface_package']/'raw/routing_grid.npz'
    features = np.load(grid_path)['source_feature_positions']
    feature_lookup = {int(f): i for i, f in enumerate(features)}
    columns = np.array([feature_lookup.get(int(f), -1) for f in local.depth_feature_position])
    valid_columns = columns >= 0
    states = {}
    for mask, name in [(0, 'baseline'), (9, 'governed')]:
        water = np.load(adaptive/'cases'/f'mask{mask:02d}_rain130_water.npz')['depth_m']
        h = np.full((settings['duration_seconds']//900+1, len(local)), np.nan, np.float32)
        h[:, valid_columns] = water[start:start+len(h), columns[valid_columns]]
        states[name] = h
    np.savez_compressed(raw/'road_states.npz', **states)
    # Free full-city preparation objects before starting the larger SUMO network reader.
    del source, coords, xy, x, y, lookup, segments, nodes_xml, edges_xml, states, water, path_union
    gc.collect()
    conversion_start = time.perf_counter()
    command = [str(sumo_binary('netconvert')), '-n', str(raw/'network.nod.xml'), '-e', str(raw/'network.edg.xml'),
               '-o', str(raw/'network.net.xml'), '--no-turnarounds', 'false', '--junctions.corner-detail', '0',
               '--offset.disable-normalization', 'true']
    with (raw/'netconvert.log').open('w', encoding='utf-8') as log:
        done = subprocess.run(command, stdout=log, stderr=log, timeout=1200)
    if done.returncode:
        raise RuntimeError('netconvert failed; see retained netconvert.log')
    netconvert_seconds = time.perf_counter()-conversion_start
    print('netconvert wall seconds', netconvert_seconds, flush=True)
    network = sumolib.net.readNet(str(raw/'network.net.xml'))
    if {e.getID() for e in network.getEdges()} != set(local.edge_id):
        raise ValueError('SUMO source edge identity mismatch')
    route_fixes = {}
    excluded_ids = set(edge_ids)-set(local.edge_id)
    for row in plan:
        if not row['valid']:
            continue
        pair = (row['origin_zone'], row['destination_zone'])
        if pair not in route_fixes:
            route = row['normal_route'].split()
            if excluded_ids.intersection(route):
                route_fixes[pair] = ('', False, 'degenerate_source_path')
            elif all(network.getEdge(a).getConnections(network.getEdge(b)) for a, b in zip(route, route[1:])):
                route_fixes[pair] = (row['normal_route'], True, 'source_reachable')
            else:
                candidate, _ = network.getShortestPath(network.getEdge(route[0]), network.getEdge(route[-1]), vClass='passenger')
                route_fixes[pair] = (' '.join(e.getID() for e in candidate), True, 'sumo_turn_repaired') if candidate else ('', False, 'sumo_turn_disconnected')
        row['normal_route'], row['valid'], row['route_status'] = route_fixes[pair]
    pd.DataFrame(plan).to_csv(raw/'departure_plan.csv', index=False)
    report = {'expected_all_scaled_trips': expected, 'planned_vehicles': len(plan),
              'valid_planned': sum(r['valid'] for r in plan), 'invalid_planned': sum(not r['valid'] for r in plan),
              'route_status_counts': pd.Series([r['route_status'] for r in plan]).value_counts().to_dict(),
              'demand_fraction': settings['demand_fraction'], 'poisson_seed': cfg['seed'],
              'matrix_shape': list(matrices[0].shape), 'source_offpeak_veh_h': float(matrices[0].sum()),
              'note': 'Whole OD sampled first, every sampled complete dry route retained. Intrazonal, connector and connectivity failures stay explicitly invalid, not fabricated trips or dropped draws.'}
    write_json(raw/'plan_report.json', report)
    route_xml = ET.Element('routes')
    ET.SubElement(route_xml, 'vType', id='car', vClass='passenger', guiShape='passenger', color='0.1,0.5,0.9',
                  length='5', minGap='2.5', tau='1.4', accel='2.6', decel='4.5', sigma='0.5')
    ET.ElementTree(route_xml).write(raw/'types.rou.xml', encoding='utf-8', xml_declaration=True)
    view = ET.Element('viewsettings')
    ET.SubElement(view, 'viewport', zoom='100', x=str((xmax-xmin)/2), y=str((ymax-ymin)/2), z='0')
    ET.ElementTree(view).write(raw/'view.xml', encoding='utf-8', xml_declaration=True)
    write_json(raw/'window.json', {'start_interval': start, 'start_beijing': '2023-09-10 10:00:00',
        'end_beijing': '2023-09-10 14:00:00', 'duration_seconds': settings['duration_seconds'],
        'departure_seconds': settings['departure_seconds'], 'selection': 'Fixed same clock window as archived local pilot, not reselected using full-district results',
        'initial_state': 'Empty network', 'projected_offset_m': [xmin, ymin]})
    sources = [ROOT/'configs/longgang_sumo_full.yaml', Path(__file__), ROOT/'src/uftr/sumo_benchmark.py',
        ROOT/'src/uftr/sumo_dynamic.py', ROOT/'src/uftr/adaptive.py', boundary_file,
        adaptive/'raw/source_edges.parquet', adaptive/'raw/network.pkl', od/'inferred_source_network.graphml',
        od/'od_sensitivity_veh_h.npz', od/'zone_connectors.csv', grid_path]
    sources += [adaptive/'cases'/f'mask{m:02d}_rain130_water.npz' for m in [0, 9]]
    write_json(out/'inputs.json', [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for p in sources])
    for p in sources[:5]:
        shutil.copy2(p, out/'provenance'/p.name)
    result = {'total_wall_seconds': time.perf_counter()-started, 'netconvert_wall_seconds': netconvert_seconds}
    write_json(out/'preparation.json', result)
    print('Preparation complete:', report['valid_planned'], 'valid /', len(plan), 'total', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='configs/longgang_sumo_full.yaml')
    parser.add_argument('--prepared')
    parser.add_argument('--scenario', choices=list(CASES), default='dry')
    args = parser.parse_args()
    cfg = yaml.safe_load((ROOT/args.config).read_text(encoding='utf-8'))
    if cfg['region'] != 'longgang' or cfg['include_dapeng'] is not False:
        raise ValueError('Invalid district scope')
    if args.prepared:
        out = (ROOT/args.prepared).resolve()
        if yaml.safe_load((out/'config.yaml').read_text(encoding='utf-8')) != cfg:
            raise ValueError('Prepared config changed')
        for item in json.loads((out/'inputs.json').read_text(encoding='utf-8')):
            if sha(ROOT/item['path']) != item['sha256']:
                raise ValueError('Prepared source/input changed: '+item['path'])
    else:
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_full5_'+uuid.uuid4().hex[:8]
        out = ROOT/cfg['output_root']/run_id
        out.mkdir(parents=True)
        (out/'provenance').mkdir()
        (out/'config.yaml').write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding='utf-8')
        write_json(out/'hardware.json', hardware())
    print('RUN', out, flush=True)
    resource_file = out/('resources_'+args.scenario+'_'+uuid.uuid4().hex[:6]+'.csv')
    monitor = ResourceMonitor(resource_file, cfg['benchmark']['memory_sample_seconds']).start()
    started = time.perf_counter()
    try:
        if not args.prepared:
            write_json(out/'status.json', {'status': 'preparing', 'scenario': args.scenario})
            prepare(out, cfg)
            gc.collect()
        monitor.phase = args.scenario
        write_json(out/'status.json', {'status': 'simulating', 'scenario': args.scenario})
        result = simulate(out, cfg, args.scenario, monitor=monitor)
        write_json(out/'status.json', {'status': 'complete', 'scenarios': [args.scenario],
                                     'whole_district_baseline_only': args.scenario == 'dry'})
        pd.DataFrame([result]).to_csv(out/'comparison.csv', index=False)
        print('DONE', out, flush=True)
    except BaseException:
        write_json(out/'status.json', {'status': 'failed', 'traceback': traceback.format_exc()})
        raise
    finally:
        monitor.close()
        write_json(out/'resources_summary.json', {**monitor.summary(), 'total_wall_seconds': time.perf_counter()-started,
            'trace': resource_file.name, 'memory_definition': hardware()['memory_definition']})


def hardware():
    cpu_name = platform.processor()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            cpu_name = winreg.QueryValueEx(key, 'ProcessorNameString')[0]
    except (ImportError, OSError):
        pass
    return {'platform': platform.platform(), 'cpu': cpu_name, 'physical_cores': psutil.cpu_count(logical=False),
            'logical_cpus': psutil.cpu_count(), 'ram_gib': psutil.virtual_memory().total/2**30,
            'gpu_solver': False, 'memory_definition': '1-second samples of summed Python+descendant RSS; shared pages may be counted twice; host available also reflects other apps'}


def simulate(out, cfg, scenario, gui=False, monitor=None):
    import traci
    import traci.constants as tc
    s = cfg['simulation']; mask, wet, rolling = CASES[scenario]
    raw = out/'raw'; local = pd.read_csv(raw/'source_sumo_mapping.csv')
    plan = pd.read_csv(raw/'departure_plan.csv').fillna({'normal_route': ''}).to_dict('records')
    valid_departures = np.sort([r['depart_s'] for r in plan if r['valid']])
    road_ids = local.edge_id.astype(str).to_numpy(); index = {e: i for i, e in enumerate(road_ids)}
    states = np.load(raw/'road_states.npz')['governed' if mask else 'baseline']
    if not wet: states = np.where(np.isfinite(states), 0., np.nan)
    speeds, factors, _ = road_factors(states, local.speed_kph.to_numpy()[None, :],
                                     local.capacity_loss.to_numpy()[None, :], s['closure_depth_m'])
    folder = out/('preview_'+scenario+'_'+uuid.uuid4().hex[:6] if gui else 'cases/'+scenario)
    folder.mkdir(parents=True)
    additional = ET.Element('additional')
    ET.SubElement(additional, 'edgeData', id='costs', file=str((folder/'edge_costs.xml.gz').resolve()), period='900', excludeEmpty='true')
    ET.ElementTree(additional).write(folder/'costs.add.xml', encoding='utf-8', xml_declaration=True)
    config_xml = ET.Element('configuration'); inp = ET.SubElement(config_xml, 'input')
    ET.SubElement(inp, 'net-file', value=str((raw/'network.net.xml').resolve()))
    ET.SubElement(inp, 'route-files', value=str((raw/'types.rou.xml').resolve()))
    ET.ElementTree(config_xml).write(folder/'longgang.sumocfg', encoding='utf-8', xml_declaration=True)
    command = [str(sumo_binary('sumo-gui' if gui else 'sumo')), '-c', str(folder/'longgang.sumocfg'),
               '--begin', '0', '--end', str(s['duration_seconds']), '--step-length', str(s['step_seconds']),
               '--seed', str(cfg['seed']), '--time-to-teleport', '-1', '--max-depart-delay', '-1',
               '--collision.action', 'warn', '--no-step-log', 'true', '--duration-log.disable', 'true',
               '--tripinfo-output', str(folder/'tripinfo.xml'), '--tripinfo-output.write-unfinished', 'true',
               '--summary-output', str(folder/'summary.xml'), '--error-log', str(folder/'warnings.log'),
               '--additional-files', str(folder/'costs.add.xml'),
               '--vehroute-output', str(folder/'vehicle_routes.xml.gz'), '--vehroute-output.write-unfinished', 'true',
               '--fcd-output', str(folder/'fcd.xml.gz'), '--device.fcd.period', str(cfg['benchmark']['fcd_period_seconds'])]
    if gui: command += ['--osg-view', 'true', '--start', '--delay', '15', '--gui-settings-file', str(raw/'view.xml')]
    (folder/'command.json').write_text(json.dumps(command, indent=2), encoding='utf-8')
    label = 'lg_'+scenario+'_'+uuid.uuid4().hex[:8]
    startup_wall = time.perf_counter()
    traci.start(command, label=label, stdout=subprocess.DEVNULL); conn = traci.getConnection(label)
    startup_seconds = time.perf_counter()-startup_wall
    queue = []; pointer = 0; injected = set(); known_routes = {}; destination = {}; arrived = 0
    tau_cache = {}; held = set(); changes = []; controls = []; series = []; events = []
    reroutes = attempts = no_route = teleports = collisions = safety_stops = 0
    occupancy = external_area = 0.; max_balance = 0; start_wall = time.perf_counter()
    hourly = []; hour_wall = start_wall
    hour_monitor_start = time.perf_counter()-monitor.started if monitor else 0.
    route_query_stats = {'count': 0, 'wall_seconds': 0.}
    length_array = local.length_m.to_numpy(); speed_array = local.speed_kph.to_numpy()
    tau_table = np.array([[tau_proxy(c, v/3.6, f) for c, v, f in zip(local.capacity_veh_h, speed_array, row)] for row in factors])
    init_seconds = time.perf_counter()-start_wall
    print('SUMO startup seconds', startup_seconds, 'controller init', init_seconds, flush=True)
    weights = {str(e): float(l*3.6/v) for e, l, v in zip(road_ids, local.length_m, local.speed_kph)}
    estimates = dict(weights); changed_weights = set(); closed = set(); k = 0; route_cache = {}
    def find_route(source, target, now):
        key = (source, target)
        if key not in route_cache:
            query_start = time.perf_counter()
            route_cache[key] = conn.simulation.findRoute(source, target, vType='car', depart=now).edges
            route_query_stats['count'] += 1
            route_query_stats['wall_seconds'] += time.perf_counter()-query_start
        return route_cache[key]
    try:
        for now in range(0, s['duration_seconds'], s['step_seconds']):
            if now % 900 == 0:
                k = now//900; closed = set(road_ids[factors[k] <= 0])
                # Dry edge defaults already equal the configured speed/permissions.
                # Wet runs send only changed controls; no repeated static TraCI writes.
                if wet:
                    changed = np.arange(len(road_ids)) if k == 0 else np.flatnonzero(
                        (speeds[k] != speeds[k-1]) | (factors[k] != factors[k-1]))
                    for i in changed:
                        edge = road_ids[i]
                        if edge in closed: conn.edge.setDisallowed(edge, ['passenger'])
                        else: conn.edge.setAllowed(edge, ['passenger'])
                        limit = max(.1, float(speeds[k, i]/3.6))
                        conn.edge.setMaxSpeed(edge, limit)
                        weights[edge] = float(length_array[i]/limit)
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
                        measured = max(measured, float(length_array[index[edge]])/mean_speed)
                    estimate = s['travel_time_smoothing']*measured+(1-s['travel_time_smoothing'])*estimates[edge]
                    estimates[edge] = max(weights[edge], estimate)
                    conn.edge.adaptTraveltime(edge, estimates[edge])
                # Flood free-flow changes also apply to empty, unobserved edges.
                if wet and now % 900 == 0:
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
                    tau = float(tau_table[k, i])
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
            due = int(np.searchsorted(valid_departures, now+s['step_seconds'], side='right'))
            external = due-len(injected)
            balance = len(injected)-pending-running-arrived
            max_balance = max(max_balance, abs(balance))
            occupancy += (running+pending+external)*s['step_seconds']; external_area += external*s['step_seconds']
            if (now+s['step_seconds']) % s['output_seconds'] == 0:
                series.append({'time_s': now+s['step_seconds'], 'released_valid': due, 'injected': len(injected),
                               'arrived': arrived, 'running': running, 'sumo_pending': pending, 'external_pending': external,
                               'unfinished_released': running+pending+external, 'held': len(held),
                               'balance_error': balance, 'vehicle_seconds': occupancy})
            if (now+s['step_seconds']) % 3600 == 0:
                measured = time.perf_counter()
                memory = monitor.summary(hour_monitor_start) if monitor else {}
                hourly.append({'simulation_hour': (now+s['step_seconds'])//3600,
                    'wall_seconds': measured-hour_wall, 'cumulative_loop_wall_seconds': measured-start_wall,
                    'arrived': arrived, 'running': running, 'sumo_pending': pending, 'external_pending': external, **memory})
                pd.DataFrame(hourly).to_csv(folder/'hourly_performance.csv', index=False)
                print('HOUR', json.dumps(hourly[-1]), flush=True)
                hour_wall = measured
                hour_monitor_start = measured-monitor.started if monitor else 0.
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
                  geometry='Flat road/car OSG; no buildings, measured elevations or flood hydraulics',
                  sumo_startup_wall_seconds=startup_seconds, controller_init_wall_seconds=init_seconds,
                  route_query_stats=route_query_stats, headless=not gui)
    pd.DataFrame(series).to_csv(folder/'traffic_series.csv', index=False)
    pd.DataFrame(events).to_csv(folder/'injections.csv', index=False)
    pd.DataFrame(controls).to_csv(folder/'controls.csv', index=False)
    write_json(folder/'route_changes.json', changes); write_json(folder/'result.json', result)
    if max_balance or result['balance_error'] or result['injected_balance_error']: raise ValueError('SUMO vehicle accounting failed')
    if teleports: raise ValueError('unexpected SUMO teleport')
    return result


if __name__ == '__main__':
    main()

