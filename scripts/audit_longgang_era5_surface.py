"""Independent array/ledger/raw-response/hash replay; does not import solver."""
from pathlib import Path
from datetime import datetime
import argparse
import hashlib
import json
import zipfile
import numpy as np
import pandas as pd
import yaml
from acquire_longgang_era5 import ROOT,sha,write


def audit(run):
    manifest=json.loads((run/'manifest.json').read_text(encoding='utf-8'))
    report=json.loads((run/'provenance/validation_report.json').read_text(encoding='utf-8'))
    cfg=yaml.safe_load((run/'provenance/longgang_era5_surface.yaml').read_text(encoding='utf-8'))
    for record in manifest['inputs']:
        if sha(ROOT/record['path'])!=record['sha256']:raise AssertionError('input changed '+record['path'])
    for record in manifest['outputs']:
        if sha(run/record['path'])!=record['sha256']:raise AssertionError('output changed '+record['path'])
    rain=ROOT/report['rainfall_package']
    data=np.load(rain/'hourly_rainfall.npz')
    response=json.loads((rain/'response.json').read_text(encoding='utf-8'))
    if isinstance(response,dict):response=[response]
    start=datetime.fromisoformat(cfg['rainfall']['simulation_start']).replace(tzinfo=None)
    end=datetime.fromisoformat(cfg['rainfall']['simulation_end']).replace(tzinfo=None)
    for j,item in enumerate(response):
        chosen=[(t,p) for t,p in zip(item['hourly']['time'],item['hourly']['precipitation'])
                if start<datetime.fromisoformat(t)<=end]
        np.testing.assert_array_equal(np.array([p for t,p in chosen]),data['precipitation_mm'][:,j])
        np.testing.assert_array_equal(np.array([t for t,p in chosen],dtype='datetime64[m]'),data['time_end_local'].astype('datetime64[m]'))
        assert item['utc_offset_seconds']==28800 and item['hourly_units']['precipitation']=='mm'
    grid=np.load(run/'raw/routing_grid.npz')
    receiver=grid['receiver'];rank=grid['rank'];spill=grid['spill_depth_m'];tau=grid['tau_s']
    rainidx=grid['rain_grid_id'];weights=grid['district_weights'];n=len(receiver)
    active=receiver>=0
    assert np.all(rank[receiver[active]]<rank[active])
    assert len(np.unique(rank))==n
    assert (spill>=0).all() and np.isfinite(spill).all()
    cellarea=cfg['domain']['cell_size_m']**2
    hourly=data['precipitation_mm'];district=(hourly@np.bincount(rainidx,weights=weights,minlength=hourly.shape[1]))/weights.sum()
    saved=pd.read_csv(run/'raw/hourly_rainfall.csv')
    np.testing.assert_allclose(saved.district_mean_mm,district,rtol=1e-12,atol=1e-12)
    ids=grid['source_feature_positions'];known=grid['modelled_features']
    summary=pd.read_csv(run/'raw/scenario_summary.csv').set_index('case')
    cubes={};ledger_max=0.;monotonic_checks=0
    count=0
    for name,case in cfg['cases'].items():
        item=np.load(run/f'raw/{name}_road_depth.npz')
        np.testing.assert_array_equal(item['source_feature_positions'],ids)
        np.testing.assert_array_equal(item['modelled_features'],known)
        a=item['depth_m'];cubes[name]=a
        assert np.isfinite(a[:,known]).all() and (a[:,known]>=0).all()
        assert np.isnan(a[:,~known]).all()
        count+=a[:,known].size
        assert np.isclose(float(a[:,known].max()),summary.loc[name,'maximum_ground_road_sample_depth_m'],rtol=0,atol=1e-12)
        assert (a>.15).sum(axis=1).max()==summary.loc[name,'maximum_modelled_source_features_over_015']
        ledger=pd.read_csv(run/f'raw/{name}_water_balance.csv')
        residual=ledger.storage_m3-ledger.storage_m3.iloc[0]-ledger.cumulative_rain_m3+ledger.cumulative_loss_m3+ledger.cumulative_boundary_outflow_m3
        ledger_max=max(ledger_max,float(abs(residual).max()))
        assert abs(residual).max()<max(1e-5,ledger.cumulative_rain_m3.max()*1e-10)
        for increments,total in [('rain_m3_interval','cumulative_rain_m3'),('loss_m3_interval','cumulative_loss_m3'),('boundary_outflow_m3_interval','cumulative_boundary_outflow_m3')]:
            np.testing.assert_allclose(ledger[increments].cumsum(),ledger[total],atol=1e-5,rtol=1e-12)
        expected=hourly[:,rainidx].sum()*case['rain_multiplier']*cellarea/1000
        assert np.isclose(ledger.cumulative_rain_m3.iloc[-1],expected,rtol=1e-12)
    assert (cubes['dry_control'][:,known]==0).all()
    for small,big in [('rainfall_070','era5_baseline'),('era5_baseline','rainfall_130'),('loss_double','era5_baseline'),('era5_baseline','loss_half')]:
        assert (cubes[small][:,known]<=cubes[big][:,known]+1e-7).all()
        monotonic_checks+=1
    # Recompute baseline using scatter-add rather than the solver's bincount.
    fields=np.load(run/'raw/baseline_depth_fields.npz')['depth_m']
    h=np.zeros(n,np.float64);dt=cfg['time']['internal_seconds'];period=cfg['time']['output_minutes']*60
    release=1-np.exp(-dt/tau)
    steps=len(hourly)*3600//dt
    maximum_replay=0.;endpoint=0;peak=np.zeros(n)
    loss_cap=cfg['loss']['capacity_mm_h']*dt/3600/1000
    for step in range(steps):
        h=h+hourly[(step*dt)//3600,rainidx]*dt/3600/1000
        h=np.maximum(0,h-loss_cap)
        flux=np.maximum(0,h-spill)*release
        next_h=h-flux
        np.add.at(next_h,receiver[active],flux[active])
        h=next_h;peak=np.maximum(peak,h)
        if (step+1)*dt%period==0:
            endpoint+=1
            maximum_replay=max(maximum_replay,float(abs(h-fields[endpoint]).max()))
    assert maximum_replay<1e-6
    peakfile=np.load(run/'raw/era5_baseline_grid_summary.npz')['peak_depth_m']
    np.testing.assert_allclose(peak,peakfile,rtol=1e-10,atol=1e-11)
    # Independently regenerate road max aggregation from full grid endpoints.
    samples=pd.read_parquet(run/'raw/road_sample_cells.parquet')
    pos={int(fid):j for j,fid in enumerate(ids)};roadcheck=0
    for fid,frame in samples.groupby('source_feature_position'):
        j=pos[int(fid)]
        expected=fields[:,frame.cell.unique()].max(axis=1)
        np.testing.assert_array_equal(expected,cubes['era5_baseline'][:,j])
        roadcheck+=len(expected)
    fine=np.load(run/'raw/verification_fine_road_depth.npz')['depth_m']
    diff=abs(fine[:,known]-cubes['era5_baseline'][:,known])
    assert float(diff.max())==report['time_step_check']['maximum_road_endpoint_difference_m']
    extended=np.load(run/'raw/verification_extended_road_depth.npz')['depth_m']
    bdiff=abs(extended[:,known]-cubes['era5_baseline'][:,known])
    assert float(bdiff.max())==report['boundary_sensitivity']['maximum_road_endpoint_difference_m']
    for name in ['verification_fine','verification_extended']:
        ledger=pd.read_csv(run/f'raw/{name}_water_balance.csv')
        residual=ledger.storage_m3-ledger.storage_m3.iloc[0]-ledger.cumulative_rain_m3+ledger.cumulative_loss_m3+ledger.cumulative_boundary_outflow_m3
        assert abs(residual).max()<max(1e-5,ledger.cumulative_rain_m3.max()*1e-10)
    zip_path=Path(str(run)+'.zip')
    with zipfile.ZipFile(zip_path) as archive:
        assert sorted(archive.namelist())==sorted(p.relative_to(run).as_posix() for p in run.rglob('*') if p.is_file())
        for name in archive.namelist():
            hsh=hashlib.sha256()
            with archive.open(name) as f:
                for b in iter(lambda:f.read(1024*1024),b''):hsh.update(b)
            assert hsh.hexdigest()==sha(run/name)
        zip_files=len(archive.namelist())
    result={'run_id':report['run_id'],'passed':True,'known_road_values_checked':count,
            'baseline_road_grid_aggregation_values_checked':roadcheck,
            'rain_values_rechecked_from_HTTP_response':int(hourly.size),
            'independent_baseline_grid_endpoints_replayed':int(fields.size),
            'maximum_replay_difference_m_float32_archive':maximum_replay,
            'maximum_cumulative_budget_residual_m3':ledger_max,
            'monotonic_sensitivity_checks':monotonic_checks,
            'input_hashes_checked':len(manifest['inputs']),'output_hashes_checked':len(manifest['outputs']),
            'zip_files_checked':zip_files,'zip_sha256':sha(zip_path),
            'manifest_sha256':sha(run/'manifest.json'),
            'note':'Numerical/data integrity only; no observed flood calibration or field validation.'}
    evidence=ROOT/'docs/validation/longgang_era5_surface';evidence.mkdir(exist_ok=True,parents=True)
    write(evidence/'independent_audit.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run');audit((ROOT/p.parse_args().run).resolve())
