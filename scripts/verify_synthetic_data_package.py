"""Verify a frozen package and ZIP without rewriting either artifact."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
import argparse
import json

ROOT = Path(__file__).resolve().parents[1]


def verify(package):
    manifest_path = package / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    checked_inputs = 0
    input_basis = {'current_bytes': 0, 'recorded_provenance_snapshot': 0}
    for item in manifest['inputs']:
        path = ROOT / item['path']
        if path.is_file() and sha256(path.read_bytes()).hexdigest() == item['sha256']:
            input_basis['current_bytes'] += 1
        else:
            # Code/config may evolve; only accept frozen snapshot bytes whose
            # SHA exactly matches this original recorded input. Never apply to data.
            candidates = [package/'provenance'/path.name]
            if path.suffix=='.yaml':candidates.append(package/'provenance/config.yaml')
            assert path.suffix in {'.py','.yaml'} and any(
                p.is_file() and sha256(p.read_bytes()).hexdigest()==item['sha256'] for p in candidates), item['path']
            input_basis['recorded_provenance_snapshot'] += 1
        checked_inputs += 1
    members = {item['path'] for item in manifest['outputs']}
    assert {p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file()} == members | {'manifest.json'}
    archive_path = package.with_suffix('.zip')
    with ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {package.name + '/' + n for n in members | {'manifest.json'}}
        for item in manifest['outputs']:
            payload = (package / item['path']).read_bytes()
            assert len(payload) == item['bytes'], item['path']
            assert sha256(payload).hexdigest() == item['sha256'], item['path']
            assert archive.read(package.name + '/' + item['path']) == payload, item['path']
        assert archive.read(package.name + '/manifest.json') == manifest_path.read_bytes()
    validation = json.loads((package / 'provenance/validation_report.json').read_text(encoding='utf-8'))
    assert validation['all_checks_passed'] and all(validation['checks'].values())
    return {'package_id': package.name, 'source_kind': 'synthetic', 'observed': False,
            'input_sha256_checks': checked_inputs, 'output_sha256_checks': len(members),
            'input_verification_basis': input_basis,
            'zip_members_equal_local_files': True, 'zip_crc_passed': True,
            'generation_consistency_checks': validation.get('check_count', len(validation['checks'])),
            'manifest_sha256': sha256(manifest_path.read_bytes()).hexdigest(),
            'zip_bytes': archive_path.stat().st_size,
            'zip_sha256': sha256(archive_path.read_bytes()).hexdigest(),
            'all_checks_passed': True,
            'scope': 'Integrity and generation consistency only; no observational calibration or traffic reassignment'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    package = args.package or ROOT / json.loads((ROOT / 'docs/deliverables/content.json').read_text(encoding='utf-8'))['synthetic_data_package']['path']
    result = verify(package.resolve())
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding='utf-8')
    print(serialized)
