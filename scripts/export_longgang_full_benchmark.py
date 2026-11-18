"""Seal a completed whole-district benchmark; publish compact evidence only."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
from uftr.sumo_dynamic import write_json
from uftr.sumo_run import sumo_binary

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024*1024), b''):
            h.update(data)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('run'); args = parser.parse_args()
    out = (ROOT/args.run).resolve()
    destination = ROOT/'docs/validation/longgang_sumo_full'
    if (out/'manifest.json').exists() or destination.exists():
        raise ValueError('Evidence already sealed; use a new run/destination rather than rewriting it')
    assert json.loads((out/'status.json').read_text())['status'] == 'complete'
    assert json.loads((out/'independent_audit.json').read_text())['headless_verified']
    for name in ['audit_longgang_full_benchmark.py', 'budget_longgang_full_benchmark.py',
                 'view_longgang_full_benchmark.py', 'export_longgang_full_benchmark.py']:
        shutil.copy2(ROOT/'scripts'/name, out/'provenance'/name)
    version = subprocess.check_output([str(sumo_binary('sumo')), '--version'], text=True)
    (out/'sumo_version.txt').write_text(version, encoding='utf-8')
    files = [p for p in out.rglob('*') if p.is_file() and p.name != 'manifest.json'
             and not p.relative_to(out).parts[0].startswith('preview_')]
    manifest = {'run': out.relative_to(ROOT).as_posix(), 'scope': 'Whole Longgang excluding Dapeng; buffer plus sampled complete dry paths; 5% synthetic demand; one dry headless baseline',
        'files': [{'path': p.relative_to(out).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in sorted(files)],
        'preview_note': 'Diagnostic GUI reruns excluded; not mixed with formal baseline or resource trace.'}
    write_json(out/'manifest.json', manifest)
    copies = ['config.yaml', 'inputs.json', 'manifest.json', 'status.json', 'hardware.json', 'preparation.json',
              'resources_summary.json', 'runtime_budget.json', 'independent_audit.json', 'sumo_version.txt', 'comparison.csv',
              'raw/scope.json', 'raw/window.json', 'raw/plan_report.json',
              'cases/dry/result.json', 'cases/dry/hourly_performance.csv', 'cases/dry/traffic_series.csv',
              'budget_probes/route_queries.csv', 'budget_probes/control_commands.csv',
              'budget_probes/duarouter_command.json', 'budget_probes/duarouter.log']
    copies += [p.relative_to(out).as_posix() for p in out.glob('resources_*.csv')]
    copies += [p.relative_to(out).as_posix() for p in (out/'figures').glob('*')]
    if (out/'tests.xml').exists():
        copies.append('tests.xml')
    for optional in ['storage_archives.json', 'gui_status.json']:
        if (out/optional).exists():
            copies.append(optional)
    for relative in copies:
        target = destination/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out/relative, target)
    evidence = [{'path': p.relative_to(destination).as_posix(), 'sha256': digest(p)}
                for p in sorted(destination.rglob('*')) if p.is_file()]
    write_json(destination/'evidence_index.json', {'run': out.relative_to(ROOT).as_posix(), 'files': evidence})
    print('Sealed', len(files), 'local files; exported', len(evidence), 'compact evidence files', flush=True)


if __name__ == '__main__':
    main()
