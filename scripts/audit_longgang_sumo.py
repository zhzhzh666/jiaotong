"""Independent replay of SUMO vehicle outcomes, occupancy and routed edge identity."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import sumolib
from uftr.sumo_run import sumo_binary
from uftr.sumo_dynamic import write_json, tau_proxy

ROOT = Path(__file__).resolve().parents[1]


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def routing_probe(out):
    """Controlled diamond proves an actual in-flight TraCI route change works."""
    import traci
    folder = out/'routing_probe'; folder.mkdir(exist_ok=True)
    if (folder/'result.json').exists(): return json.loads((folder/'result.json').read_text())
    nodes = ET.Element('nodes')
    for name, x, y in [('s', 0, 0), ('j', 500, 0), ('u', 750, 200), ('l', 750, -200), ('k', 1000, 0), ('t', 1500, 0)]:
        ET.SubElement(nodes, 'node', id=name, x=str(x), y=str(y))
    edges = ET.Element('edges')
    for name, a, b in [('a', 's', 'j'), ('b', 'j', 'u'), ('b2', 'u', 'k'), ('c', 'j', 'l'), ('c2', 'l', 'k'), ('d', 'k', 't')]:
        ET.SubElement(edges, 'edge', id=name, **{'from': a, 'to': b, 'speed': '10', 'numLanes': '1'})
    ET.ElementTree(nodes).write(folder/'nodes.xml'); ET.ElementTree(edges).write(folder/'edges.xml')
    subprocess.run([str(sumo_binary('netconvert')), '-n', str(folder/'nodes.xml'), '-e', str(folder/'edges.xml'),
                    '-o', str(folder/'network.net.xml')], capture_output=True, check=True)
    routes = ET.Element('routes'); ET.SubElement(routes, 'vType', id='car', vClass='passenger')
    ET.SubElement(routes, 'route', id='old', edges='a b b2 d')
    ET.SubElement(routes, 'vehicle', id='probe', type='car', route='old', depart='0')
    ET.ElementTree(routes).write(folder/'routes.xml')
    traci.start([str(sumo_binary('sumo')), '-n', str(folder/'network.net.xml'), '-r', str(folder/'routes.xml'),
                 '--no-step-log', 'true', '--time-to-teleport', '-1', '--seed', '42'], label='longgang_routing_probe')
    conn = traci.getConnection('longgang_routing_probe')
    try:
        conn.simulationStep(10.)
        before = list(conn.vehicle.getRoute('probe')); current = conn.vehicle.getRoadID('probe')
        conn.edge.setDisallowed('b', ['passenger'])
        alternative = list(conn.simulation.findRoute(current, 'd', vType='car', depart=10).edges)
        assert 'b' not in alternative and 'c' in alternative
        conn.vehicle.setRoute('probe', alternative)
        after = list(conn.vehicle.getRoute('probe')); arrived = 0; teleports = 0
        for _ in range(250):
            conn.simulationStep(); arrived += conn.simulation.getArrivedNumber(); teleports += conn.simulation.getStartingTeleportNumber()
        assert arrived == 1 and teleports == 0 and before != after
    finally: conn.close()
    report = {'source_kind': 'Synthetic diamond functional fixture, not Longgang benefit',
              'closure_time_s': 10, 'closed_edge': 'b', 'before': before, 'after': after,
              'arrived': arrived, 'teleports': teleports, 'passed': True}
    write_json(folder/'result.json', report); return report


def capacity_probe(out):
    """Saturated single road measures the proxy; it need not match target capacity."""
    folder = out/'capacity_probe'; folder.mkdir(exist_ok=False)
    ET.ElementTree(ET.fromstring('<nodes><node id="a" x="0" y="0"/><node id="b" x="500" y="0"/></nodes>')).write(folder/'nodes.xml')
    reports = []
    for h in [0., .1, .2]:
        w = h*1000
        v = 50. if h == 0 else min(50., .0009*w*w-.5529*w+86.9448)
        factor = max(.2, 1-.75*h/.3); tau = tau_proxy(1600, 50/3.6, factor)
        label = f'depth{int(h*100):02d}'
        ET.ElementTree(ET.fromstring(f'<edges><edge id="e" from="a" to="b" speed="{v/3.6}" numLanes="1"/></edges>')).write(folder/(label+'_edges.xml'))
        subprocess.run([str(sumo_binary('netconvert')), '-n', str(folder/'nodes.xml'), '-e', str(folder/(label+'_edges.xml')),
                        '-o', str(folder/(label+'.net.xml'))], capture_output=True, check=True)
        routes = ET.Element('routes'); ET.SubElement(routes, 'vType', id='car', tau=str(tau), length='5', minGap='2.5', sigma='0.5')
        ET.SubElement(routes, 'route', id='r', edges='e')
        for i in range(2000): ET.SubElement(routes, 'vehicle', id=f'v{i}', type='car', route='r', depart='0')
        ET.ElementTree(routes).write(folder/(label+'.rou.xml'))
        trip = folder/(label+'_tripinfo.xml')
        run = subprocess.run([str(sumo_binary('sumo')), '-n', str(folder/(label+'.net.xml')), '-r', str(folder/(label+'.rou.xml')),
                              '--end', '1200', '--step-length', '1', '--seed', '42', '--time-to-teleport', '-1',
                              '--no-step-log', 'true', '--tripinfo-output', str(trip)], capture_output=True, text=True)
        (folder/(label+'.log')).write_text(run.stdout+'\n'+run.stderr, encoding='utf-8')
        if run.returncode: raise RuntimeError('capacity probe failed')
        arrivals = np.array([float(t.attrib['arrival']) for t in ET.parse(trip).getroot().findall('tripinfo')])
        discharge = int(np.count_nonzero((arrivals >= 600) & (arrivals < 1200)))*6
        reports.append({'depth_m': h, 'speed_kph': v, 'tau_s': tau, 'reference_capacity_veh_h': 1600*factor,
                        'observed_discharge_veh_h_600_to_1200': discharge,
                        'relative_capacity_difference': discharge/(1600*factor)-1})
    pd.DataFrame(reports).to_csv(folder/'discharge_comparison.csv', index=False)
    return reports


def audit(out, probe=True):
    plan = pd.read_csv(out/'raw/departure_plan.csv'); network = sumolib.net.readNet(str(out/'raw/network.net.xml'))
    mapping = pd.read_csv(out/'raw/source_sumo_mapping.csv'); ids = set(mapping.edge_id)
    assert {e.getID() for e in network.getEdges()} == ids
    for row in plan.itertuples():
        route = row.normal_route.split()
        assert set(route) <= ids
        assert all(network.getEdge(a).getConnections(network.getEdge(b)) for a, b in zip(route, route[1:]))
    sources = json.loads((out/'inputs.json').read_text(encoding='utf-8'))
    for source in sources: assert digest(ROOT/source['path']) == source['sha256'], source['path']
    source_index = {Path(s['path']).name: ROOT/s['path'] for s in sources}
    connectors = pd.read_csv(source_index['zone_connectors.csv'])
    connected = connectors.node_id.notna().to_numpy(); intra = np.eye(len(connected), dtype=bool)
    matrix = np.load(source_index['od_sensitivity_veh_h.npz'])['base__offpeak']
    eligible = connected[:, None] & connected[None, :] & ~intra
    boundary = json.loads((out/'raw/boundary_demand_audit.json').read_text(encoding='utf-8'))
    assert np.isclose(matrix[eligible].sum(), boundary['eligible_offpeak_veh_h'])
    demand_ledger = {'full_offpeak_veh_h': float(matrix.sum()), 'eligible_offpeak_veh_h': float(matrix[eligible].sum()),
                     'missing_connector_offpeak_veh_h': float(matrix[~eligible & ~intra].sum()),
                     'intrazonal_offpeak_veh_h': float(np.trace(matrix)),
                     'note': 'ROI uses visits of eligible normal routes; disconnected, nonintersecting, intrazonal and missing-connector demand remain in full-OD ledger, not fabricated SUMO trips.'}
    start = json.loads((out/'raw/window.json').read_text(encoding='utf-8'))['start_interval']
    road_states = np.load(out/'raw/road_states.npz')
    feature_order = np.load(source_index['routing_grid.npz'])['source_feature_positions']
    feature_lookup = {int(f): i for i, f in enumerate(feature_order)}
    for mask, key in [(0, 'baseline'), (9, 'governed')]:
        water = np.load(source_index[f'mask{mask:02d}_rain130_water.npz'])['depth_m']
        expected = np.full_like(road_states[key], np.nan)
        for i, feature in enumerate(mapping.depth_feature_position):
            if feature in feature_lookup: expected[:, i] = water[start:start+len(expected), feature_lookup[feature]]
        assert np.array_equal(expected, road_states[key], equal_nan=True)
    reports = []
    for folder in sorted((out/'cases').iterdir()):
        result = json.loads((folder/'result.json').read_text(encoding='utf-8'))
        series = pd.read_csv(folder/'traffic_series.csv'); end = result['duration_seconds']
        trips = {r.attrib['id']: r.attrib for r in ET.parse(folder/'tripinfo.xml').getroot().findall('tripinfo')}
        complete = {key: float(r['arrival']) for key, r in trips.items() if float(r['arrival']) >= 0}
        assert len(complete) == result['arrived']
        assert result['planned'] == len(plan)
        assert result['planned'] == result['invalid']+result['external_pending']+result['sumo_pending']+result['running']+result['arrived']
        assert np.all(series.injected == series.arrived+series.running+series.sumo_pending)
        assert np.all(series.released_valid == series.arrived+series.running+series.sumo_pending+series.external_pending)
        # Right-endpoint occupancy includes the release endpoint. SUMO arrival
        # timestamps name the beginning of the step in which it reports arrival.
        independent = sum((complete.get(r.vehicle_id, end)+1-np.ceil(r.depart_s)) for r in plan.itertuples() if r.valid)
        assert abs(independent-result['vehicle_seconds']) < 1e-6
        assert result['teleports'] == 0
        changes = json.loads((folder/'route_changes.json').read_text(encoding='utf-8'))
        assert len(changes) == result['route_changes']
        for event in changes:
            route = event['new']
            assert set(route) <= ids
            assert all(network.getEdge(a).getConnections(network.getEdge(b)) for a, b in zip(route, route[1:]))
        reports.append({'scenario': result['scenario'], 'planned': len(plan), 'arrived': len(complete),
                        'vehicle_seconds_replayed': float(independent), 'route_changes_checked': len(changes),
                        'vehicle_balance_error': result['balance_error'], 'teleports': result['teleports'],
                        'collision_vehicle_events': result['collision_vehicle_events']})
    report = {'source_sha_verified': len(sources), 'source_sumo_arcs': len(ids), 'planned_routes_checked': len(plan),
              'road_depth_values_checked': int(2*road_states['baseline'].size), 'full_od_ledger': demand_ledger,
              'scenarios': reports, 'note': 'Numerical/network consistency, not observed traffic validation.'}
    if probe: report['capacity_probe'] = capacity_probe(out)
    elif (out/'capacity_probe/discharge_comparison.csv').exists():
        report['capacity_probe'] = pd.read_csv(out/'capacity_probe/discharge_comparison.csv').to_dict('records')
    report['routing_probe'] = routing_probe(out)
    write_json(out/'independent_audit.json', report)
    return report


def figures(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    folder = out/'figures'; folder.mkdir(exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, layout='constrained')
    for case in sorted((out/'cases').iterdir()):
        q = pd.read_csv(case/'traffic_series.csv')
        style = '--' if 'rolling' in case.name else '-'
        axes[0].plot(q.time_s/3600, q.arrived, style, label=case.name)
        axes[1].plot(q.time_s/3600, q.external_pending+q.running+q.sumo_pending, style, label=case.name)
    axes[0].set(ylabel='Completed vehicles', title='Longgang 3x3 km SUMO pilot | 5% synthetic boundary-visit demand')
    axes[1].set(xlabel='Simulation hour (last hour: no new planned departures)', ylabel='Released but unfinished vehicles')
    for ax in axes: ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.savefig(folder/'traffic_comparison.png', dpi=160); fig.savefig(folder/'traffic_comparison.svg'); plt.close(fig)
    net = sumolib.net.readNet(str(out/'raw/network.net.xml'))
    mapping = pd.read_csv(out/'raw/source_sumo_mapping.csv')
    depth = np.load(out/'raw/road_states.npz')['baseline']; peak = np.nanmax(np.where(np.isfinite(depth), depth, -np.inf), axis=0)
    peak[~np.isfinite(peak)] = np.nan
    lines = [net.getEdge(e).getShape() for e in mapping.edge_id]
    fig, ax = plt.subplots(figsize=(9, 8), layout='constrained')
    cmap = plt.get_cmap('YlOrRd').copy(); cmap.set_bad('#888888')
    collection = LineCollection(lines, array=np.ma.masked_invalid(np.minimum(peak, .5)), cmap=cmap, linewidths=.8)
    collection.set_clim(0, .5); ax.add_collection(collection); ax.autoscale(); ax.set_aspect('equal')
    ax.set(title='Untreated 1.3x rain | maximum estimated depth in selected window', xlabel='Local east (m)', ylabel='Local north (m)')
    fig.colorbar(collection, ax=ax, label='Modelled depth (m), clipped at 0.5; grey = unknown')
    fig.savefig(folder/'road_exposure.png', dpi=160); fig.savefig(folder/'road_exposure.svg'); plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('run'); parser.add_argument('--no-probe', action='store_true')
    args = parser.parse_args(); path = (ROOT/args.run).resolve()
    print(json.dumps(audit(path, not args.no_probe), ensure_ascii=False, indent=2)); figures(path)
