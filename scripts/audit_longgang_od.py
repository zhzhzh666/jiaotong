"""Independently check frozen Longgang OD deliverables without editing the run."""
from pathlib import Path
import argparse
import hashlib
import json
from zipfile import ZipFile
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('run', type=Path)
args = p.parse_args()
run = args.run.resolve()
report = json.loads((run/'demand_report.json').read_text(encoding='utf-8'))
manifest = json.loads((run/'manifest.json').read_text(encoding='utf-8'))
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()
hashes = 0
for group, base in [('inputs', ROOT), ('outputs', run)]:
    for item in manifest[group]:
        path = base/item['path']
        assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], path
        hashes += 1
with ZipFile(str(run)+'.zip') as z:
    assert z.testzip() is None
    files = {f.relative_to(run).as_posix(): f for f in run.rglob('*') if f.is_file()}
    assert set(z.namelist()) == set(files)
    for name, path in files.items():
        assert hashlib.sha256(z.read(name)).hexdigest() == sha(path), name
targets = pd.read_csv(run/'zone_marginal_targets.csv').set_index(['period','zone_id'])
matrices = {}
max_error = 0.
for period in report['periods']:
    frame = pd.read_csv(run/f'od_{period}_veh_h.csv', index_col=0)
    assert frame.shape == tuple(report['matrix_shape']) and frame.index.tolist() == frame.columns.tolist()
    matrix = frame.to_numpy()
    assert np.isfinite(matrix).all() and (matrix >= 0).all()
    t = targets.loc[period].reindex(frame.index)
    for actual, expected in [(matrix.sum(1),t.production_veh_h.to_numpy()),(matrix.sum(0),t.attraction_veh_h.to_numpy())]:
        error = np.max(np.abs(actual-expected)/np.maximum(expected,1e-12))
        max_error = max(max_error, float(error))
        assert error < 1e-9
    assert np.all(matrix[-12:,-12:] == 0)
    assert np.isclose(matrix.sum(), report['periods'][period]['total_veh_h'], rtol=1e-11)
    matrices[period] = matrix
intervals = pd.read_csv(run/'interval_totals.csv')
assert len(intervals) == 96
daily = np.zeros_like(matrix)
for row in intervals.itertuples():
    actual = pd.read_csv(run/'od_15min_base'/f'od_{row.start_time.replace(":", "")}_expected_trips.csv.gz', index_col=0).to_numpy()
    expected = matrices[row.period]*.25
    assert np.allclose(actual, expected, rtol=1e-10, atol=1e-10)
    assert np.isclose(actual.sum(), row.expected_vehicle_trips, rtol=1e-11)
    daily += actual
disk_daily = pd.read_csv(run/'od_daily_expected_trips.csv', index_col=0).to_numpy()
assert np.allclose(daily, disk_daily, rtol=1e-10, atol=1e-10)
assert np.isclose(daily.sum(), report['daily_expected_vehicle_trips']['base'], rtol=1e-11)
factors = {'offpeak':1., 'morning_peak':2., 'evening_peak':1.8}
od = pd.read_parquet(run/'od_all_periods.parquet')
assert not od.observed_od.any()
for period, factor in factors.items():
    rows = od[od.period == period]
    for status, value in rows.groupby('route_status').flow_veh_h.sum().items():
        assert np.isclose(value, report['periods'][period]['by_route_status_veh_h'][status])
    assert rows.loc[rows.route_status=='unreachable_normal_network','free_flow_with_access_s'].isna().all()
    assert np.allclose(matrices[period], matrices['offpeak']*factor, rtol=1e-10, atol=1e-10)
status = report['periods']['offpeak']['by_route_status_veh_h']
audit = {'run_id':run.name, 'all_checks_passed':True, 'input_output_hashes_verified':hashes,
         'zip_files_verified':len(files), 'all_96_intervals_read_back':True,
         'max_csv_relative_margin_error':max_error,
         'daily_route_status_expected_trips':{k:v*29.4 for k,v in status.items()},
         'route_status_fraction':{k:v/report['periods']['offpeak']['total_veh_h'] for k,v in status.items()},
         'zip_sha256':sha(Path(str(run)+'.zip'))}
validation = ROOT/'docs/validation/longgang_od'
validation.mkdir(exist_ok=True, parents=True)
for name in ['demand_report.json','manifest.json','network_report.json']:
    (validation/name).write_bytes((run/name).read_bytes())
(validation/'numerical_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False,indent=2))
