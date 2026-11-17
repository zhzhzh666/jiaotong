"""Preserve user-supplied water-level tables and geocodes without inventing depth.

User-derived risk labels/durations are retained, not taken as observed road
closure. SW has no verified original unit/datum until source documentation is
provided. Geocodes are approximate, not surveyed sensor locations.
"""
from pathlib import Path
from zipfile import ZipFile
import json
import shutil
import geopandas as gpd
import numpy as np
import pandas as pd
from .archive import file_hash, now, write_json
from .spatial import match_surface_roads


def risk_band(values):
    """User-confirmed processing thresholds, not a road closure criterion."""
    x=np.asarray(values,float)
    return np.select([x<.15,x<.30,x<.40],['蓝Ⅳ','黄Ⅲ','橙Ⅱ'],default='红Ⅰ')


def seal_user_sources(root, filenames, snapshot):
    snapshot.mkdir(parents=True,exist_ok=False)
    files=[]
    for name in filenames:
        source=(root/name).resolve();source.relative_to(root)
        if source.parent != root.resolve():raise ValueError('user source must be an explicitly listed root file')
        shutil.copyfile(source,snapshot/name)
        files.append({'path':name,'bytes':source.stat().st_size,'sha256':file_hash(source)})
    write_json(snapshot/'source_inventory.json',{'created_at':now(),'source_kind':'user_supplied_derived',
        'source_url':None,'source_platform':'深圳市政府数据开放平台 (user attestation)',
        'user_attestation':'User scraped platform water levels, selected high-water dates; 45 stations; platform addresses geocoded using Amap. Exact dataset/API URL not supplied.',
        'original_unit_and_vertical_reference':'not independently verified',
        'risk_thresholds_m_user_confirmed':[0.15,0.30,0.40],
        'datum_user_interpretation':'User infers road-relative depth because dry-weather SW is usually near zero; platform does not state the zero datum. Treat as plausible interpretation, not verified datum.',
        'coordinates':'CSV claims WGS84 converted from geocoded GCJ02; not surveyed sensor coordinates',
        'files':files})
    return snapshot


def inspect_user_water(snapshot, output, boundary, edges, matching):
    inventory=json.loads((snapshot/'source_inventory.json').read_text(encoding='utf-8'))
    for item in inventory['files']:
        path=(snapshot/item['path']).resolve();path.relative_to(snapshot.resolve())
        if file_hash(path)!=item['sha256']:raise ValueError('user source snapshot changed')
    def read(name):return pd.read_csv(snapshot/name,encoding='utf-8-sig',dtype={'CZBM':str,'ID':str})
    stations=read('深圳积涝测站_带坐标汇总.csv')
    levels=read('9·7暴雨_全量水位_带分级.csv')
    filtered=read('9·7暴雨_洪涝水位记录_带坐标.csv')
    summary=read('9·7暴雨_测站洪涝指标汇总(1).csv')
    if stations.CZBM.duplicated().any() or levels.ID.duplicated().any() or levels.duplicated(['CZBM','SJ']).any():
        raise ValueError('duplicate station, record ID or station timestamp')
    if not set(levels.CZBM).issubset(set(stations.CZBM)):raise ValueError('unknown station code')
    levels['SW']=pd.to_numeric(levels.SW,errors='raise')
    parsed=pd.to_datetime(levels.SJ,errors='raise')
    if not np.isfinite(levels.SW).all():raise ValueError('nonfinite user water level')
    bands=risk_band(levels.SW)
    if not np.array_equal(bands,levels['风险等级'].str.split('(').str[0].to_numpy()):raise ValueError('water risk labels disagree with user-confirmed thresholds')
    if not np.array_equal(levels.SW.ge(.15).to_numpy(),levels['是否洪涝'].to_numpy()):raise ValueError('source flood flag inconsistent with confirmed processing threshold')
    if not np.isfinite(stations[['经度WGS84','纬度WGS84']].to_numpy(float)).all():raise ValueError('nonfinite user geocode')
    if not stations['经度WGS84'].between(-180,180).all() or not stations['纬度WGS84'].between(-90,90).all():raise ValueError('invalid claimed geographic coordinate')
    sites=gpd.GeoDataFrame(stations.copy(),geometry=gpd.points_from_xy(stations['经度WGS84'],stations['纬度WGS84']),crs=4326)
    sites['point_id']='user_station_'+sites.CZBM
    sites['source_kind']='user_supplied_derived_geocode'
    sites['within_study']=sites.geometry.map(boundary.covers)
    sites['location_verified']=False
    sites['depth_verified']=False
    sites['geocoding_warning']=sites['方式'].str.contains('东莞',na=False)
    peak=levels.groupby('CZBM').SW.max()
    peak_difference=(peak-stations.set_index('CZBM')['峰值水位m']).abs()
    subset=levels[levels['是否洪涝'].eq(True)].sort_values('ID').reset_index(drop=True)
    check=filtered.sort_values('ID').reset_index(drop=True)
    subset_consistent=len(subset)==len(check) and subset.ID.equals(check.ID) and np.array_equal(subset.SW,check.SW)
    if not subset_consistent:raise ValueError('filtered water records disagree with full source')
    zips=[]
    for item in inventory['files']:
        if not item['path'].endswith('.zip'):continue
        with ZipFile(snapshot/item['path']) as archive:
            names=[n for n in archive.namelist() if n.endswith('.geojson')]
            if len(names)!=1:raise ValueError('expected one GeoJSON in source archive')
            content=json.loads(archive.read(names[0]).decode('utf-8-sig'))
            features=content.get('features',[])
            for feature in features:
                code=str(feature['properties']['CZBM'])
                site=sites.set_index('CZBM').loc[code]
                if max(abs(feature['geometry']['coordinates'][0]-site.geometry.x),abs(feature['geometry']['coordinates'][1]-site.geometry.y))>1e-6:
                    raise ValueError('zipped GeoJSON geocode disagrees with CSV')
            zips.append({'archive':item['path'],'features':len(features),
                         'input_crs_declaration':content.get('crs'),
                         'note':'Nonstandard string CRS in source retained; normalized derived output uses standard GeoJSON WGS84'})
    output.mkdir(parents=True,exist_ok=False)
    sites.to_file(output/'user_stations_all.geojson',driver='GeoJSON')
    local=sites[sites.within_study].copy()
    local.to_file(output/'user_stations_in_study.geojson',driver='GeoJSON')
    joined=levels.merge(stations[['CZBM','经度WGS84','纬度WGS84','行政区','地址']],on='CZBM',validate='many_to_one')
    joined=joined.rename(columns={'SW':'water_level_raw','SJ':'timestamp_raw','风险等级':'source_derived_risk_label','是否洪涝':'source_derived_flood_flag'})
    joined['source_kind']='user_supplied_water_level_unverified_reference'
    joined['unit_claimed_by_summary']='m'
    joined['original_SW_unit_verified']=False
    joined['vertical_reference_verified']=False
    joined['timestamp_timezone']='not specified in source'
    joined['usable_as_road_depth']=False
    joined.sort_values(['CZBM','timestamp_raw','ID']).to_csv(output/'user_water_levels_all.csv',index=False,encoding='utf-8-sig')
    joined[joined.CZBM.isin(local.CZBM)].to_csv(output/'user_water_levels_in_study.csv',index=False,encoding='utf-8-sig')
    mapping=match_surface_roads(local,edges,matching)
    mapping['overall_location_confidence']='unverified_geocode'
    mapping['usable_as_road_flood_exposure']=False
    mapping.to_csv(output/'user_station_road_candidates.csv',index=False,encoding='utf-8-sig')
    cadence=[]
    for code,group in levels.groupby('CZBM'):
        stamps=pd.to_datetime(group.SJ).sort_values()
        differences=stamps.diff().dt.total_seconds().dropna()
        flagged=group[group['是否洪涝'].eq(True)]
        span=(pd.to_datetime(flagged.SJ).max()-pd.to_datetime(flagged.SJ).min()).total_seconds()/60 if len(flagged) else 0.
        cadence.append({'station_id':code,'records':len(group),'median_interval_s':float(differences.median()) if len(differences) else None,
            'max_interval_s':float(differences.max()) if len(differences) else None,
            'gaps_over_10min':int((differences>600).sum()),'flagged_records':len(flagged),
            'first_to_last_flag_span_min':span,
            'source_duration_min':float(summary.set_index('CZBM').loc[code,'达涝时长min']),
            'duration_note':'First-to-last span includes gaps and returns below threshold; not verified cumulative inundation duration'})
    pd.DataFrame(cadence).to_csv(output/'station_sampling_quality.csv',index=False,encoding='utf-8-sig')
    quality={'source_kind':'user_supplied_platform_water_levels_with_address_geocodes','stations':len(sites),
        'source_platform':inventory['source_platform'],'user_attestation':inventory['user_attestation'],
        'risk_thresholds_m_user_confirmed':[0.15,0.30,0.40],
        'risk_labels_match_confirmed_thresholds':True,
        'datum_user_interpretation':'Dry-weather SW near zero supports suspected road-relative depth, but the platform does not specify the zero datum; unverified interpretation',
        'water_level_records':len(levels),'source_flagged_records':len(filtered),
        'source_flagged_stations':int(filtered.CZBM.nunique()),
        'timestamp_min_raw':str(parsed.min()),'timestamp_max_raw':str(parsed.max()),
        'water_level_raw_min':float(levels.SW.min()),'water_level_raw_max':float(levels.SW.max()),
        'district_label_nanshan_stations':int(stations['行政区'].eq('南山区').sum()),
        'stations_within_study':len(local),'records_within_study':int(levels.CZBM.isin(local.CZBM).sum()),
        'suspicious_geocode_station_ids':sites.loc[sites.geocoding_warning,'CZBM'].to_list(),
        'summary_peak_max_difference':float(peak_difference.max()),'filtered_subset_exactly_matches_full':bool(subset_consistent),
        'source_label_ranges':levels.groupby('风险等级').SW.agg(['count','min','max']).reset_index().to_dict('records'),
        'source_zip_checks':zips,'depth_adoption_status':'quarantined_from_road_depth_until_original_unit_and_vertical_reference_verified',
        'limitations':['User confirms Shenzhen open-data platform and Amap address geocoding; exact dataset/API URL and original field dictionary not supplied yet',
                       'CSV peak column claims metres; SW original unit and zero datum not verified',
                       'Address/POI geocodes, not sensor surveyed coordinates; a Dongguan POI match is flagged',
                       'District labels not used to override spatial study boundary',
                       'Source risk classes and flood flag are derived labels, not observed vehicle closure',
                       'Sampling irregular; no interpolation or missing-to-zero fill',
                       'First/last flagged time span is not continuous inundation duration']}
    write_json(output/'user_water_quality.json',quality)
    return quality,sites,joined
