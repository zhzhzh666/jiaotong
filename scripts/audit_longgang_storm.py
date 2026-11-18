"""Audit frozen rainfall/storage/exposure arrays without changing the model run."""
from pathlib import Path
from zipfile import ZipFile
import argparse
import hashlib
import json
import shutil
import numpy as np
import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('run',type=Path);args=p.parse_args();run=args.run.resolve()
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
report=json.loads((run/'provenance/validation_report.json').read_text(encoding='utf-8'))
manifest=json.loads((run/'manifest.json').read_text(encoding='utf-8'))
assert report['all_checks_passed'] and all(report['checks'].values())
hashes=0
for group,base in [('inputs',ROOT),('outputs',run)]:
    for item in manifest[group]:
        path=base/item['path']
        assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],path
        hashes+=1
with ZipFile(str(run)+'.zip') as z:
    files={p.relative_to(run).as_posix():p for p in run.rglob('*') if p.is_file()}
    assert set(z.namelist())==set(files)
    for name,path in files.items():
        h=hashlib.sha256()
        with z.open(name) as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        assert h.hexdigest()==sha(path),name
cfg=yaml.safe_load((run/'provenance/longgang_storm.yaml').read_text(encoding='utf-8'))
params=pd.read_csv(run/'raw/site_parameters.csv');features=pd.read_csv(run/'raw/road_feature_status.csv')
links=pd.read_csv(run/'raw/site_road_links.csv');rain=pd.read_csv(run/'raw/reference_rainfall.csv')
summary=pd.read_csv(run/'raw/scenario_summary.csv').set_index(['case','scenario'])
si={v:i for i,v in enumerate(params.site_id)};fi={v:i for i,v in enumerate(features.source_feature_position)}
groups={fi[fid]:[si[s] for s in frame.site_id] for fid,frame in links.groupby('source_feature_position')}
modeled=features.valid_sample_count.to_numpy()>0;dt=cfg['interval_minutes']/60
max_recurrence=max_drainage=max_dry_error=max_aggregate=0.;points=0
for case,settings in cfg['cases'].items():
    for scenario,total in cfg['rainfall']['total_mm'].items():
        depth=pd.read_parquet(run/f'raw/site_depths/{case}__{scenario}.parquet')
        n=len(params);h=depth.depth_m.to_numpy().reshape(-1,n);times=depth.time_h.to_numpy().reshape(-1,n)[:,0]
        assert np.array_equal(depth.site_id.to_numpy().reshape(-1,n)[0],params.site_id)
        assert np.allclose(times,np.arange(97)*dt) and not depth.observed.any()
        balance=pd.read_parquet(run/f'raw/balance/{case}__{scenario}.parquet')
        rain_array=balance.rain_mm_interval.to_numpy().reshape(96,n)
        expected_rain=rain[rain.scenario.eq(scenario)].rain_mm_interval.to_numpy()[:,None]*params.rain_spatial_factor.to_numpy()[None,:]
        assert np.allclose(rain_array,expected_rain,rtol=1e-12,atol=1e-12)
        assert np.isclose(rain_array.sum(0).mean(),total)
        inflow=rain_array*params.runoff_coefficient.to_numpy()*params.hypothetical_concentration_ratio.to_numpy()
        c=params.drainage_mm_h.to_numpy()*settings['drainage_multiplier']
        tau=params.recession_tau_h.to_numpy()*settings['recession_multiplier']
        predicted_drain=np.minimum(h[:-1]*1000+inflow,c*dt+h[:-1]*1000*dt/tau)
        expected_next=(h[:-1]*1000+inflow-predicted_drain)/1000
        max_recurrence=max(max_recurrence,float(abs(expected_next-h[1:]).max()))
        max_drainage=max(max_drainage,float(abs(predicted_drain-balance.drained_mm.to_numpy().reshape(96,n)).max()))
        assert np.allclose(inflow,balance.inflow_mm.to_numpy().reshape(96,n),rtol=1e-12,atol=1e-10)
        assert np.allclose(np.diff(h,axis=0)*1000,balance.storage_change_mm.to_numpy().reshape(96,n),rtol=1e-12,atol=1e-10)
        stop=round(cfg['rainfall']['event_end_hour']/dt)
        k=np.arange(len(h)-stop)[:,None]
        closed_form=np.maximum((h[stop]*1000+c*tau)*(1-dt/tau)**k-c*tau,0)/1000
        max_dry_error=max(max_dry_error,float(abs(h[stop:]-closed_form).max()))
        saved=np.load(run/f'raw/road_depths/{case}__{scenario}.npz')
        actual=saved['depth_m'];assert np.array_equal(saved['source_feature_positions'],features.source_feature_position)
        assert np.array_equal(saved['modelled_features'],modeled)
        assert np.isnan(actual[:,~modeled]).all()
        expected=np.full_like(actual,np.nan)
        for j,indices in groups.items():expected[:,j]=h[:,indices].max(1)
        max_aggregate=max(max_aggregate,float(abs(actual[:,modeled]-expected[:,modeled]).max()))
        s=summary.loc[case,scenario]
        assert np.isclose(s.peak_depth_m,h.max())
        assert s.max_source_features_atleast_030==int((actual>=.3).sum(1).max())
        if case=='baseline':
            long=pd.read_parquet(run/f'raw/road_depths/baseline__{scenario}.parquet')
            assert np.allclose(actual,long.depth_m.to_numpy().reshape(actual.shape),equal_nan=True)
        points+=h.size
assert max_recurrence<1e-12 and max_drainage<1e-9 and max_dry_error<1e-12 and max_aggregate<1e-12
thresholds=pd.read_csv(run/'raw/site_threshold_metrics.csv')
assert thresholds.loc[thresholds.status.ne('recovered'),'recovery_hour'].isna().all()
assert thresholds.duration_above_h.between(0,24).all()
audit={'run_id':run.name,'all_checks_passed':True,'hashes_verified':hashes,'zip_files_verified':len(files),
    'case_scenario_combinations_audited':len(cfg['cases'])*len(cfg['rainfall']['total_mm']),
    'site_endpoint_values_audited':points,'max_recurrence_error_m':max_recurrence,
    'max_drainage_error_mm':max_drainage,'max_closed_form_dry_recession_error_m':max_dry_error,
    'max_source_road_aggregation_error_m':max_aggregate,'zip_sha256':sha(Path(str(run)+'.zip'))}
dest=ROOT/'docs/validation/longgang_storm';dest.mkdir(parents=True,exist_ok=True)
for name,source in {'validation_report.json':'provenance/validation_report.json','manifest.json':'manifest.json',
    'scenario_summary.csv':'raw/scenario_summary.csv','time_step_check.csv':'raw/time_step_check.csv'}.items():shutil.copy2(run/source,dest/name)
shutil.copy2(ROOT/'.cache/longgang_storm_tests.xml',dest/'tests.xml')
for file in (run/'figures').glob('*.png'):shutil.copy2(file,dest/file.name)
(dest/'numerical_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False,indent=2))
