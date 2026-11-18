"""Freeze a completed SUMO run and publish compact auditable evidence, not bulk data."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
from uftr.sumo_dynamic import write_json
from uftr.sumo_run import sumo_binary

ROOT = Path(__file__).resolve().parents[1]


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('run'); args = parser.parse_args()
    out = (ROOT/args.run).resolve(); destination = ROOT/'docs/validation/longgang_sumo'
    assert json.loads((out/'status.json').read_text())['status'] == 'complete'
    assert len(json.loads((out/'independent_audit.json').read_text())['scenarios']) == 5
    for name in ['audit_longgang_sumo.py', 'view_longgang_sumo.py', 'export_longgang_sumo_evidence.py']:
        shutil.copy2(ROOT/'scripts'/name, out/'provenance'/name)
    version = subprocess.check_output([str(sumo_binary('sumo-gui')), '--version'], text=True)
    (out/'sumo_version.txt').write_text(version, encoding='utf-8')
    files = [p for p in out.rglob('*') if p.is_file() and not p.relative_to(out).parts[0].startswith('preview_') and p.name != 'manifest.json']
    manifest = {'run': str(out.relative_to(ROOT)), 'scope': 'Longgang S0 3x3km ROI; scaled demand; uncalibrated',
                'files': [{'path': p.relative_to(out).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(files)],
                'preview_note': 'GUI preview folders are separate diagnostic reruns, excluded from numerical evidence. Screenshots preserved under docs/validation/longgang_sumo/figures.'}
    write_json(out/'manifest.json', manifest)
    copy = ['config.yaml', 'status.json', 'inputs.json', 'manifest.json', 'sumo_version.txt', 'comparison.csv', 'independent_audit.json',
            'raw/window.json', 'raw/plan_report.json', 'raw/boundary_demand_audit.json',
            'capacity_probe/discharge_comparison.csv', 'routing_probe/result.json']
    copy += [p.relative_to(out).as_posix() for p in (out/'cases').glob('*/result.json')]
    copy += [p.relative_to(out).as_posix() for p in (out/'cases').glob('*/traffic_series.csv')]
    copy += [p.relative_to(out).as_posix() for p in (out/'cases').glob('*/route_changes.json')]
    copy += [p.relative_to(out).as_posix() for p in (out/'figures').glob('*')]
    if (out/'gui_camera.json').exists(): copy.append('gui_camera.json')
    for relative in copy:
        target = destination/relative; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(out/relative, target)
    index = [{'path': p.relative_to(destination).as_posix(), 'sha256': digest(p)} for p in sorted(destination.rglob('*'))
             if p.is_file() and p.name != 'evidence_index.json']
    write_json(destination/'evidence_index.json', {'run': str(out.relative_to(ROOT)), 'files': index})
    print('Exported', len(index), 'evidence files')


if __name__ == '__main__': main()
