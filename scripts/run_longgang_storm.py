"""Build a new, offline Longgang synthetic rainfall/ponding/road-exposure run."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import hashlib
import json
import shutil
import time
import traceback
import uuid
import zipfile
import geopandas as gpd
import numpy as np
import pandas as pd
import yaml
from uftr.longgang_storm import rain_profile,rain_factors,make_road_sites,aggregate_road_depth,graph_road_identities
from uftr.storm_process import simulate_ponding,threshold_metrics
from uftr.spatial import clip_rasters

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def write(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def build(config):
    started=time.time();cfg=yaml.safe_load(config.read_text(encoding='utf-8'))
    if cfg['region']!='longgang' or cfg['include_dapeng'] is not False:raise ValueError('wrong study scope')
    name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_longgang_storm_'+uuid.uuid4().hex[:8]
    out=ROOT/cfg['output_root']/name;out.mkdir(parents=True,exist_ok=False)
    for sub in ['gis','raw','raw/site_depths','raw/road_depths','raw/balance','figures','provenance']:(out/sub).mkdir()
    print('OUTPUT '+str(out),flush=True);write(out/'status.json',{'status':'running','observed':False})
    try:
        od=ROOT/cfg['od_package'];frozen=json.loads((od/'manifest.json').read_text(encoding='utf-8'))
        recorded={r['path']:r['sha256'] for r in frozen['outputs']}
        for file in ['inferred_source_network.graphml','study_boundary.geojson','config.yaml']:
            assert sha(od/file)==recorded[file],file
        netcfg=yaml.safe_load((od/'config.yaml').read_text(encoding='utf-8'))['network']
        source=ROOT/cfg['source_roads'];dsm=ROOT/cfg['dsm']
        assert any(Path(r['path']).as_posix()==Path(cfg['source_roads']).as_posix() and r['sha256']==sha(source) for r in frozen['inputs'])
        boundary=gpd.read_file(od/'study_boundary.geojson');assert not boundary.include_dapeng.any()
        polygon=boundary.geometry.union_all();boundary.to_file(out/'gis/study_boundary.geojson',driver='GeoJSON')
        print('Clipping DSM; sampling ground roads on 250m proxy grid',flush=True)
        terrain=clip_rasters([dsm],polygon,out/'gis/longgang_dsm_30m.tif')
        roads=gpd.read_file(source,layer=cfg['road_layer'])
        sites,features,links,samples=make_road_sites(roads,polygon,dsm,cfg['spatial'],netcfg)
        print(f'{len(sites)} proxy sites; {len(features)} accepted source road features',flush=True)
        site=sites.copy();p=cfg['ponding'];low=site.local_low_score.to_numpy()
        site['rain_spatial_factor']=rain_factors(np.c_[site.x_m,site.y_m],cfg['rainfall'],cfg['seed'])
        site['runoff_coefficient']=p['runoff_coefficient']
        site['hypothetical_concentration_ratio']=p['concentration_ratio_min']+p['concentration_ratio_span']*low
        site['drainage_mm_h']=p['drainage_min_mm_h']+p['drainage_span_mm_h']*(1-low)
        site['recession_tau_h']=p['recession_tau_h']
        site.to_crs(4326).to_file(out/'gis/flood_proxy_sites.geojson',driver='GeoJSON')
        site.drop(columns='geometry').to_csv(out/'raw/site_parameters.csv',index=False,encoding='utf-8-sig')
        features.to_crs(4326).to_file(out/'gis/road_features.geojson',driver='GeoJSON')
        features.drop(columns='geometry').to_csv(out/'raw/road_feature_status.csv',index=False,encoding='utf-8-sig')
        links.to_csv(out/'raw/site_road_links.csv',index=False)
        samples.to_parquet(out/'raw/road_sample_coverage.parquet',index=False)
        print('Reading exact directed arc identities from frozen OD graph',flush=True)
        arcs=graph_road_identities(od/'inferred_source_network.graphml',roads,polygon,features.source_feature_position)
        arcs=arcs.merge(features.drop(columns='geometry')[['source_feature_position','status']],on='source_feature_position',validate='many_to_one')
        arcs.to_csv(out/'raw/od_graph_arc_mapping.csv',index=False)
        dt=cfg['interval_minutes']/60;endpoints=np.arange(round(cfg['duration_hours']/dt)+1)*dt
        rain=rain_profile(cfg['duration_hours'],dt,cfg['rainfall'])
        rain.to_csv(out/'raw/reference_rainfall.csv',index=False,encoding='utf-8-sig')
        arrays={};summaries=[];metrics=[];road_metrics=[];step=[]
        maximum_residual=event_residual=0.;max_road_replay=0.
        modeled=features.valid_sample_count.gt(0).to_numpy()
        feature_ids=features.source_feature_position.to_numpy();site_ids=site.site_id.to_numpy()
        for case,settings in cfg['cases'].items():
            for scenario,total in cfg['rainfall']['total_mm'].items():
                print(f'Simulating {case} / {scenario}',flush=True)
                reference=rain[rain.scenario.eq(scenario)].rain_mm_interval.to_numpy()
                rainfall=reference[:,None]*site.rain_spatial_factor.to_numpy()[None,:]
                arguments=(site.runoff_coefficient.to_numpy(),site.hypothetical_concentration_ratio.to_numpy(),
                    site.drainage_mm_h.to_numpy()*settings['drainage_multiplier'],site.recession_tau_h.to_numpy()*settings['recession_multiplier'])
                result=simulate_ponding(rainfall,dt,*arguments);h=result['depth_m'];arrays[case,scenario]=h
                maximum_residual=max(maximum_residual,float(abs(result['balance_residual_mm']).max()))
                event=h[-1]*1000-result['inflow_mm'].sum(0)+result['drained_mm'].sum(0)
                event_residual=max(event_residual,float(abs(event).max()))
                pd.DataFrame({'time_h':np.repeat(endpoints,len(site)), 'site_id':np.tile(site_ids,len(endpoints)),
                    'depth_m':h.ravel(),'observed':False}).to_parquet(out/f'raw/site_depths/{case}__{scenario}.parquet',index=False)
                pd.DataFrame({'start_h':np.repeat(endpoints[:-1],len(site)),'site_id':np.tile(site_ids,len(endpoints)-1),
                    'rain_mm_interval':rainfall.ravel(),'inflow_mm':result['inflow_mm'].ravel(),
                    'drained_mm':result['drained_mm'].ravel(),'storage_change_mm':(np.diff(h,axis=0)*1000).ravel()}).to_parquet(out/f'raw/balance/{case}__{scenario}.parquet',index=False)
                road=aggregate_road_depth(h,site,features,links)
                assert np.isfinite(road[:,modeled]).all() and np.isnan(road[:,~modeled]).all()
                # Full endpoint matrix; indices align with the exact source-feature positions.
                np.savez_compressed(out/f'raw/road_depths/{case}__{scenario}.npz',time_h=endpoints,
                    source_feature_positions=feature_ids,depth_m=road,modelled_features=modeled,
                    source_kind=np.array('synthetic_max_grid_proxy_not_observed'),observed=np.array(False))
                if case=='baseline':
                    pd.DataFrame({'time_h':np.repeat(endpoints,len(features)),
                        'source_feature_position':np.tile(feature_ids,len(endpoints)),'depth_m':road.ravel(),
                        'depth_status':np.tile(features.status.to_numpy(),len(endpoints)),'observed':False}).to_parquet(out/f'raw/road_depths/baseline__{scenario}.parquet',index=False)
                    fine=simulate_ponding(np.repeat(rainfall/3,3,axis=0),dt/3,*arguments)['depth_m'][::3]
                    diff=abs(fine-h)
                    step.append({'scenario':scenario,'max_endpoint_difference_m':float(diff.max()),
                        'median_endpoint_difference_m':float(np.median(diff)),
                        'coarse_peak_m':float(h.max()),'fine_peak_at_common_endpoints_m':float(fine.max()),
                        'fine_rainfall_assumption':'15min rain uniformly split into three 5min intervals'})
                local=[]
                for j,pid in enumerate(site_ids):
                    for threshold in cfg['thresholds_m']:
                        m=threshold_metrics(endpoints,h[:,j],threshold)
                        row={'case':case,'scenario':scenario,'site_id':pid,'peak_depth_m':float(h[:,j].max()),
                            'first_peak_h':float(endpoints[h[:,j].argmax()]),**m,'observed':False}
                        metrics.append(row);local.append(row)
                local=pd.DataFrame(local);recovery=local[np.isclose(local.threshold_m,cfg['recovery_threshold_m'])]
                risk=local[np.isclose(local.threshold_m,.15)]
                if case=='baseline':
                    for j,fid in enumerate(feature_ids):
                        for threshold in cfg['thresholds_m']:
                            m=threshold_metrics(endpoints,road[:,j],threshold) if modeled[j] else {
                                'threshold_m':threshold,'duration_above_h':None,'recovery_hour':None,
                                'hours_after_peak':None,'status':'not_modelled'}
                            road_metrics.append({'scenario':scenario,'source_feature_position':int(fid),
                                'peak_depth_m':float(road[:,j].max()) if modeled[j] else None,**m,'observed':False})
                peak=np.unravel_index(h.argmax(),h.shape)
                n15=(road>.15).sum(1);n30=(road>=.30).sum(1)
                summaries.append({'case':case,'scenario':scenario,'reference_rain_mm':total,
                    'peak_depth_m':float(h.max()),'peak_site_id':site_ids[peak[1]],'first_peak_h':float(endpoints[peak[0]]),
                    'max_sites_above_015':int((h>.15).sum(1).max()),'max_source_features_above_015':int(n15.max()),
                    'max_source_features_atleast_030':int(n30.max()),
                    'max_site_duration_above_015_h':float(risk.duration_above_h.max()),
                    'ever_wet_sites_001':int(recovery.status.ne('not_exceeded').sum()),
                    'censored_sites_001':int(recovery.status.eq('right_censored').sum()),
                    'recovered_sites_001':int(recovery.status.eq('recovered').sum()),
                    'latest_recovery_h_001':float(recovery.recovery_hour.max()) if recovery.recovery_hour.notna().any() else None,
                    'modelled_source_features':int(modeled.sum()),'unknown_source_features':int((~modeled).sum())})
        summary=pd.DataFrame(summaries);metrics=pd.DataFrame(metrics)
        summary.to_csv(out/'raw/scenario_summary.csv',index=False,encoding='utf-8-sig')
        metrics.to_csv(out/'raw/site_threshold_metrics.csv',index=False,encoding='utf-8-sig')
        pd.DataFrame(road_metrics).to_csv(out/'raw/baseline_road_threshold_metrics.csv',index=False,encoding='utf-8-sig')
        pd.DataFrame(step).to_csv(out/'raw/time_step_check.csv',index=False)
        rain_stop=round(cfg['rainfall']['event_end_hour']/dt)
        metric_boundary=gpd.GeoSeries([polygon],crs=4326).to_crs(32650).iloc[0]
        # Interpolation/projection can place a clipped line endpoint a few
        # nanometres outside. Report the measured error; allow only 1 micrometre.
        maximum_boundary_error_m=float(site.distance(metric_boundary).max())
        checks={'scope_excludes_dapeng':not bool(boundary.include_dapeng.any()),
            'frozen_OD_inputs_match':True,'rain_reference_totals':all(np.isclose(rain[rain.scenario.eq(s)].rain_mm_interval.sum(),t) for s,t in cfg['rainfall']['total_mm'].items()),
            'site_mean_rain_factor_one':bool(np.isclose(site.rain_spatial_factor.mean(),1)),
            'all_sites_inside_boundary_1um_tolerance':maximum_boundary_error_m<=1e-6,
            'finite_nonnegative_depths':all(np.isfinite(h).all() and (h>=0).all() for h in arrays.values()),
            'dry_normal':all((arrays[c,'normal']==0).all() for c in cfg['cases']),
            'scenario_ordering':all((arrays[c,'general']<=arrays[c,'severe']+1e-12).all() and (arrays[c,'severe']<=arrays[c,'extreme']+1e-12).all() for c in cfg['cases']),
            'dry_recession_nonincreasing':all((np.diff(h[rain_stop:],axis=0)<=1e-12).all() for h in arrays.values()),
            'drainage_ordering':all((arrays['drainage_half',s]>=arrays['baseline',s]-1e-12).all() and (arrays['baseline',s]>=arrays['drainage_1p5',s]-1e-12).all() for s in cfg['rainfall']['total_mm']),
            'recession_ordering':all((arrays['recession_slow',s]>=arrays['baseline',s]-1e-12).all() and (arrays['baseline',s]>=arrays['recession_fast',s]-1e-12).all() for s in cfg['rainfall']['total_mm']),
            'interval_water_balance':maximum_residual<1e-9,'event_water_balance':event_residual<1e-8,
            'no_false_recovery':bool(metrics.loc[metrics.status.ne('recovered'),'recovery_hour'].isna().all()),
            'durations_within_window':bool(metrics.duration_above_h.between(0,cfg['duration_hours']).all()),
            'unknown_roads_are_NaN':True,'unique_arc_IDs_read_from_graph':bool(arcs.edge_id.is_unique)}
        assert all(checks.values()),checks
        report={'run_id':name,'region':'longgang','include_dapeng':False,'observed':False,'topology_certified':False,
            'model':'independent_road_grid_storage_proxies_not_hydrodynamic','od_package':cfg['od_package'],
            'site_count':len(site),'accepted_source_features_in_scope':len(features),'modelled_source_features':int(modeled.sum()),
            'source_feature_status_counts':{str(k):int(v) for k,v in features.status.value_counts().items()},
            'directed_arc_mapping_rows':len(arcs),'boundary_crossing_arcs':int(arcs.crosses_study_boundary.sum()),
            'sample_count':len(samples),'missing_dsm_samples':int((~samples.valid_dsm).sum()),
            'maximum_site_boundary_error_m':maximum_boundary_error_m,'boundary_numeric_tolerance_m':1e-6,
            'terrain':terrain,'time_endpoints':len(endpoints),'intervals':len(endpoints)-1,'cases':len(cfg['cases']),
            'scenarios':len(cfg['rainfall']['total_mm']),'max_interval_balance_residual_mm':maximum_residual,
            'max_event_balance_residual_mm':event_residual,'time_step_check':step,'checks':checks,'all_checks_passed':True,
            'baseline_summary':summary[summary.case.eq('baseline')].replace({np.nan:None}).to_dict('records'),
            'limitations':['Synthetic stress scenarios, not official return periods or observed historical floods',
                'DSM includes buildings/vegetation; local low score is an uncalibrated proxy, not delineated drainage',
                'Independent stores have no lateral exchange, pipe network, river/tide backwater or verified pond areas',
                'Ground source-line depth is maximum linked grid proxy: coarse conservative exposure, not surveyed carriageway depth',
                'Bridges, tunnels, nonzero layer and missing DSM remain unmodelled NaN; partial coverage flagged',
                'Graph IDs are exact within an inferred, uncertified topology; crossing arcs may include outside-boundary portions',
                'Station SW zero datum and address proxy positions unverified; monitoring not used for calibration',
                'Road-proxy rainfall factors normalized across sites, not full district area',
                'No traffic assignment, road speed/capacity response, resilience, optimization or SUMO run'],
            'elapsed_seconds':time.time()-started}
        write(out/'provenance/validation_report.json',report)
        make_figures(out,rain,site,features,arrays,endpoints,summary)
        inputs=[config,Path(__file__).resolve(),ROOT/'src/uftr/longgang_storm.py',ROOT/'src/uftr/storm_process.py',
            ROOT/'src/uftr/longgang_od.py',ROOT/'src/uftr/spatial.py',source,dsm,od/'manifest.json',od/'study_boundary.geojson',od/'config.yaml',od/'inferred_source_network.graphml']
        for file in inputs[:6]:shutil.copy2(file,out/'provenance'/file.name)
        write(out/'status.json',{'status':'complete_synthetic_storm_uncalibrated','observed':False})
        manifest={'run_id':name,'inputs':[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in inputs],
            'outputs':[{'path':p.relative_to(out).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(out.rglob('*')) if p.is_file()]}
        write(out/'manifest.json',manifest)
        with zipfile.ZipFile(str(out)+'.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for file in sorted(out.rglob('*')):
                if file.is_file():z.write(file,file.relative_to(out).as_posix())
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        return out
    except Exception:
        write(out/'status.json',{'status':'failed','traceback':traceback.format_exc()});raise


def make_figures(out,rain,sites,features,arrays,times,summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'svg.fonttype':'none','font.size':10})
    colors=['#4184a3','#d59028','#b74050'];names=['general','severe','extreme']
    def save(fig,name):
        for ext in ['png','svg']:fig.savefig(out/'figures'/f'{name}.{ext}',dpi=160)
        plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(12,10),sharex=True,layout='constrained')
    for scenario,color in zip(names,colors):
        frame=rain[rain.scenario.eq(scenario)];h=arrays['baseline',scenario]
        axes[0].stairs(frame.intensity_mm_h,np.r_[frame.start_h.to_numpy(),24],color=color,label=f'{scenario} / {frame.rain_mm_interval.sum():.0f} mm')
        axes[1].plot(times,h.max(1),color=color);axes[2].plot(times,(h>.15).sum(1),color=color)
    for ax,label in zip(axes,['参考雨强 mm/h','代理单元最大水深 m','水深 > 0.15 m代理单元数']):
        ax.set_ylabel(label);ax.set_xlim(0,24);ax.set_ylim(bottom=0);ax.axvline(13,color='gray',ls='--');ax.grid(alpha=.2)
    axes[0].legend();axes[2].set_xlabel('相对情景起点 小时')
    fig.suptitle('龙岗不含大鹏 合成暴雨与积水过程\n独立道路网格蓄水代理，未经实测标定，单元数不代表淹没面积')
    save(fig,'rainfall_ponding_process')
    fig,axes=plt.subplots(1,3,figsize=(16,6),layout='constrained')
    for ax,scenario in zip(axes,names):
        features.plot(ax=ax,color='#d6dde0',linewidth=.25)
        sites.assign(peak_m=arrays['baseline',scenario].max(0)).plot(ax=ax,column='peak_m',cmap='YlOrRd',markersize=5,vmin=0,vmax=arrays['baseline','extreme'].max(),legend=scenario=='extreme',legend_kwds={'label':'合成峰值水深 m','shrink':.6})
        ax.set_title(scenario+'  各单元各自峰值');ax.set_axis_off()
    fig.suptitle('龙岗道路积水代理空间分布\n点值为不同时间各自峰值，不是连续淹没图，桥隧与未建模道路不赋零水深')
    save(fig,'proxy_peak_map')
    fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
    j=int(arrays['baseline','extreme'].max(0).argmax())
    for case in summary.case.drop_duplicates():axes[0].plot(times,arrays[case,'extreme'][:,j],label=case)
    axes[0].axhline(.01,color='gray',ls=':');axes[0].set(xlabel='小时',ylabel='同一代理单元水深 m',title='极端情景 排水与退水参数敏感性');axes[0].legend(fontsize=8);axes[0].grid(alpha=.2)
    base=summary[summary.case.eq('baseline')&summary.scenario.ne('normal')].set_index('scenario').loc[names]
    axes[1].bar(names,base.max_source_features_atleast_030,color=colors)
    axes[1].set(ylabel='同时达到0.30 m的源道路要素数最大值',title='合成道路暴露\n按源线聚合，不能解释为独立道路或封路实测')
    save(fig,'sensitivity_road_exposure')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,default=ROOT/'configs/longgang_storm.yaml')
    build(p.parse_args().config.resolve())
