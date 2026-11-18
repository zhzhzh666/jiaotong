"""Replay the archived whole-district controller after the headless benchmark."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import time
import traci
import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('run')
    parser.add_argument('--preview-seconds', type=int)
    parser.add_argument('--camera-pause-seconds', type=int, default=0)
    args = parser.parse_args(); out = (ROOT/args.run).resolve()
    if not 0 <= args.camera_pause_seconds <= 60:
        raise ValueError('Camera pause must be in 0..60 seconds')
    cfg = yaml.safe_load((out/'config.yaml').read_text(encoding='utf-8'))
    if args.preview_seconds is not None:
        if not 300 <= args.preview_seconds <= cfg['simulation']['duration_seconds']:
            raise ValueError('Preview must be 300 seconds or longer and within the original run')
        cfg['simulation']['duration_seconds'] = args.preview_seconds
    for item in json.loads((out/'inputs.json').read_text(encoding='utf-8')):
        h = hashlib.sha256()
        with (ROOT/item['path']).open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                h.update(block)
        if h.hexdigest() != item['sha256']:
            raise ValueError('Replay source changed: '+item['path'])
    spec = importlib.util.spec_from_file_location('archived_full_district', out/'provenance/run_longgang_full_benchmark.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.ROOT = ROOT
    original_start = traci.start
    def start(*pos, **kw):
        pos = (list(pos[0])+['--quit-on-end', 'true'], *pos[1:])
        result = original_start(*pos, **kw)
        conn = traci.getConnection(kw['label']); original_step = conn.simulationStep
        camera = {'focused': False, 'diagnostic_preview_seconds': args.preview_seconds}
        def step(*p, **k):
            result = original_step(*p, **k)
            if not camera['focused'] and conn.simulation.getTime() >= 300:
                ids = list(conn.vehicle.getIDList())
                if ids:
                    vehicle = ids[len(ids)//2]
                    conn.gui.trackVehicle('View #0', vehicle)
                    conn.gui.setZoom('View #0', 1500.)
                    camera.update(focused=True, vehicle_id=vehicle, time_s=conn.simulation.getTime())
                    latest = max(out.glob('preview_dry_*'), key=lambda x: x.stat().st_mtime)
                    (latest/'camera.json').write_text(json.dumps(camera, indent=2), encoding='utf-8')
                    print('OSG CAMERA', json.dumps(camera), flush=True)
                    if args.camera_pause_seconds:
                        time.sleep(args.camera_pause_seconds)
            return result
        conn.simulationStep = step
        return result
    traci.start = start
    module.simulate(out, cfg, 'dry', gui=True)


if __name__ == '__main__':
    main()
