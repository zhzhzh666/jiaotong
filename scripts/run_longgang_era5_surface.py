"""Run Method B with pinned ERA5 forcing and DSM; preserve all prior runs."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import math
import shutil
import time
import traceback
import uuid
import zipfile
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
import yaml
from pyproj import Transformer
from rasterio.transform import from_origin, rowcol
from rasterio.warp import reproject, Resampling
from uftr.era5_surface import priority_drainage, travel_time, simulate
from acquire_longgang_era5 import sha, write, ROOT


def verify_files(package, paths):
    manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8'))
    records={r['path']:r['sha256'] for r in manifest['outputs']}
    for path in paths:
        if sha(package/path)!=records[path]:raise ValueError('input SHA mismatch: '+path)


def raster_write(path, values, transform, crs):
    a=np.asarray(values,np.float32)
    with rasterio.open(path,'w',driver='GTiff',height=a.shape[0],width=a.shape[1],count=1,
                       dtype='float32',crs=crs,transform=transform,nodata=np.nan,compress='deflate') as dst:
        dst.write(a,1)


def make_domain(cfg, polygon, buffer_m, out):
    dx=cfg['domain']['cell_size_m'];crs=cfg['domain']['crs']
    xmin,ymin,xmax,ymax=polygon.buffer(buffer_m).bounds
    xmin=math.floor(xmin/dx)*dx;ymin=math.floor(ymin/dx)*dx
    xmax=math.ceil(xmax/dx)*dx;ymax=math.ceil(ymax/dx)*dx
    nr=round((ymax-ymin)/dx);nc=round((xmax-xmin)/dx)
    transform=from_origin(xmin,ymax,dx,dx)
    z=np.full((nr,nc),np.nan,np.float64)
    for tile in cfg['dsm_tiles']:
        with rasterio.open(ROOT/tile) as src:
            reproject(rasterio.band(src,1),z,src_transform=src.transform,src_crs=src.crs,
                      dst_transform=transform,dst_crs=crs,dst_nodata=np.nan,
                      init_dest_nodata=False,resampling=Resampling.average,num_threads=1)
    if not np.isfinite(z).all():raise ValueError('DSM has missing model-domain cells')
    rr,cc=np.indices(z.shape)
    xx=xmin+(cc.ravel()+.5)*dx;yy=ymax-(rr.ravel()+.5)*dx
    cells=shapely.box(xx-dx/2,yy-dx/2,xx+dx/2,yy+dx/2)
    weights=np.clip(shapely.area(shapely.intersection(cells,polygon))/(dx*dx),0,1)
    if not np.isclose(weights.sum()*dx*dx,polygon.area,rtol=1e-8):raise ValueError('district area mismatch')
    lon,lat=Transformer.from_crs(crs,4326,always_xy=True).transform(xx,yy)
    raster_write(out/'terrain_dsm_mean_150m.tif',z,transform,crs)
    raster_write(out/'district_fraction.tif',weights.reshape(z.shape),transform,crs)
    drainage=priority_drainage(z,dx)
    raster_write(out/'depression_storage_threshold_m.tif',drainage['spill_depth_m'].reshape(z.shape),transform,crs)
    tau=travel_time(drainage,cfg['routing'])
    return {'z':z,'transform':transform,'weights':weights,'lon':lon,'lat':lat,
            'drainage':drainage,'tau':tau,'bounds':[xmin,ymin,xmax,ymax]}


def map_rain(domain,data,cfg):
    grid=cfg['rainfall']['grid_degrees']
    lookup={(round(float(a)/grid),round(float(b)/grid)):j
            for j,(a,b) in enumerate(zip(data['latitude'],data['longitude']))}
    keys=np.c_[np.rint(domain['lat']/grid).astype(int),np.rint(domain['lon']/grid).astype(int)]
    try:return np.array([lookup[tuple(k)] for k in keys],int)
    except KeyError as e:raise ValueError('missing ERA5 source grid for cell') from e


def map_roads(domain,samples,features):
    # Reuse exact accepted source-feature positions and ground/bridge flags.
    sample=samples[samples.valid_dsm].copy()
    rr,cc=rowcol(domain['transform'],sample.x_m.to_numpy(),sample.y_m.to_numpy())
    rr=np.asarray(rr);cc=np.asarray(cc);nr,nc=domain['z'].shape
    if not ((rr>=0)&(rr<nr)&(cc>=0)&(cc<nc)).all():raise ValueError('road samples outside domain')
    sample['cell']=rr*nc+cc
    cells=np.unique(sample.cell.to_numpy())
    columns={int(c):j for j,c in enumerate(cells)}
    links={int(fid):np.array([columns[int(c)] for c in frame.cell.unique()],int)
           for fid,frame in sample.groupby('source_feature_position')}
    ids=features.source_feature_position.to_numpy()
    modelled=np.array([int(fid) in links for fid in ids])
    eligible=features.ground_model_eligible.to_numpy(bool)
    if (modelled&~eligible).any():raise ValueError('bridge/tunnel assigned depth')
    return cells,links,ids,modelled,sample


def aggregate(sample_depth,links,feature_ids,modelled):
    a=np.full((len(sample_depth),len(feature_ids)),np.nan,np.float32)
    for j in np.flatnonzero(modelled):a[:,j]=sample_depth[:,links[int(feature_ids[j])]].max(axis=1)
    return a


def summarize(case,result,road,modelled,weights,dx):
    ledger=pd.DataFrame(result['ledger']);last=ledger.iloc[-1]
    return {'case':case,'maximum_district_cell_depth_m':float(result['peak_depth_m'][weights>0].max()),
            'maximum_ground_road_sample_depth_m':float(road[:,modelled].max()),
            'maximum_modelled_source_features_over_015':int((road>.15).sum(axis=1).max()),
            'maximum_modelled_source_features_atleast_030':int((road>=.30).sum(axis=1).max()),
            'district_area_ever_over_015_km2':float(weights[result['peak_depth_m']>.15].sum()*dx**2/1e6),
            'maximum_simultaneous_area_over_015_km2':float(ledger['district_area_above_0.15_km2'].max()),
            'domain_rain_m3':float(last.cumulative_rain_m3),'domain_loss_m3':float(last.cumulative_loss_m3),
            'domain_boundary_outflow_m3':float(last.cumulative_boundary_outflow_m3),
            'domain_final_storage_m3':float(last.storage_m3),
            'maximum_step_balance_residual_m3':float(result['maximum_step_residual_m3']),
            'maximum_cumulative_balance_residual_m3':float(abs(ledger.balance_residual_m3).max())}


def build(config,rainfall_package):
    started=time.time();cfg=yaml.safe_load(config.read_text(encoding='utf-8'))
    if cfg['region']!='longgang' or cfg['include_dapeng'] is not False:raise ValueError('wrong scope')
    rid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_era5_surface_'+uuid.uuid4().hex[:8]
    out=ROOT/cfg['output_root']/rid;out.mkdir(parents=True,exist_ok=False)
    for folder in ['gis','raw','figures','provenance','verification_domain']:(out/folder).mkdir()
    print('OUTPUT '+str(out),flush=True);write(out/'status.json',{'status':'running'})
    try:
        rain=rainfall_package;od=ROOT/cfg['od_package'];prior=ROOT/cfg['road_reference_package']
        verify_files(rain,['request.json','response.json','response_metadata.json','hourly_rainfall.npz','grid_metadata.json','attribution.json','status.json'])
        verify_files(od,['study_boundary.geojson'])
        verify_files(prior,['gis/road_features.geojson','raw/road_sample_coverage.parquet','raw/od_graph_arc_mapping.csv'])
        request=json.loads((rain/'request.json').read_text(encoding='utf-8'))
        if request['params']['models']!='era5' or request['simulation_start']!=cfg['rainfall']['simulation_start'] or request['simulation_end']!=cfg['rainfall']['simulation_end']:
            raise ValueError('rain package does not match model configuration')
        data=np.load(rain/'hourly_rainfall.npz',allow_pickle=False)
        hourly=data['precipitation_mm']
        boundary=gpd.read_file(od/'study_boundary.geojson')
        if boundary.include_dapeng.any():raise ValueError('wrong boundary')
        polygon=boundary.to_crs(cfg['domain']['crs']).geometry.union_all()
        boundary.to_file(out/'gis/study_boundary.geojson',driver='GeoJSON')
        features=gpd.read_file(prior/'gis/road_features.geojson')
        samples=pd.read_parquet(prior/'raw/road_sample_coverage.parquet')
        shutil.copy2(prior/'raw/od_graph_arc_mapping.csv',out/'raw/od_graph_arc_mapping.csv')
        print('Preparing DSM and priority-flood drainage',flush=True)
        domain=make_domain(cfg,polygon,cfg['domain']['buffer_m'],out/'gis')
        grid=map_rain(domain,data,cfg)
        cells,links,ids,modelled,sample=map_roads(domain,samples,features)
        sample.to_parquet(out/'raw/road_sample_cells.parquet',index=False)
        features.to_file(out/'gis/road_features.geojson',driver='GeoJSON')
        features.drop(columns='geometry').to_csv(out/'raw/road_feature_status.csv',index=False,encoding='utf-8-sig')
        np.savez_compressed(out/'raw/routing_grid.npz',receiver=domain['drainage']['receiver'],
            rank=domain['drainage']['rank'],spill_depth_m=domain['drainage']['spill_depth_m'],
            filled_elevation_m=domain['drainage']['filled_elevation_m'],tau_s=domain['tau'],
            rain_grid_id=grid,district_weights=domain['weights'],road_cells=cells,
            source_feature_positions=ids,modelled_features=modelled)
        dx=cfg['domain']['cell_size_m'];weights=domain['weights'];nt=round(len(hourly)*60/cfg['time']['output_minutes'])+1
        print(f'Domain {domain["z"].shape}, {domain["z"].size} cells; {len(cells)} road sample cells',flush=True)
        # District mean is fractional raster intersection area weighted.
        grid_weights=np.bincount(grid,weights=weights,minlength=hourly.shape[1])/weights.sum()
        district_rain=hourly@grid_weights
        rainframe=pd.DataFrame({'time_end_local':data['time_end_local'],'district_mean_mm':district_rain})
        for j in range(hourly.shape[1]):rainframe[f'grid_{j}_mm']=hourly[:,j]
        rainframe.to_csv(out/'raw/hourly_rainfall.csv',index=False)
        summaries=[];baseline=None;base_road=None
        for name,case in cfg['cases'].items():
            print('Simulating '+name,flush=True)
            result=simulate(domain['z'],domain['drainage'],domain['tau'],hourly,grid,dx,weights,cells,cfg,case,
                            save_fields=name=='era5_baseline')
            road=aggregate(result['road_sample_depth_m'],links,ids,modelled)
            np.savez_compressed(out/f'raw/{name}_road_depth.npz',depth_m=road,
                 time_h=np.arange(nt)*cfg['time']['output_minutes']/60,
                 source_feature_positions=ids,modelled_features=modelled,observed=np.array(False))
            np.savez_compressed(out/f'raw/{name}_grid_summary.npz',peak_depth_m=result['peak_depth_m'],
                                final_depth_m=result['final_depth_m'])
            pd.DataFrame(result['ledger']).to_csv(out/f'raw/{name}_water_balance.csv',index=False)
            summaries.append(summarize(name,result,road,modelled,weights,dx))
            if name=='era5_baseline':
                baseline=result;base_road=road
                np.savez_compressed(out/'raw/baseline_depth_fields.npz',depth_m=result['depth_fields_m'],
                    shape=np.array(domain['z'].shape),time_h=np.arange(nt)*cfg['time']['output_minutes']/60)
                masked=np.where(weights>0,result['peak_depth_m'],np.nan).reshape(domain['z'].shape)
                raster_write(out/'gis/district_peak_depth_m.tif',masked,domain['transform'],cfg['domain']['crs'])
        print('Replaying baseline with smaller time step',flush=True)
        fine=simulate(domain['z'],domain['drainage'],domain['tau'],hourly,grid,dx,weights,cells,cfg,
                      cfg['cases']['era5_baseline'],dt_s=cfg['time']['verification_seconds'])
        fine_road=aggregate(fine['road_sample_depth_m'],links,ids,modelled)
        diff=abs(fine_road[:,modelled]-base_road[:,modelled])
        stepcheck={'coarse_seconds':cfg['time']['internal_seconds'],'fine_seconds':cfg['time']['verification_seconds'],
                   'maximum_road_endpoint_difference_m':float(diff.max()),'p95_road_endpoint_difference_m':float(np.quantile(diff,.95)),
                   'coarse_peak_road_m':float(base_road[:,modelled].max()),'fine_peak_road_m':float(fine_road[:,modelled].max()),
                   'acceptance_absolute_m':.02,'acceptance_relative_to_peak':.05,
                   'passed':bool(diff.max()<=.02+.05*fine_road[:,modelled].max())}
        np.savez_compressed(out/'raw/verification_fine_road_depth.npz',depth_m=fine_road)
        pd.DataFrame(fine['ledger']).to_csv(out/'raw/verification_fine_water_balance.csv',index=False)
        print('Checking larger domain boundary sensitivity',flush=True)
        extended=make_domain(cfg,polygon,cfg['domain']['buffer_verification_m'],out/'verification_domain')
        egrid=map_rain(extended,data,cfg)
        ecells,elinks,eids,emodelled,_=map_roads(extended,samples,features)
        big=simulate(extended['z'],extended['drainage'],extended['tau'],hourly,egrid,dx,extended['weights'],ecells,cfg,cfg['cases']['era5_baseline'])
        broad=aggregate(big['road_sample_depth_m'],elinks,eids,emodelled)
        bdiff=abs(broad[:,modelled]-base_road[:,modelled])
        boundarycheck={'base_buffer_m':cfg['domain']['buffer_m'],'extended_buffer_m':cfg['domain']['buffer_verification_m'],
                       'extended_grid_shape':list(extended['z'].shape),'maximum_road_endpoint_difference_m':float(bdiff.max()),
                       'p95_road_endpoint_difference_m':float(np.quantile(bdiff,.95)),
                       'extended_peak_road_m':float(broad[:,modelled].max()),
                       'full_upstream_catchment_certified':False}
        np.savez_compressed(out/'raw/verification_extended_road_depth.npz',depth_m=broad)
        pd.DataFrame(big['ledger']).to_csv(out/'raw/verification_extended_water_balance.csv',index=False)
        summary=pd.DataFrame(summaries);summary.to_csv(out/'raw/scenario_summary.csv',index=False)
        all_roads=[np.load(out/f'raw/{c}_road_depth.npz')['depth_m'] for c in cfg['cases']]
        dry=all_roads[list(cfg['cases']).index('dry_control')]
        checks={'frozen_source_hashes_match':True,'scope_excludes_dapeng':True,'rainfall_complete_and_nonnegative':True,
                'all_domain_DSM_cells_finite':bool(np.isfinite(domain['z']).all()),
                'district_area_conserved':bool(np.isclose(weights.sum()*dx*dx,polygon.area,rtol=1e-8)),
                'all_ground_road_depths_finite_nonnegative':all(np.isfinite(a[:,modelled]).all() and (a[:,modelled]>=0).all() for a in all_roads),
                'unknown_roads_remain_NaN':all(np.isnan(a[:,~modelled]).all() for a in all_roads),
                'dry_control_zero':bool((dry[:,modelled]==0).all()),
                'domain_water_balance':bool(summary.maximum_cumulative_balance_residual_m3.max()<max(1e-5,summary.domain_rain_m3.max()*1e-10)),
                'time_step_refinement':stepcheck['passed']}
        if not all(checks.values()):raise ValueError('failed numerical checks: '+str(checks))
        report={'run_id':rid,'method':'B_DSM_priority_flood_D8_linear_storage_routing',
                'region':'longgang','include_dapeng':False,'rain_source':'ERA5_reanalysis_via_Open_Meteo',
                'observed_rain_gauges':False,'observed_flood_depths':False,'calibrated':False,
                'rainfall_package':rain.relative_to(ROOT).as_posix(),'road_reference_package':cfg['road_reference_package'],
                'simulation_start':cfg['rainfall']['simulation_start'],'simulation_end':cfg['rainfall']['simulation_end'],
                'rain_hours':len(hourly),'rain_grid_count':hourly.shape[1],'rain_grids_used_in_domain':np.unique(grid).tolist(),
                'rain_grids_used_in_district':np.flatnonzero(grid_weights>0).tolist(),
                'district_mean_rain_total_mm':float(district_rain.sum()),'district_mean_max_hour_mm':float(district_rain.max()),
                'grid_shape':list(domain['z'].shape),'domain_cells':domain['z'].size,'domain_bounds_m':domain['bounds'],
                'district_area_km2':float(weights.sum()*dx*dx/1e6),'cell_size_m':dx,
                'output_endpoints':nt,'case_count':len(cfg['cases']),
                'source_features':len(ids),'modelled_ground_features':int(modelled.sum()),'unknown_features':int((~modelled).sum()),
                'road_samples':len(sample),'road_sample_cells':len(cells),
                'directed_arc_mapping_count':len(pd.read_csv(out/'raw/od_graph_arc_mapping.csv')),
                'maximum_depression_storage_threshold_m':float(domain['drainage']['spill_depth_m'].max()),
                'time_step_check':stepcheck,'boundary_sensitivity':boundarycheck,'checks':checks,'all_checks_passed':True,
                'scenarios':summaries,'elapsed_seconds':time.time()-started,
                'limitations':['ERA5 ~0.25 degree hourly forcing is reanalysis, not local gauges; no historical event calibration',
                    '30m DSM area-averaged to 150m includes canopy/buildings and does not resolve curbs or underpasses',
                    'Fixed D8 priority-flood tree and per-cell spill storage approximate routing; not 2D shallow-water hydraulics',
                    'No sewer network, groundwater, river/tide backwater, pressure flow or dynamic flow reversal',
                    '5km rectangular open boundary assumes zero external inflow; 10km replay is sensitivity, not catchment certification',
                    'Zero initial surface storage; uniform hourly rainfall; lumped loss/travel times assumed, not measured',
                    'Road values are maxima over accepted ground sample cells; bridges/tunnels remain unknown',
                    'No updated road capacity/speed, traffic assignment, resilience or SUMO run']}
        write(out/'provenance/validation_report.json',report)
        figures(out,domain,boundary,summary,baseline,rainframe,base_road,modelled,cfg)
        inputs=[config,Path(__file__),ROOT/'src/uftr/era5_surface.py',ROOT/'scripts/acquire_longgang_era5.py',
                *[ROOT/p for p in cfg['dsm_tiles']],od/'manifest.json',od/'study_boundary.geojson',
                prior/'manifest.json',prior/'gis/road_features.geojson',prior/'raw/road_sample_coverage.parquet',
                prior/'raw/od_graph_arc_mapping.csv',rain/'manifest.json',rain/'response.json',rain/'hourly_rainfall.npz',rain/'request.json']
        for p in inputs[:4]:shutil.copy2(p,out/'provenance'/p.name)
        shutil.copy2(rain/'attribution.json',out/'provenance/rainfall_attribution.json')
        write(out/'status.json',{'status':'complete_method_B_uncalibrated','run_id':rid})
        manifest={'run_id':rid,'inputs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in inputs],
                  'outputs':[{'path':p.relative_to(out).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()]}
        write(out/'manifest.json',manifest)
        with zipfile.ZipFile(str(out)+'.zip','w',zipfile.ZIP_DEFLATED,compresslevel=4) as z:
            for p in sorted(out.rglob('*')):
                if p.is_file():z.write(p,p.relative_to(out).as_posix())
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        return out
    except Exception:
        write(out/'status.json',{'status':'failed','traceback':traceback.format_exc()});raise


def figures(out,domain,boundary,summary,baseline,rainframe,road,modelled,cfg):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'svg.fonttype':'none'})
    def save(fig,name):
        for ext in ['png','svg']:fig.savefig(out/'figures'/f'{name}.{ext}',dpi=150)
        plt.close(fig)
    ledger=pd.DataFrame(baseline['ledger'])
    fig,axes=plt.subplots(3,1,figsize=(12,10),layout='constrained',sharex=True)
    axes[0].stairs(rainframe.district_mean_mm,np.arange(len(rainframe)+1),color='#267d9b')
    axes[0].set_ylabel('区内面积加权降雨 mm/h')
    axes[1].plot(ledger.time_h,ledger.district_max_cell_depth_m,label='区内最大网格')
    axes[1].plot(ledger.time_h,road[:,modelled].max(axis=1),label='地面道路样点最大值')
    axes[1].set_ylabel('估计蓄水深度 m');axes[1].legend()
    axes[2].plot(ledger.time_h,ledger['district_area_above_0.15_km2'])
    axes[2].set_ylabel('估计深度 > 0.15 m面积 km²');axes[2].set_xlabel('自2023-09-06 00:00起 小时（北京时间）')
    for ax in axes:ax.grid(alpha=.2);ax.set_xlim(0,len(rainframe));ax.set_ylim(bottom=0)
    fig.suptitle('龙岗不含大鹏：ERA5驱动的B方案研究原型\n再分析降雨＋150 m DSM地形汇流；排水假设未标定，非实测灾情')
    save(fig,'era5_surface_process')
    fig,axes=plt.subplots(1,2,figsize=(14,6),layout='constrained')
    extent=domain['bounds'];extent=[extent[0],extent[2],extent[1],extent[3]]
    z=domain['z'];weights=domain['weights'].reshape(z.shape)
    axes[0].imshow(z,extent=extent,cmap='terrain');axes[0].set_title('30 m DSM面积平均至150 m')
    peak=np.where(weights>0,baseline['peak_depth_m'].reshape(z.shape),np.nan)
    im=axes[1].imshow(peak,extent=extent,cmap='YlOrRd',vmin=0,vmax=max(.15,float(np.nanquantile(peak,.995))));fig.colorbar(im,ax=axes[1],label='估计蓄水深度 m（颜色截至99.5分位）')
    axes[1].set_title('各网格各自峰值，非同一时刻淹没图')
    for ax in axes:
        boundary.to_crs(cfg['domain']['crs']).boundary.plot(ax=ax,color='#192e3c',linewidth=.6)
        ax.set_xlabel('UTM 50N 东向 m');ax.set_ylabel('北向 m')
    fig.suptitle('B方案空间结果：DSM与固定D8蓄泄近似，不能解释为精细街道水动力预测')
    save(fig,'era5_surface_map')
    fig,axes=plt.subplots(1,2,figsize=(14,6),layout='constrained')
    axes[0].barh(summary.case,summary.maximum_ground_road_sample_depth_m,color='#347f98')
    axes[0].set_xlabel('各参数组地面道路样点最大估计深度 m')
    axes[1].plot(ledger.time_h,ledger.cumulative_rain_m3/1e6,label='累计降雨')
    accounted=ledger.cumulative_loss_m3+ledger.cumulative_boundary_outflow_m3+ledger.storage_m3
    axes[1].plot(ledger.time_h,accounted/1e6,ls='--',label='损失＋边界排出＋现存蓄水')
    axes[1].set_xlabel('小时');axes[1].set_ylabel('全计算域水量 百万m³');axes[1].legend()
    fig.suptitle('假设敏感性与全计算域水量记账\n水量平衡通过不等于模型已实测标定')
    save(fig,'era5_surface_sensitivity_balance')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default='configs/longgang_era5_surface.yaml')
    p.add_argument('--rainfall',required=True)
    args=p.parse_args();build((ROOT/args.config).resolve(),(ROOT/args.rainfall).resolve())
