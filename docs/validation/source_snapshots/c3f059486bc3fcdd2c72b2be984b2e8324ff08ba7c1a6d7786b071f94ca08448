"""Acquire spatial context, retain missing-data evidence and map synthetic risk."""
from pathlib import Path
import json
import sys
import shutil
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import shape
from .archive import RunArchive, file_hash, now, write_json
from .config import load_config
from .spatial import (clip_rasters, read_osm_facilities, read_gsod, normalize_points,
                      match_surface_roads, synthetic_risk_points)
from .spatial_sources import acquire_sources, seal_snapshot, verify_snapshot


def plot_context(edges, points, mapping_frame, pois, dem, population, rainfall, directory, run_id, dpi):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from rasterio.plot import show
    road=edges.to_crs(32650)
    # Plot the mainland road extent. Full study window and islands remain in all data files.
    bounds=road.total_bounds; x0,y0,x1,y1=bounds
    if x1-x0>40000: x0=x1-40000
    def base(title):
        fig,ax=plt.subplots(figsize=(10,9))
        fig.subplots_adjust(left=.12,right=.97,top=.9,bottom=.14)
        ax.add_collection(LineCollection([list(g.coords) for g in road.geometry],colors='#8196a5',linewidths=.35,alpha=.6))
        ax.set_xlim(x0-300,x1+300);ax.set_ylim(y0-300,y1+300);ax.set_aspect('equal')
        ax.ticklabel_format(style='plain',useOffset=False)
        ax.set_xlabel('Easting (m), EPSG:32650');ax.set_ylabel('Northing (m), EPSG:32650')
        ax.set_title(title)
        return fig,ax
    paths=[]
    def save(fig,name):
        fig.text(.01,.025,f'© OpenStreetMap contributors, ODbL 1.0 | {run_id}',fontsize=8)
        p=directory/(name+'.png');fig.savefig(p,dpi=dpi);plt.close(fig);paths.append(p)
    fig,ax=base('Synthetic clustered risk points on real roads\nGeometric match confidence only; no observed flood locations')
    selected=mapping_frame[mapping_frame.selected_geometry].drop_duplicates('point_id').set_index('point_id')
    pt=points.to_crs(32650).copy()
    pt['confidence']=pt.point_id.map(selected.match_confidence).fillna('unmatched')
    for category,color in [('high','#2a8f64'),('medium','#db9b30'),('low','#c64545'),('unmatched','#333333')]:
        part=pt[pt.confidence.eq(category)]
        ax.scatter(part.geometry.x,part.geometry.y,s=28,c=color,edgecolors='white',linewidths=.4,label=f'{category}: {len(part)}',zorder=5)
    ax.legend(loc='lower left',title='Geometric association')
    save(fig,'synthetic_risk_map')
    fig,ax=base('OSM hospital / fire-station inventory\nIncomplete coverage; polygon interior points are not verified entrances')
    projected=pois.to_crs(32650)
    for category,color,marker in [('hospital','#b33e4b','P'),('fire_station','#de8f22','^'),('emergency_shelter','#418e56','s'),('assembly_point','#79539d','o')]:
        part=projected[projected.category.eq(category)]
        ax.scatter(part.geometry.x,part.geometry.y,s=35,c=color,marker=marker,label=f'{category}: {len(part)}',zorder=5)
    ax.legend(loc='lower left',fontsize=9)
    save(fig,'facilities_map')
    # These are source-grid maps, with their true units, not downscaled predictions.
    fig,axes=plt.subplots(1,2,figsize=(12,5.8))
    for ax,path,title,cmap in [(axes[0],dem,'Copernicus GLO-30 DSM (m)\nSurface includes buildings / vegetation','terrain'),(axes[1],population,'WorldPop 2020 UN-adjusted estimate\nPeople per native ~1 km cell','magma')]:
        with rasterio.open(path) as src:
            values=src.read(1,masked=True)
            image=ax.imshow(values,extent=[src.bounds.left,src.bounds.right,src.bounds.bottom,src.bounds.top],cmap=cmap,origin='upper')
            fig.colorbar(image,ax=ax,shrink=.7)
        ax.set_title(title,fontsize=11);ax.set_xlabel('Longitude (WGS84)');ax.set_ylabel('Latitude (WGS84)')
    fig.subplots_adjust(left=.07,right=.98,bottom=.2,top=.87,wspace=.33)
    fig.text(.02,.08,'Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018\nprovided under COPERNICUS by the European Union and ESA; all rights reserved. WorldPop: CC BY 4.0\nPopulation cells retained on native grid; no resampling into 30 m counts.',fontsize=8)
    save(fig,'terrain_population')
    subset=rainfall[rainfall.date_gmt.between('2023-09-01','2023-09-15')]
    fig,ax=plt.subplots(figsize=(10,5))
    ax.bar(pd.to_datetime(subset.date_gmt),subset.precipitation_mm,color='#4b88ae')
    ax.set_title('Baoan International station 59493099999: reported daily precipitation\nRegional context only; not Nanshan areal rainfall or 15-minute observations')
    ax.set_ylabel('Reported precipitation (mm)');ax.set_xlabel('NOAA GSOD nominal date (GMT); accumulation may include previous day')
    fig.autofmt_xdate(rotation=35);fig.subplots_adjust(left=.1,right=.97,bottom=.28,top=.82)
    fig.text(.01,.025,f'NOAA NCEI GSOD 2023 | {run_id} | Inches × 25.4; missing/insufficient reports remain missing',fontsize=8)
    p=directory/'rainfall_daily.png';fig.savefig(p,dpi=dpi);plt.close(fig);paths.append(p)
    return paths


def run_phase02(root, config_path, offline_source=None):
    config=load_config(config_path)
    if config['phase']!='02': raise ValueError('Phase 02 configuration required')
    settings=config['spatial']
    network_dir=(root/settings['network_directory']).resolve();network_dir.relative_to(root)
    osm_snapshot=(root/settings['osm_snapshot']).resolve();osm_snapshot.relative_to(root)
    # Verify every source tile against the earlier sealed snapshot before reuse.
    earlier=verify_snapshot(osm_snapshot)
    boundary=gpd.read_file(network_dir/'study_boundary.geojson').to_crs(4326).geometry.iloc[0]
    contract={'network_inventory_sha256':file_hash(network_dir.parent/'output_inventory.json'),
              'osm_inventory_sha256':file_hash(osm_snapshot/'source_inventory.json'),
              'source_specs':settings['sources']}
    initial=[config_path,*sorted((root/'src/uftr').glob('*.py')),network_dir.parent/'output_inventory.json']
    with RunArchive(root,config,initial) as run:
        run.manifest['command']=[sys.executable,*sys.argv]
        if offline_source:
            snapshot=(root/offline_source).resolve();snapshot.relative_to(root)
            verify_snapshot(snapshot,contract)
        else:
            snapshot=root/'data/raw/phase02'/run.run_id
            records=acquire_sources(snapshot,settings['sources'])
            write_json(snapshot/'acquisition_report.json',{'sources':records,'accessed_at':now(),
                'official_portal_note':'Public catalog only. Download requires real-name login; no official georeferenced flood/monitoring records acquired.'})
            seal_snapshot(snapshot,contract)
        # Protect earlier outputs too, rather than trusting only an inventory filename.
        inventory=json.loads((network_dir.parent/'output_inventory.json').read_text(encoding='utf-8'))
        for item in inventory['files']:
            p=(network_dir.parent/item['path']).resolve();p.relative_to(network_dir.parent)
            if file_hash(p)!=item['sha256']:raise ValueError('Phase 01 processed output checksum mismatch')
        run.manifest['inputs'].extend({'path':str(p.resolve()),'sha256':file_hash(p)} for p in sorted(snapshot.rglob('*')) if p.is_file())
        run.manifest['inputs'].extend({'path':str((osm_snapshot/item['path']).resolve()),'sha256':item['sha256']} for item in earlier['files'])
        run.manifest['inputs'].extend({'path':str((network_dir/n).resolve()),'sha256':file_hash(network_dir/n)} for n in ['road_edges.geojson','study_boundary.geojson'])
        run.flush()
        output=root/'data/processed/phase02'/run.run_id;output.mkdir(parents=True,exist_ok=False)
        synthetic=root/'data/synthetic/phase02'/run.run_id;synthetic.mkdir(parents=True,exist_ok=False)
        run.log('clip DSM and native population raster')
        dem=output/'copernicus_dsm_30m.tif';pop=output/'population_2020_native_1km.tif'
        terrain=clip_rasters([snapshot/n for n in ['dem_e113.tif','dem_e114.tif']],boundary,dem)
        population=clip_rasters([snapshot/'population_2020_1km.tif'],boundary,pop)
        terrain.update(dataset='Copernicus GLO-30 DSM, AWS 2021 release', vertical_datum='EGM2008',
            acquisition_period='TanDEM-X 2011-2015 with older gap-filling sources',
            attribution='Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved')
        population.update(dataset='WorldPop 2020 aggregated 1 km UN-adjusted population counts',
                          year=2020,units='estimated people per native cell',license='CC BY 4.0')
        edges=gpd.read_file(network_dir/'road_edges.geojson')
        run.log('extract facilities from original unfiltered OSM XML')
        pois,poi_quality=read_osm_facilities(osm_snapshot/'nanshan',boundary)
        pois.to_file(output/'facilities.geojson',driver='GeoJSON')
        rain=read_gsod(snapshot/'baoan_gsod_2023.csv',settings['rain_station'])
        rain.to_csv(output/'rainfall_timeseries.csv',index=False,encoding='utf-8-sig')
        write_json(output/'flood_points.geojson',{'type':'FeatureCollection','features':[],
                    'data_status':'No official georeferenced flood/monitoring records acquired; missing is not zero flood risk'})
        run.log('generate explicitly synthetic low-DSM clustered risk locations')
        points=synthetic_risk_points(edges,boundary,dem,settings['synthetic_risk'],config['seed'])
        points=normalize_points(points,boundary)
        points.to_file(synthetic/'flood_points.geojson',driver='GeoJSON')
        matched=match_surface_roads(points,edges,settings['matching'])
        matched.to_csv(output/'flood_road_mapping.csv',index=False,encoding='utf-8-sig')
        poi_input=pois.rename(columns={'poi_id':'point_id'})
        poi_mapping=match_surface_roads(poi_input,edges,settings['matching'])
        poi_mapping.to_csv(output/'facility_road_candidates.csv',index=False,encoding='utf-8-sig')
        selected=matched[matched.selected_geometry].drop_duplicates('point_id')
        point_conf=selected.match_confidence.value_counts().to_dict()
        point_conf['unmatched']=len(points)-len(selected)
        year2023=rain[rain.date_gmt.str.startswith('2023-')]
        event=rain[rain.date_gmt.isin(['2023-09-07','2023-09-08'])]
        quality={'run_id':run.run_id,'status':'passed_with_explicit_data_gaps','processed_root':output.relative_to(root).as_posix(),
            'synthetic_root':synthetic.relative_to(root).as_posix(),'source_snapshot':snapshot.relative_to(root).as_posix(),
            'dem':terrain,'population':population,'facilities':poi_quality,
            'rainfall':{'station_id':settings['rain_station'],'name':'BAOAN INTERNATIONAL','records':len(rain),
                        'valid_records':int(rain.valid.sum()),'year_2023_records':len(year2023),
                        'source_flag_counts':rain.source_flag.value_counts().to_dict(),
                        'event_daily_records':event.astype(object).where(pd.notna(event),None).to_dict('records'),
                        'time_note':'GMT nominal report dates, may include previous day; no hourly/15-minute disaggregation'},
            'flood':{'observed_points':0,'observed_depth_records':0,'synthetic_risk_points':len(points),
                     'geometric_match_point_counts':point_conf,'candidate_rows':len(matched),
                     'excluded_vertical_candidate_rows':int(matched.exclusion_reason.fillna('').ne('').sum()),
                     'selected_directed_edge_rows':int(matched.selected_geometry.sum()),
                     'confidence_note':'Geometric association only. No point is an observed flood event; selection never declares road flooded.'},
            'limitations':['No official historical georeferenced flood points or road depth monitoring acquired',
                           'Copernicus GLO-30 is DSM, not bare-earth drainage DTM; no hydraulic calibration',
                           'WorldPop 2020 UN-adjusted ~1 km modelled counts, not 2023/2026 census or daytime traffic demand',
                           'Native population cells use centre-in-polygon inclusion, with boundary and coastal uncertainty',
                           'OSM POIs incomplete; polygon points and road candidates are not verified facility entrances',
                           'OSM assembly points are separate from designated emergency shelters',
                           'Airport daily rainfall outside Nanshan is regional context, not local areal or 15-minute input'],
            'required_outputs':['flood_points.geojson','flood_road_mapping.csv','rainfall_timeseries.csv'],
            'synthetic_parameters':settings['synthetic_risk'],'matching_parameters':settings['matching']}
        write_json(output/'data_quality_report.json',quality)
        write_json(run.path/'raw/spatial_report.json',quality)
        sources=[output/'data_quality_report.json',synthetic/'flood_points.geojson',output/'flood_road_mapping.csv',
                 output/'facilities.geojson',output/'rainfall_timeseries.csv',dem,pop,network_dir/'road_edges.geojson']
        run.log('render actual GIS maps and station rainfall')
        plots=plot_context(edges,points,matched,pois,dem,pop,rain,run.path/'figures',run.run_id,config['outputs']['dpi'])
        for path in plots:
            run.add_artifact(path,title={'synthetic_risk_map':'合成地形风险点与几何匹配置信度','facilities_map':'真实OSM应急设施不完整清单','terrain_population':'Copernicus DSM与WorldPop人口原生栅格','rainfall_daily':'宝安机场2023年9月逐日雨量'}[path.stem],
                             kind='figure',data_kind='mixed' if path.stem=='synthetic_risk_map' else 'real',source_paths=sources,
                             units={'length':'m','rainfall':'mm','population':'estimated people per native cell'})
        write_json(output/'output_inventory.json',{'run_id':run.run_id,'files':[
            {'path':p.relative_to(root).as_posix(),'sha256':file_hash(p)}
            for folder in [output,synthetic] for p in sorted(folder.rglob('*')) if p.is_file()]})
        print(json.dumps(quality,ensure_ascii=False),flush=True)
    return run.path
