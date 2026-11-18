"""Build an auditable rainfall/ponding/OD scenario package from existing GIS inputs.

This creates synthetic experiment inputs, never inferred observations. No core
traffic/resilience results or historical manifests are changed by this script.
"""
from __future__ import annotations
import argparse
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import shutil
import zipfile
from zoneinfo import ZoneInfo

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
import yaml

ROOT = Path(__file__).resolve().parents[1]
NAMES = {'normal':'正常', 'general':'一般', 'severe':'严重', 'extreme':'极端'}


def hash_file(p):
    h = sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def build(config_path):
    cfg = yaml.safe_load(config_path.read_text(encoding='utf-8'))
    stamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%dT%H%M%S')
    out = ROOT/'data/synthetic/scenario_packages'/f'{stamp}_nanshan_seed{cfg["seed"]}'
    out.mkdir(parents=True,exist_ok=False)
    for folder in ['rainfall','flood','demand','gis','figures','provenance']: (out/folder).mkdir()
    rng=np.random.default_rng(cfg['seed'])
    dt=cfg['interval_minutes']/60
    n=int(cfg['duration_hours']/dt)
    assert n*dt == cfg['duration_hours'] and dt > 0
    t=np.arange(n)*dt; mid=t+dt/2; endpoints=np.arange(n+1)*dt
    paths=cfg['paths']; net=ROOT/paths['network']; zone_root=ROOT/paths['zones']
    points=gpd.read_file(ROOT/paths['risk_points']).sort_values('point_id').reset_index(drop=True)
    roads=gpd.read_file(net/'road_edges.geojson')
    boundary=gpd.read_file(net/'study_boundary.geojson')
    zones=gpd.read_file(zone_root/'traffic_zones.geojson')
    gateways=gpd.read_file(zone_root/'boundary_gateways.geojson')
    mapping=pd.read_csv(ROOT/paths['point_road_mapping'])
    selected=mapping[mapping.selected_geometry & mapping.edge_id.notna()].copy()
    rain_cfg=cfg['rainfall']; model=cfg['ponding']
    xy=points.to_crs(32650).geometry
    coordinates=np.column_stack([xy.x,xy.y])
    kernel=np.exp(-cdist(coordinates,coordinates)/rain_cfg['spatial_correlation_m'])
    noise=np.linalg.cholesky(kernel+np.eye(len(points))*1e-9)@rng.normal(size=len(points))
    rain_factor=np.exp(rain_cfg['spatial_log_sd']*noise)
    rain_factor/=rain_factor.mean()
    # Lower DSM receives higher assumed concentration; DSM is not a drainage DTM.
    elevation_rank=points.dsm_m.rank(method='average',pct=True).to_numpy()
    concentration=model['concentration_ratio_min']+model['concentration_ratio_span']*(1-elevation_rank)
    drain=model['drainage_min_mm_h']+model['drainage_span_mm_h']*elevation_rank
    weights=sum(w*np.exp(-.5*((mid-peak)/width)**2) for w,peak,width in zip(
        rain_cfg['peak_weights'],rain_cfg['peaks_hour'],rain_cfg['peak_width_hours']))
    weights[(mid<rain_cfg['event_start_hour']) | (mid>=rain_cfg['event_end_hour'])]=0
    weights/=weights.sum()
    rain_tables=[]; depth_tables=[]; balance_tables=[]; edge_tables=[]; summaries=[]; depth_arrays={}
    point_ids=points.point_id.to_numpy(); pid_to_index={p:i for i,p in enumerate(point_ids)}
    edge_ids=sorted(selected.edge_id.unique())
    point_depths={}; rain_arrays={}; residual=0.0
    for scenario,total in rain_cfg['total_mm'].items():
        regional=weights*total
        rainfall=regional[:,None]*rain_factor[None,:]
        runoff=rainfall*model['runoff_coefficient']*concentration[None,:]
        h=np.zeros((n+1,len(points))); drained=np.zeros_like(runoff)
        for k in range(n):
            available=h[k]+runoff[k]
            drained[k]=np.minimum(available,drain*dt+h[k]*dt/model['recession_tau_h'])
            h[k+1]=available-drained[k]
        delta=h[1:]-h[:-1]-runoff+drained
        residual=max(residual,float(np.abs(delta).max()))
        depths=h/1000
        point_depths[scenario]=depths; rain_arrays[scenario]=regional
        depth_arrays[scenario]=depths
        rain_tables.append(pd.DataFrame({'scenario':scenario,'interval_index':np.arange(n),
            'start_hour':t,'end_hour':t+dt,'rainfall_mm_interval':regional,
            'intensity_mm_h':regional/dt,'cumulative_rainfall_mm':regional.cumsum(),
            'source_kind':'synthetic_assumed_rainfall','observed':False}))
        point_rain=pd.DataFrame({'scenario':scenario,'interval_index':np.repeat(np.arange(n),len(points)),
            'point_id':np.tile(point_ids,n),'rainfall_mm_interval':rainfall.ravel(),
            'source_kind':'synthetic_spatial_rainfall','observed':False})
        point_rain.to_csv(out/'rainfall'/f'point_rainfall_{scenario}.csv',index=False,encoding='utf-8-sig')
        depth_tables.append(pd.DataFrame({'scenario':scenario,'time_s':np.repeat(endpoints*3600,len(points)).astype(int),
            'point_id':np.tile(point_ids,n+1),'depth_m':depths.ravel(),
            'risk_index':np.searchsorted(model['risk_breaks_m'],depths.ravel(),side='right'),
            'source_kind':'synthetic_rainfall_bucket','observed':False}))
        balance_tables.append(pd.DataFrame({'scenario':scenario,'point_id':point_ids,
            'rainfall_total_mm':rainfall.sum(axis=0),'concentrated_runoff_mm':runoff.sum(axis=0),
            'drained_mm':drained.sum(axis=0),'initial_storage_mm':h[0],'final_storage_mm':h[-1],
            'mass_balance_residual_mm':h[-1]-h[0]-runoff.sum(axis=0)+drained.sum(axis=0)}))
        ed=np.zeros((n+1,len(edge_ids)))
        for j,edge_id in enumerate(edge_ids):
            indices=[pid_to_index[p] for p in selected.loc[selected.edge_id.eq(edge_id),'point_id'].unique()]
            ed[:,j]=depths[:,indices].max(axis=1)
        edge_tables.append(pd.DataFrame({'scenario':scenario,'time_s':np.repeat(endpoints*3600,len(edge_ids)).astype(int),
            'edge_id':np.tile(edge_ids,n+1),'depth_m':ed.ravel(),
            'source_kind':'synthetic_rainfall_bucket_geometric_association','zero_datum_observed':False}))
        for j,pid in enumerate(point_ids):
            k=int(depths[:,j].argmax())
            summaries.append({'scenario':scenario,'point_id':pid,'peak_depth_m':float(depths[k,j]),
                'first_peak_hour':float(endpoints[k]),'risk_index':int(np.searchsorted(model['risk_breaks_m'],depths[k,j],side='right')),
                'source_kind':'synthetic_rainfall_bucket','observed':False})
    rain=pd.concat(rain_tables,ignore_index=True)
    depth=pd.concat(depth_tables,ignore_index=True)
    edge_depth=pd.concat(edge_tables,ignore_index=True)
    balance=pd.concat(balance_tables,ignore_index=True)
    peaks=pd.DataFrame(summaries)
    rain.to_csv(out/'rainfall/areal_reference_rainfall_15min.csv',index=False,encoding='utf-8-sig')
    depth.to_csv(out/'flood/point_depth_timeseries.csv',index=False,encoding='utf-8-sig')
    depth.to_parquet(out/'flood/point_depth_timeseries.parquet',index=False)
    edge_depth.to_parquet(out/'flood/edge_depth_timeseries.parquet',index=False)
    balance.to_csv(out/'flood/water_balance.csv',index=False,encoding='utf-8-sig')
    peaks.to_csv(out/'flood/point_peak_summary.csv',index=False,encoding='utf-8-sig')
    params=points[['point_id','dsm_m']].copy()
    params['rain_spatial_factor']=rain_factor; params['runoff_coefficient']=model['runoff_coefficient']
    params['hypothetical_concentration_ratio']=concentration; params['drainage_mm_h']=drain
    params['recession_tau_h']=model['recession_tau_h']; params['has_geometric_road_match']=params.point_id.isin(selected.point_id)
    params['observed']=False; params.to_csv(out/'flood/point_parameters.csv',index=False,encoding='utf-8-sig')
    points['source_kind']='synthetic_low_DSM_road_candidates'; points['observed']=False
    for scenario in NAMES:
        points=points.merge(peaks[peaks.scenario.eq(scenario)][['point_id','peak_depth_m']].rename(columns={'peak_depth_m':f'{scenario}_peak_m'}),on='point_id',validate='one_to_one')
    points.to_file(out/'gis/synthetic_flood_points.geojson',driver='GeoJSON')
    for name in ['study_boundary.geojson']:
        shutil.copy2(net/name,out/'gis'/name)
    for name in ['traffic_zones.geojson','boundary_gateways.geojson','all_zone_connectors.csv']:
        shutil.copy2(zone_root/name,out/'gis'/name)
    shutil.copy2(ROOT/paths['point_road_mapping'],out/'gis/point_road_candidates.csv')

    # Full matrices include zero-demand zones, intrazonal demand and all gateways.
    source_od=pd.read_csv(ROOT/cfg['demand']['source'])
    zone_ids=sorted(zones.zone_id.astype(str).tolist())+sorted(gateways.zone_id.astype(str).tolist())
    assert len(zone_ids)==len(set(zone_ids))
    matrices={}; period_totals={}
    for period,frame in source_od.groupby('period'):
        matrix=frame.pivot(index='origin_zone',columns='destination_zone',values='flow_veh_h').reindex(index=zone_ids,columns=zone_ids).fillna(0)
        matrix.to_csv(out/'demand'/f'od_{period}_veh_h.csv',encoding='utf-8-sig',float_format='%.12g')
        matrices[period]=matrix.to_numpy(); period_totals[period]=float(matrix.to_numpy().sum())
    source_od.to_csv(out/'demand/od_all_periods_long.csv',index=False,encoding='utf-8-sig')
    meta=pd.DataFrame({'zone_index':np.arange(len(zone_ids)),'zone_id':zone_ids,
                       'zone_kind':['internal']*len(zones)+['external_gateway']*len(gateways)})
    meta.to_csv(out/'demand/zone_index.csv',index=False,encoding='utf-8-sig')
    profile=[]; daily=np.zeros_like(matrices['offpeak']); od_arrays=np.empty((n,len(zone_ids),len(zone_ids)),dtype=np.float64)
    for k,hour in enumerate(mid):
        demand=cfg['demand']; period='offpeak'
        if demand['morning_hours'][0] <= hour < demand['morning_hours'][1]: period='morning_peak'
        elif demand['evening_hours'][0] <= hour < demand['evening_hours'][1]: period='evening_peak'
        factor=float(demand['hourly_offpeak_multipliers'][int(hour)])*demand['weather_demand_multiplier']
        trips=matrices[period]*factor*dt
        od_arrays[k]=trips; daily+=trips
        profile.append({'interval_index':k,'start_hour':float(t[k]),'end_hour':float(t[k]+dt),
                        'base_period':period,'rate_multiplier':factor,'duration_hours':dt,
                        'total_rate_veh_h':period_totals[period]*factor,'expected_vehicles_interval':float(trips.sum()),
                        'source_kind':'synthetic_time_profile','observed':False})
    profile=pd.DataFrame(profile)
    profile.to_csv(out/'demand/departure_profile_15min.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(daily,index=zone_ids,columns=zone_ids).to_csv(out/'demand/od_daily_expected_vehicles.csv',encoding='utf-8-sig',float_format='%.12g')
    np.savez_compressed(out/'demand/od_15min_expected_vehicles.npz',expected_vehicles=od_arrays,
                        zone_ids=np.array(zone_ids,dtype='U48'),start_hour=t,end_hour=t+dt)

    # Independent arithmetic/file round trips, not a claim of empirical calibration.
    in_boundary=points.geometry.covered_by(boundary.geometry.union_all())
    checks={'all_60_points_in_boundary':bool(in_boundary.all() and len(points)==60),
        'nonnegative_finite_depth':bool(np.isfinite(depth.depth_m).all() and depth.depth_m.ge(0).all()),
        'normal_is_dry':bool((point_depths['normal']==0).all()),
        'rainfall_totals_match_assumptions':all(np.isclose(rain_arrays[s].sum(),v) for s,v in rain_cfg['total_mm'].items()),
        'nested_depth_scenarios':bool(all((point_depths[b]>=point_depths[a]-1e-12).all() for a,b in zip(list(NAMES)[:-1],list(NAMES)[1:]))),
        'per_interval_mass_balance':residual<1e-10,
        'event_mass_balance':bool(balance.mass_balance_residual_mm.abs().max()<1e-8),
        'all_mapped_edges_exist':bool(set(edge_ids)<=set(roads.edge_id)),
        'all_input_OD_zones_retained':bool((set(source_od.origin_zone)|set(source_od.destination_zone))<=set(zone_ids)),
        'daily_OD_equals_interval_sum':bool(np.allclose(daily,od_arrays.sum(axis=0),rtol=1e-12,atol=1e-12)),
        'profile_expected_vehicles_conserved':bool(np.isclose(profile.expected_vehicles_interval.sum(),daily.sum(),rtol=1e-12)),
        'all_OD_finite_nonnegative':bool(np.isfinite(od_arrays).all() and (od_arrays>=0).all()),
        'OD_archive_roundtrip':bool(np.allclose(np.load(out/'demand/od_15min_expected_vehicles.npz')['expected_vehicles'],od_arrays))}
    for period in matrices:
        reloaded=pd.read_csv(out/'demand'/f'od_{period}_veh_h.csv',index_col=0).to_numpy()
        checks[f'{period}_CSV_roundtrip']=bool(np.allclose(reloaded,matrices[period],rtol=1e-10,atol=1e-12))
    if not all(checks.values()): raise ValueError(checks)
    report={'package_id':out.name,'data_kind':'synthetic_scenarios_unvalidated','seed':cfg['seed'],
        'duration_h':cfg['duration_hours'],'interval_min':cfg['interval_minutes'],'intervals':n,'depth_endpoints':n+1,
        'points':len(points),'road_matched_points':int(params.has_geometric_road_match.sum()),'affected_directed_edges':len(edge_ids),
        'matrix_shape':[len(zone_ids),len(zone_ids)],'internal_zones':len(zones),'gateways':len(gateways),
        'active_OD_zone_ids':len(set(source_od.origin_zone)|set(source_od.destination_zone)),
        'nonzero_pairs_per_period':int((matrices['offpeak']>0).sum()),'base_OD_totals_veh_h':period_totals,
        'daily_expected_vehicle_trips':float(daily.sum()),'rainfall_total_mm':rain_cfg['total_mm'],
        'maximum_point_depth_m':{s:float(point_depths[s].max()) for s in NAMES},
        'max_mass_balance_residual_mm':float(balance.mass_balance_residual_mm.abs().max()),
        'checks':checks,'check_count':len(checks),'all_checks_passed':all(checks.values()),
        'scope':'New synthetic rainfall-driven bucket experiment inputs only; prior Phase04-13 results are not recomputed',
        'geometric_edge_default':'Unlisted edges assumed depth 0; listed edges use max of associated synthetic points',
        'units':{'rainfall':'mm per interval','intensity':'mm/h','depth':'m at interval endpoint','base_OD':'veh/h',
                 'time_OD':'fractional expected vehicle trips per 15min','daily_OD':'expected vehicle trips per day'},
        'limits':['No measured OD, drainage capacity, catchment boundaries, flood footprint or return-period calibration',
                  'DSM ranking and hypothetical runoff concentration are proxies; ponds do not exchange water',
                  'Synthetic spatial rain mean is an unweighted 60-point mean, not a calibrated area integral',
                  'Point-road association does not establish physical inundation; five unmatched points retained',
                  'Exogenous OD kept identical across weather scenarios; unreachable and intrazonal demand retained',
                  'Observed SW records remain separate and do not calibrate this model']}
    (out/'provenance/validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Numerical generation passed; plotting...',flush=True)
    plot_figures(out,points,roads,boundary,rain,peaks,point_depths,profile,matrices,report)
    write_documentation(out,cfg,report)
    shutil.copy2(config_path,out/'provenance/config.yaml')
    shutil.copy2(__file__,out/'provenance/generate_synthetic_data_package.py')
    write_shared_content(out,report)
    input_paths=[config_path,Path(__file__).resolve(),ROOT/paths['risk_points'],ROOT/paths['point_road_mapping'],
        net/'road_edges.geojson',net/'study_boundary.geojson',ROOT/cfg['demand']['source'],
        zone_root/'traffic_zones.geojson',zone_root/'boundary_gateways.geojson',zone_root/'all_zone_connectors.csv']
    files=[p for p in sorted(out.rglob('*')) if p.is_file()]
    manifest={'package_id':out.name,'status':'success','source_kind':'synthetic','observed':False,
        'inputs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hash_file(p)} for p in input_paths],
        'outputs':[{'path':p.relative_to(out).as_posix(),'bytes':p.stat().st_size,'sha256':hash_file(p)} for p in files]}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(out.parent))
    print(json.dumps({'package':str(out),'zip':str(archive),'checks':len(checks),'report':report},ensure_ascii=False),flush=True)
    return out


def plot_figures(out,points,roads,boundary,rain,peaks,depths,profile,matrices,report):
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'svg.fonttype':'none','font.size':11})
    def save(fig,name):
        for ext in ['png','svg']: fig.savefig(out/'figures'/f'{name}.{ext}',dpi=170)
        plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(13,8),sharex=True)
    fig.subplots_adjust(left=.09,right=.96,top=.87,bottom=.17,hspace=.25)
    colors={'general':'#4b8caa','severe':'#e39a35','extreme':'#be4058'}
    for s,c in colors.items():
        d=rain[rain.scenario.eq(s)]
        axes[0].step(d.start_hour,d.intensity_mm_h,where='post',color=c,label=f'{NAMES[s]} {report["rainfall_total_mm"][s]} mm')
        axes[1].plot(np.arange(len(depths[s]))*report['interval_min']/60,depths[s].max(axis=1),color=c,label=NAMES[s])
    axes[0].set_ylabel('合成雨强（mm/h）'); axes[0].legend(ncol=3); axes[0].grid(alpha=.2)
    axes[1].set_ylabel('60点最大合成水深（m）'); axes[1].set_xlabel('情景起点后的小时')
    axes[1].grid(alpha=.2); axes[1].set_xticks(np.arange(0,25,2)); axes[1].set_xlim(0,24)
    fig.suptitle('南山合成情景  降雨驱动的积水过程',fontsize=18)
    fig.text(.09,.07,'24小时 / 15分钟；总雨量为实验假设，无重现期含义。独立蓄水桶模型不解析管网、汇水区与河潮顶托。',fontsize=11)
    save(fig,'synthetic_rainfall_depth')
    fig,axes=plt.subplots(1,3,figsize=(16,8))
    fig.subplots_adjust(left=.03,right=.94,bottom=.16,top=.85,wspace=.07)
    r=roads.to_crs(32650); b=boundary.to_crs(32650); p=points.to_crs(32650)
    x0,y0,x1,y1=r[r.geometry.centroid.y>2485000].total_bounds
    vmax=report['maximum_point_depth_m']['extreme']
    for ax,s in zip(axes,['general','severe','extreme']):
        r.plot(ax=ax,color='#98b1c0',linewidth=.2,rasterized=True)
        b.boundary.plot(ax=ax,color='#9ba5ac',linewidth=.6,linestyle='--')
        im=ax.scatter(p.geometry.x,p.geometry.y,c=p[f'{s}_peak_m'],cmap='YlOrRd',vmin=0,vmax=vmax,s=25,edgecolors='#5b6b75',linewidths=.3,zorder=5)
        ax.set_xlim(x0-600,x1+500); ax.set_ylim(y0-400,y1+600); ax.set_aspect('equal'); ax.axis('off')
        ax.set_title(f'{NAMES[s]}情景  {report["rainfall_total_mm"][s]} mm\n最大合成水深 {report["maximum_point_depth_m"][s]:.2f} m',fontsize=13)
    fig.colorbar(im,ax=axes.tolist(),shrink=.65,pad=.02,label='各点事件最高合成水深（m）')
    fig.suptitle('南山60个合成风险候选点与真实路网',fontsize=19)
    fig.text(.07,.065,'点位源于低DSM道路种子及高斯聚集，不是历史积涝点。三图使用同一色标，点位和参数固定。\n各点峰值不同时；未生成连续淹没面。© OpenStreetMap contributors，ODbL 1.0',fontsize=11)
    save(fig,'synthetic_flood_points_map')
    fig,axes=plt.subplots(1,2,figsize=(13,6.5));fig.subplots_adjust(left=.08,right=.94,bottom=.21,top=.85,wspace=.28)
    mat=matrices['morning_peak']; active=np.flatnonzero((mat.sum(axis=0)+mat.sum(axis=1))>0)
    im=axes[0].imshow(np.ma.masked_less_equal(mat[np.ix_(active,active)],0),cmap='magma',norm=LogNorm(vmin=1e-4,vmax=mat.max()),interpolation='nearest')
    axes[0].set_title(f'早高峰活跃分区子矩阵 {len(active)} × {len(active)}')
    axes[0].set_xlabel('目的分区序号');axes[0].set_ylabel('起点分区序号')
    fig.colorbar(im,ax=axes[0],shrink=.7,label='合成需求（veh/h，对数色阶）')
    axes[1].step(profile.start_hour,profile.total_rate_veh_h,where='post',color='#367da1')
    axes[1].set_title('24小时合成出发需求');axes[1].set_xlabel('情景起点后的小时');axes[1].set_ylabel('合成需求率（veh/h）')
    axes[1].set_xlim(0,24);axes[1].grid(alpha=.2)
    fig.suptitle('南山合成OD矩阵与出发时间分布',fontsize=18)
    fig.text(.08,.07,f'完整矩阵 {report["matrix_shape"][0]} × {report["matrix_shape"][1]}，含568个内部TAZ及6个外部网关；零需求区和不可达需求保留。\nOD与时间分布未经实测校准。各暴雨情景使用同一出发需求，避免混淆需求变化与道路受损效应。',fontsize=11)
    save(fig,'synthetic_OD_demand')


def write_documentation(out,cfg,report):
    text=f'''# 南山降雨积水与交通需求合成数据包

本包是基于真实OSM路网、WorldPop模型人口与假设参数构造的实验输入。降雨、水深和OD均为合成，不能当作2023年9月暴雨重建、实测交通或已标定水动力预测。观测水位文件保持独立。

- 时间：相对情景起点0至24小时，96个15分钟区间，水深97个端点。不赋真实事件日期。
- 降雨总量：正常0、一般100、严重200、极端300 mm。5至13小时双峰雨型，峰中心8和10小时。名称是实验强度标签，不是气象等级或重现期。
- 空间：60个既有合成低DSM道路候选点，全部在研究边界内。空间扰动1.5km相关，60点雨量算术均值等于参考雨量，不代表真实面积加权降雨。
- 简化积水模型：输入有效雨量为 R[k,i] × 0.8 × A[i]，单位mm。A为假设汇水面积与积水面积比。
  排水量 D=min(H[k]+输入, c[i]×0.25+H[k]×0.25/4)，H[k+1]=H[k]+输入-D。模型H为假设路面相对积水，不采用观测SW零点。
- A=2+2.5×(1-DSM百分位)，c=8+10×DSM百分位 mm/h。DSM含建筑植被，仅作代理，不识别真实汇水区、坡向或排水管网。
- 55点具有几何道路匹配，关联54条有向边；5点保留但不赋路段水深。路段取关联点最大值，未列路段默认0只是模型假设，不证明实际无积水。
- 完整OD矩阵为{report['matrix_shape'][0]}×{report['matrix_shape'][1]}，包括568内部TAZ、6外部网关。242个ID有正OD，每时段58528非零对，其余分区零需求仍保留。
- 三时段基准矩阵单位veh/h。平峰{report['base_OD_totals_veh_h']['offpeak']:.4f}、早峰{report['base_OD_totals_veh_h']['morning_peak']:.4f}、晚峰{report['base_OD_totals_veh_h']['evening_peak']:.4f} veh/h。来自既有重力/IPF合成OD，没有新观测校准。
- 7至9小时用早峰、17至19小时用晚峰，其余平峰。每小时附加倍率见config.yaml。每15分钟期望车辆数=基准OD率×倍率×0.25。
- 全天期望出行量{report['daily_expected_vehicle_trips']:.4f}车次。允许小数，这是期望值，转SUMO车辆需另做可复现抽样。
- 不可达需求和区内出行仍保留在矩阵，长表route_status记录，矩阵不等于已服务道路流量。雨天需求倍率固定1，所有情景使用相同OD。
- 本包尚未重跑既有交通分配、韧性和治理实验，旧结果不能引用为本包的效果。

## 文件使用

rainfall/areal_reference_rainfall_15min.csv保存参考雨量、雨强及累计量；point_rainfall_*.csv保存点级合成雨量。
flood/point_depth_timeseries.csv或parquet保存60点全过程。edge_depth_timeseries.parquet使用既有Phase04的scenario/time_s/edge_id/depth_m接口，可作为后续新实验输入。
flood/point_parameters.csv保存假设参数；water_balance.csv保存输入、排水和末期储量；point_peak_summary.csv保存各点峰值。
demand/od_*_veh_h.csv是三个完整带行列ID的OD率矩阵；od_all_periods_long.csv保留路由状态；od_daily_expected_vehicles.csv是全天期望车次矩阵。
demand/od_15min_expected_vehicles.npz内expected_vehicles形状为(96,574,574)，单位车次/15分钟；zone_ids给出行列顺序，start_hour/end_hour给出区间。
demand/departure_profile_15min.csv保存96个区间的基准时段、倍率和总量；zone_index.csv对应全部574分区。
gis/保存合成点、TAZ、网关、接入状态与候选道路对应，不重复复制大型路网。真实道路输入路径和SHA在manifest.json。
figures/保存PNG与SVG；provenance/保存脚本、配置和数值检查。manifest.json为输入输出指纹。

```python
import numpy as np
import pandas as pd
data = np.load('demand/od_15min_expected_vehicles.npz', allow_pickle=False)
od_08_00 = data['expected_vehicles'][32]  # [8.00,8.25)，期望车次
ids = data['zone_ids']
pd.DataFrame(od_08_00, index=ids, columns=ids).to_csv('od_0800_0815.csv')
# 若分配器需要veh/h，应使用 od_08_00 / 0.25，不能把车次直接当小时率。
```

## 验证及适用范围

{report['check_count']}项算术、边界、情景单调性及文件回读检查通过。逐步及全事件水量平衡误差见provenance/validation_report.json。检查通过只证明生成和单位换算一致，不证明假设符合真实南山排水和交通。

真实来源：© OpenStreetMap contributors，ODbL1.0；Copernicus GLO30 DSM；WorldPop2020，CC BY4.0。详见项目DATA_SOURCES.md。合成参数见provenance/config.yaml。
'''
    (out/'README.md').write_text(text,encoding='utf-8')
    fields=[
        ('rainfall','scenario','text','normal/general/severe/extreme，假设强度'),
        ('rainfall','interval_index','index','0到95的15分钟区间序号'),
        ('rainfall','start_hour / end_hour','hour','相对情景起点的区间左右边界'),
        ('rainfall','rainfall_mm_interval','mm/interval','该区间合成雨量，不能当mm/h'),
        ('rainfall','intensity_mm_h','mm/h','区间雨量除以0.25小时'),
        ('rainfall','cumulative_rainfall_mm','mm','截至该区间末端累计合成雨量'),
        ('flood','point_id','text','既有60个合成候选点的稳定ID'),
        ('flood','time_s','s','相对情景起点端点时间0到86400'),
        ('flood','depth_m','m','模型假设路面相对积水，不是观测SW'),
        ('flood','risk_index','ordinal','0蓝/1黄/2橙/3红，断点0.15/0.30/0.40m'),
        ('flood','edge_id','text','既有有向道路ID，同路双向分别保留'),
        ('flood','peak_depth_m / first_peak_hour','m / hour','事件最高值及其首次出现的相对时刻'),
        ('balance','concentrated_runoff_mm / drained_mm','mm','相对于假设积水面积的有效输入和排水量'),
        ('balance','initial_storage_mm / final_storage_mm','mm','独立蓄水桶初末储量'),
        ('balance','mass_balance_residual_mm','mm','末储量减初储量减输入加排水'),
        ('parameters','hypothetical_concentration_ratio','dimensionless','假设汇水面积比，不是实测汇水区'),
        ('parameters','drainage_mm_h','mm/h','相对假设积水面积的恒定排水能力'),
        ('parameters','rain_spatial_factor','dimensionless','点雨量对参考雨量的乘数，60点算术均值1'),
        ('demand','origin_zone / destination_zone','text','起终点分区ID，包含外部网关'),
        ('demand','flow_veh_h','veh/h','三个基准时段的合成小时需求率'),
        ('demand','rate_multiplier','dimensionless','叠加在选定基准矩阵上的时段倍率'),
        ('demand','expected_vehicles_interval','vehicle trips/interval','单个15分钟区间的期望车次，允许小数'),
        ('demand','NPZ expected_vehicles','vehicle trips/interval','96×574×574，轴依次为区间、起点、终点'),
        ('demand','daily OD matrix','vehicle trips/day','96个区间期望车次数值求和'),
        ('demand','zone_index / zone_id','index / text','CSV与NPZ矩阵的固定行列顺序'),
        ('demand','route_status','text','保留可达、正常不可达及区内未上图需求状态'),
        ('provenance','source_kind / observed','text / bool','派生记录均为synthetic、observed为False')]
    pd.DataFrame(fields,columns=['table_group','field','unit','description']).to_csv(out/'data_dictionary.csv',index=False,encoding='utf-8-sig')
    cards=''.join(f'<h2>{p.stem}</h2><a href="figures/{p.name}"><img src="figures/{p.name}"></a>' for p in sorted((out/'figures').glob('*.png')))
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>南山合成情景数据</title><style>body{max-width:1100px;margin:32px auto;font:16px Microsoft YaHei}img{max-width:100%}</style><h1>南山降雨积水与OD合成数据</h1><p>实验输入，未经实测校准。24小时，15分钟，60合成点，574×574 OD。</p><p><a href="README.md">字段与使用说明</a> · <a href="provenance/validation_report.json">数值检查</a></p>'+cards,encoding='utf-8')


def write_shared_content(out,report):
    path=ROOT/'docs/deliverables/content.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    source=out.relative_to(ROOT).as_posix()
    sections=[
        {'title':'补充情景 降雨驱动的合成积水', 'paragraphs':[
            '新增数据包采用固定种子42，在24小时内按15分钟步长生成降雨与积水。正常、一般、严重、极端情景总雨量分别为0、100、200、300 mm，名称仅表示实验强度，不对应官方重现期。',
            '60个候选点沿用低DSM道路种子及高斯聚集。各点使用独立蓄水桶，有效降雨按假设汇水比例集中，并按假设排水能力与储量消退。水量守恒只验证计算一致，不能替代管网和水动力标定。',
            f'最高合成点水深为一般{report["maximum_point_depth_m"]["general"]:.3f} m、严重{report["maximum_point_depth_m"]["severe"]:.3f} m、极端{report["maximum_point_depth_m"]["extreme"]:.3f} m。观测SW数据不参与本模型的零点或参数校准。'],
         'slide_points':['24小时，15分钟步长，固定种子42','总雨量100 / 200 / 300 mm为实验假设','独立蓄水桶模型，未经真实排水系统标定'],
         'figure':source+'/figures/synthetic_rainfall_depth.png','caption':'补充图 合成雨强及60点最大水深过程，时间为相对情景起点'},
        {'title':'补充情景 南山合成积水点', 'paragraphs':[
            '所有60个合成候选点均在研究边界内。点位来源为既有低DSM道路种子及聚集，DSM含建筑植被，不能视为裸地排水地形。各点峰值可能发生在不同时间。',
            '55点存在几何道路匹配，关联54条有向边；其余5点保留且不赋路段水深。路段使用关联点最大值，未列路段默认干燥仅为模型假设。几何匹配不能证明实际道路受淹。',
            '本补充仅生成新实验输入，没有重跑既有交通分配、韧性或治理优化，原阶段实验结论不自动适用于这套新情景。'],
         'slide_points':['60个合成候选点，55点有几何道路匹配','关联54条有向边，保留5个未匹配点','空间匹配和假设排水参数均需后续验证'],
         'figure':source+'/figures/synthetic_flood_points_map.png','caption':'补充图 三种暴雨强度的各点最高合成水深，使用相同色标'},
        {'title':'补充情景 完整OD矩阵与出发需求', 'paragraphs':[
            '完整矩阵574×574，包含568个内部交通分区和6个外部网关。每个基准时段58528个非零OD对，242个ID有正需求，零需求区、不可达需求和区内需求均保留。OD沿用人口与设施生成的重力/IPF结果，未经实测校准。',
            f'平峰、早峰、晚峰小时总率分别为36974.7448、73949.4896、66554.5406 veh/h。按假设时间分布形成96个15分钟矩阵，全天期望出行量{report["daily_expected_vehicle_trips"]:.2f}车次。区间矩阵单位为期望车次，小时率应除以0.25。',
            f'完整数据、配置、脚本及{report["check_count"]}项算术与回读检查存于{source}。所有天气情景使用相同外生OD，不推定真实雨天出行抑制或真实路段流量。'],
         'slide_points':['完整OD为574 × 574，保留零需求与不可达出行','三套小时率矩阵及96套15分钟期望车次矩阵','OD与时间分布合成，未重跑交通分配'],
         'figure':source+'/figures/synthetic_OD_demand.png','caption':'补充图 242个活跃分区的早高峰子矩阵及全天合成需求率'}]
    # Version source facts before changing maintained delivery content.
    shutil.copy2(path,out/'provenance/content_before.json')
    data['final']['sections']=[s for s in data['final']['sections'] if not s.get('title','').startswith('补充情景 ')]+sections
    data['synthetic_data_package']={'path':source,'report':report,'sections_added':3}
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'docs/SYNTHETIC_DATA_PACKAGE.md').write_text((out/'README.md').read_text(encoding='utf-8')+'\n当前数据包路径：`'+source+'`。\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,default=ROOT/'configs/synthetic_data_package.yaml')
    build(parser.parse_args().config)
