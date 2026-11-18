"""Export real TraCI trajectories without modifying the archived experiment.

Run with the project Python. Three scenarios are replayed with the frozen controller;
the original accounting is compared before any viewer data is published.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import importlib.util
import json
import shutil
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import traci
import traci.constants as tc
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = 'data/processed/longgang_sumo/20261118T175153_sumo_492a503a'


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    path.write_bytes(data)
    path.with_suffix(path.suffix+'.gz').write_bytes(gzip.compress(data, compresslevel=6, mtime=0))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', default=DEFAULT)
    p.add_argument('--output', default='dashboard/digital-twin/data')
    args = p.parse_args()
    archived = ROOT / args.run
    output = ROOT / args.output
    replay = ROOT / 'data/processed' / ('digital_twin_replay_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))
    replay.mkdir(parents=True, exist_ok=False)
    for record in json.loads((archived/'inputs.json').read_text(encoding='utf-8')):
        if hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Archived input changed: '+record['path'])
        if record['path'] == 'scripts/run_longgang_sumo.py':
            if hashlib.sha256((archived/'provenance/run_longgang_sumo.py').read_bytes()).hexdigest() != record['sha256']:
                raise ValueError('Archived controller snapshot changed')
    shutil.copytree(archived / 'raw', replay / 'raw')
    cfg = yaml.safe_load((archived/'config.yaml').read_text(encoding='utf-8'))
    spec = importlib.util.spec_from_file_location('frozen_controller', archived/'provenance/run_longgang_sumo.py')
    controller = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(controller)
    controller.ROOT = ROOT
    edges = pd.read_csv(archived/'raw/source_sumo_mapping.csv')
    net = ET.parse(archived/'raw/network.net.xml').getroot()
    road_shapes = {e.attrib['id']: e.find('lane').attrib['shape'] for e in net.findall('edge') if e.attrib.get('function') != 'internal'}
    roads = []
    for row in edges.itertuples():
        pts = [[round(float(v), 2) for v in point.split(',')[:2]] for point in road_shapes[row.edge_id].split()]
        roads.append({'id': row.edge_id, 'points': pts, 'class': row.highway})
    states = np.load(archived/'raw/road_states.npz')
    depths = {name: np.where(np.isfinite(states[key]), states[key], -1).round(4).tolist()
              for name, key in [('rain_rolling', 'baseline'), ('governed_rolling', 'governed')]}
    window = json.loads((archived/'raw/window.json').read_text())
    junctions = [[[round(float(v),2) for v in point.split(',')[:2]] for point in j.attrib['shape'].split()]
                 for j in net.findall('junction') if j.attrib.get('shape') and j.attrib.get('type') != 'internal']
    dump(output/'network.json', {'roads': roads, 'junctions': junctions, 'depths': depths, 'window': window,
         'source_run': args.run, 'building_geometry': 'Procedural illustration; not measured buildings',
         'sample_seconds': 1, 'frame_columns': ['vehicle_index','x_m','y_m','angle_degrees','speed_m_s']})
    original_start = traci.start
    checks = {}
    for scenario in ['dry', 'rain_rolling', 'governed_rolling']:
        frames = [{'t': 0, 'v': []}]
        ids = []
        id_index = {}
        def start(*pos, **kw):
            result = original_start(*pos, **kw)
            conn = traci.getConnection(kw['label'])
            original_step, original_subscribe = conn.simulationStep, conn.vehicle.subscribe
            def subscribe(vid, variables, *a, **k):
                return original_subscribe(vid, list(variables)+[tc.VAR_POSITION, tc.VAR_ANGLE], *a, **k)
            def step(*a, **k):
                result = original_step(*a, **k)
                now = int(conn.simulation.getTime())
                if now % 1 == 0:
                    values = []
                    observed = dict(conn.vehicle.getAllSubscriptionResults())
                    # Newly departed vehicles have not been subscribed by the controller yet.
                    for vid in conn.simulation.getDepartedIDList():
                        observed[vid] = {tc.VAR_POSITION: conn.vehicle.getPosition(vid),
                                         tc.VAR_ANGLE: conn.vehicle.getAngle(vid),
                                         tc.VAR_SPEED: conn.vehicle.getSpeed(vid)}
                    for vid, value in observed.items():
                        if tc.VAR_POSITION not in value:
                            continue
                        if vid not in id_index:
                            id_index[vid] = len(ids)
                            ids.append(vid)
                        x, y = value[tc.VAR_POSITION]
                        values.append([id_index[vid], round(x, 2), round(y, 2), round(value[tc.VAR_ANGLE], 1), round(value[tc.VAR_SPEED], 2)])
                    frames.append({'t': now, 'v': values})
                return result
            conn.vehicle.subscribe = subscribe
            conn.simulationStep = step
            return result
        traci.start = start
        try:
            result = controller.simulate(replay, cfg, scenario)
        finally:
            traci.start = original_start
        expected = json.loads((archived/'cases'/scenario/'result.json').read_text())
        fields = ['planned', 'injected', 'arrived', 'running', 'sumo_pending', 'external_pending',
                  'vehicle_seconds', 'route_changes', 'teleports', 'collision_vehicle_events']
        checks[scenario] = {key: result[key] == expected[key] for key in fields if key in expected}
        if not all(checks[scenario].values()):
            raise ValueError('Replay accounting mismatch: '+scenario)
        series = pd.read_csv(replay/'cases'/scenario/'traffic_series.csv').to_dict('records')
        dump(output/(scenario+'.json'), {'sample_seconds': 1, 'ids': ids, 'frames': frames, 'series': series, 'result': result})
        print('EXPORTED', scenario, len(frames), len(ids), flush=True)
    dump(output/'audit.json', {'source_run': args.run, 'matches_archived_accounting': checks,
         'sampling': 'TraCI every 1 s; newly departed vehicles are captured using direct position/angle/speed queries',
         'visual_interpolation': 'Linear between consecutive samples for vehicles present in both; no invented trajectories'})


if __name__ == '__main__':
    main()
