"""Replay the archived controller in an OSG view and focus a live SUMO vehicle.

This launches the actual TraCI simulation, not an empty sumocfg-only animation.
Camera commands affect visualization only; archived solver sources stay unchanged.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import time
import yaml
import traci

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(); p.add_argument('run'); p.add_argument('--scenario', default='dry')
    p.add_argument('--camera-pause-seconds', type=int, default=0)
    args = p.parse_args(); out = (ROOT/args.run).resolve()
    if not 0 <= args.camera_pause_seconds <= 60: raise ValueError('camera pause must be between 0 and 60 seconds')
    cfg = yaml.safe_load((out/'config.yaml').read_text(encoding='utf-8'))
    for record in json.loads((out/'inputs.json').read_text(encoding='utf-8')):
        if hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Changed replay input: '+record['path'])
    spec = importlib.util.spec_from_file_location('archived_longgang_controller', out/'provenance/run_longgang_sumo.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); module.ROOT = ROOT
    if args.scenario not in module.CASES: raise ValueError('invalid replay scenario')
    start_original = traci.start
    def start(*pos, **kw):
        result = start_original(*pos, **kw)
        connection = traci.getConnection(kw['label']); original_step = connection.simulationStep
        camera = {'focused': False}
        def step(*step_pos, **step_kw):
            result = original_step(*step_pos, **step_kw)
            if not camera['focused'] and connection.simulation.getTime() >= 300:
                vehicles = list(connection.vehicle.getIDList())
                if vehicles:
                    vehicle = vehicles[len(vehicles)//2]
                    connection.gui.trackVehicle('View #0', vehicle)
                    connection.gui.setZoom('View #0', 1500.)
                    camera.update(focused=True, vehicle_id=vehicle, time_s=connection.simulation.getTime(),
                                  requested_zoom=1500., returned_zoom=connection.gui.getZoom('View #0'))
                    (out/'gui_camera.json').write_text(json.dumps(camera, indent=2), encoding='utf-8')
                    print('OSG CAMERA', json.dumps(camera), flush=True)
                    if args.camera_pause_seconds: time.sleep(args.camera_pause_seconds)
            return result
        connection.simulationStep = step
        return result
    traci.start = start
    module.simulate(out, cfg, args.scenario, gui=True)


if __name__ == '__main__': main()
