"""Audit supplied OSM files and select Longgang/Dapeng source features, not a graph.

Documents are read as provenance, never executed. Raw files and previous runs stay
unchanged. No endpoint-only graph is offered as a verified road topology.
"""
from pathlib import Path
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4
import json
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
import argparse

import geopandas as gpd
import pandas as pd
import rasterio
from shapely.geometry import box, Point
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]


def digest(p):
    return sha256(Path(p).read_bytes()).hexdigest()


def write(p, value):
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def run(config):
    cfg = yaml.safe_load(config.read_text(encoding='utf-8'))
    source = ROOT/cfg['source_directory']
    original = json.loads((source/'source_manifest.json').read_text(encoding='utf-8-sig'))
    for entry in original:
        assert digest(source/entry['name']) == entry['sha256'], entry['name']
    extracted = source/'extracted'
    extracted.mkdir(exist_ok=True)
    archives = []
    for p in sorted(source.glob('*.zip')):
        with zipfile.ZipFile(p) as z:
            assert z.testzip() is None
            members = []
            for info in z.infolist():
                target = (extracted/info.filename).resolve()
                assert target.is_relative_to(extracted.resolve()) and not info.is_dir()
                content = z.read(info)
                if target.exists():
                    assert target.read_bytes() == content, info.filename
                else:
                    target.parent.mkdir(exist_ok=True, parents=True)
                    target.write_bytes(content)
                members.append({'name': info.filename, 'bytes': len(content), 'sha256': sha256(content).hexdigest()})
            archives.append({'name': p.name, 'crc_passed': True, 'members': members})
    for a, b in [('深圳OSM路网数据字段说明(1).docx', '深圳OSM路网数据字段说明.docx'),
                 ('道路等级统计(1).csv', '道路等级统计.csv')]:
        assert (source/a).read_bytes() == (extracted/b).read_bytes()
    with zipfile.ZipFile(source/'深圳OSM路网数据字段说明(1).docx') as z:
        xml = ET.fromstring(z.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs = [''.join(t.text or '' for t in p.findall('.//w:t', ns)) for p in xml.findall('.//w:p', ns)]
        (source/'field_dictionary.txt').write_text('\n'.join(paragraphs), encoding='utf-8')

    gpkg = extracted/'深圳OSM路网.gpkg'
    with sqlite3.connect('file:'+gpkg.resolve().as_posix()+'?mode=ro', uri=True) as con:
        integrity = con.execute('pragma quick_check').fetchone()[0]
        assert integrity == 'ok'
        layers = []
        for name, srs in con.execute('select table_name,srs_id from gpkg_contents').fetchall():
            assert name in {'motor_shenzhen', 'all_roads_shenzhen', 'motor_all_bbox'}
            count = con.execute('select count(*) from "'+name+'"').fetchone()[0]
            layers.append({'name': name, 'features': count, 'srs_id': srs})
    roads = gpd.read_file(gpkg, layer=cfg['network_layer'], fid_as_index=True)
    duplicate = gpd.read_file(extracted/'深圳机动车路网.geojson')
    assert roads.crs.to_epsg() == 4326 and duplicate.crs.to_epsg() == 4326
    assert len(roads) == len(duplicate)
    assert roads.osm_id.astype(str).tolist() == duplicate.osm_id.astype(str).tolist()
    assert roads.geometry.to_wkb().tolist() == duplicate.geometry.to_wkb().tolist()
    assert roads.length_m.tolist() == duplicate.length_m.tolist()
    boundary_json = json.loads((extracted/'深圳市行政区边界.json').read_text(encoding='utf-8-sig'))
    boundary = gpd.read_file(extracted/'深圳市行政区边界.json')
    district = boundary[boundary.adcode.astype(str).eq(str(cfg['scope_adcode']))].copy()
    assert len(district) == 1 and district.geometry.is_valid.all()
    source_geom = district.geometry.union_all()
    geom = source_geom
    include_dapeng = bool(cfg['include_dapeng'])
    scope_method = 'whole supplied 440307 geometry'
    removed_geom = None
    if not include_dapeng:
        if cfg.get('scope_selection') != 'component_covering_supplied_district_center':
            raise ValueError('Explicit mainland component selection required')
        # This bundle has two separate polygon components. Do not select by area:
        # the Dapeng component is slightly larger than the Longgang mainland.
        if source_geom.geom_type != 'MultiPolygon' or len(source_geom.geoms) != 2:
            raise ValueError('Review changed source boundary before excluding Dapeng')
        center = Point(*district.iloc[0]['center'])
        parts = [part for part in source_geom.geoms if part.covers(center)]
        if len(parts) != 1:
            raise ValueError('District center must identify exactly one component')
        geom = parts[0]
        removed_geom = source_geom.difference(geom)
        assert geom.is_valid and not geom.intersects(removed_geom)
        scope_method = 'retain supplied polygon covering its Longgang district center; exclude other Dapeng polygon'
        district.geometry = [geom]
    district['include_dapeng'] = include_dapeng
    district['scope_selection_method'] = scope_method
    selection = roads[roads.intersects(geom)].copy()
    selection.insert(0, 'source_feature_id', ['motor_shenzhen_fid_'+str(v) for v in selection.index])
    selection['selection_rule'] = 'whole source feature intersects selected study polygon'
    selection['topology_ready'] = False

    stations = gpd.read_file(ROOT/cfg['station_source']).to_crs(4326)
    selected_stations = stations[stations.geometry.covered_by(geom)].copy()
    selected_stations = selected_stations.rename(columns={'within_study': 'within_previous_nanshan_study'})
    selected_stations['within_longgang_supplied_boundary'] = True
    selected_stations['include_dapeng_in_scope'] = include_dapeng
    selected_stations['district_label_conflict'] = ~selected_stations['行政区'].eq('龙岗区')
    projected = selection.to_crs(cfg['projected_crs'])
    candidates = gpd.sjoin_nearest(selected_stations.to_crs(cfg['projected_crs']),
        projected[['source_feature_id', 'osm_id', 'highway', 'bridge', 'tunnel', 'layer', 'geometry']],
        how='left', distance_col='candidate_distance_m')
    # A nearest feature is only a candidate; retain ties and original geocoding flags.
    candidates['road_association_verified'] = False
    water = pd.read_csv(ROOT/cfg['water_source'], dtype={'CZBM': str})
    levels = water[water.CZBM.isin(selected_stations.CZBM.astype(str))].copy()
    label_only = levels[levels.CZBM.isin(selected_stations.loc[~selected_stations.district_label_conflict, 'CZBM'])]
    rasters = []
    for key in ['population_source', 'dsm_source']:
        with rasterio.open(ROOT/cfg[key]) as ds:
            transformed = district.to_crs(ds.crs).geometry.union_all()
            rasters.append({'role': key, 'path': cfg[key], 'crs': str(ds.crs),
                'resolution': list(ds.res), 'extent_covers_boundary': box(*ds.bounds).covers(transformed),
                'note': 'Extent check only; valid pixel coverage and Longgang clipping not yet audited'})

    name = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%dT%H%M%S')+'_longgang_intake_'+uuid4().hex[:8]
    out = ROOT/cfg['output_root']/name
    out.mkdir(parents=True, exist_ok=False)
    district.to_file(out/'study_boundary_supplied.geojson', driver='GeoJSON')
    if removed_geom is not None:
        gpd.GeoDataFrame({'name':['excluded Dapeng component'],'source_adcode':[cfg['scope_adcode']]},
            geometry=[removed_geom],crs=boundary.crs).to_file(out/'excluded_dapeng_boundary.geojson',driver='GeoJSON')
    selection.to_file(out/'road_features_intersecting.geojson', driver='GeoJSON')
    selected_stations.to_file(out/'water_stations_candidates.geojson', driver='GeoJSON')
    levels.to_csv(out/'water_records_candidates.csv', index=False, encoding='utf-8-sig')
    candidates.drop(columns='geometry').to_csv(out/'station_road_candidates.csv', index=False, encoding='utf-8-sig')
    stats = selection.groupby('highway', dropna=False).agg(features=('osm_id','size'),
        whole_feature_length_m=('length_m','sum')).reset_index()
    stats.to_csv(out/'road_class_summary.csv', index=False, encoding='utf-8-sig')
    label_summary = selected_stations[['CZBM','行政区','district_label_conflict']].merge(
        levels.groupby('CZBM').agg(records=('CZBM','size'), observed_SW_peak_m=('water_level_raw','max')).reset_index(),
        on='CZBM', validate='one_to_one')
    label_summary.to_csv(out/'station_selection_summary.csv', index=False, encoding='utf-8-sig')

    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    fig, ax = plt.subplots(figsize=(11,8))
    selection.plot(ax=ax, color='#8396a4', linewidth=.35)
    district.boundary.plot(ax=ax, color='#263c50', linewidth=1)
    selected_stations[~selected_stations.district_label_conflict].plot(ax=ax, color='#d55e00', markersize=30, zorder=4)
    selected_stations[selected_stations.district_label_conflict].plot(ax=ax, color='#8a2be2', marker='x', markersize=55, zorder=5)
    short_scope = '包含大鹏' if include_dapeng else '不含大鹏'
    ax.set_title(f'龙岗研究范围（{short_scope}）\n{len(selection):,}条候选道路线与{len(selected_stations)}个候选积涝站', fontsize=16)
    ax.set_xlabel('经度 / WGS84标称坐标');ax.set_ylabel('纬度 / WGS84标称坐标')
    ax.set_aspect(1/__import__('math').cos(__import__('math').radians(22.65)))
    consistent=int((~selected_stations.district_label_conflict).sum())
    conflict=int(selected_stations.district_label_conflict.sum())
    fig.text(.08,.025,f'橙点：{consistent}个龙岗标签站；紫叉：{conflict}个行政区标签冲突站。边界基准与测站位置待核实。\n© OpenStreetMap contributors，ODbL 1.0；道路为几何要素，尚未重建可分配拓扑。',fontsize=10)
    fig.tight_layout(rect=(0,.075,1,1))
    fig.savefig(out/'longgang_roads_water_candidates.png', dpi=180)
    fig.savefig(out/'longgang_roads_water_candidates.svg')
    plt.close(fig)
    report = {'run_id': name, 'region': cfg['region'], 'scope': cfg['region_label'], 'adcode':cfg['scope_adcode'],
        'include_dapeng': include_dapeng, 'authorization': cfg['scope_authorization'],
        'scope_selection_method':scope_method,
        'scope_is_derived_from_supplier_not_independent_official_boundary':True,
        'source_boundary_sha256':digest(extracted/'深圳市行政区边界.json'),
        'selected_boundary_bounds':list(geom.bounds),
        'excluded_boundary_bounds':list(removed_geom.bounds) if removed_geom is not None else None,
        'selected_roads_intersect_excluded_component':int(selection.intersects(removed_geom).sum()) if removed_geom is not None else 0,
        'selected_stations_in_excluded_component':int(selected_stations.intersects(removed_geom).sum()) if removed_geom is not None else 0,
        'removed_source_road_features':int((roads.intersects(source_geom) & ~roads.intersects(geom)).sum()),
        'removed_station_ids':stations.loc[stations.geometry.covered_by(source_geom) & ~stations.geometry.covered_by(geom),'CZBM'].tolist(),
        'source_files': [{k:e[k] for k in ['name','bytes','sha256','copy_verified']} for e in original],
        'archives':archives, 'sqlite_quick_check': integrity, 'actual_layers': layers,
        'source_geojson_matches_motor_layer':True, 'supplied_boundary_features':len(boundary),
        'boundary_has_explicit_crs': bool(boundary_json.get('crs')), 'boundary_datum_independently_verified':False,
        'road_features_selected':len(selection), 'selected_features_are_directed_graph_edges':False,
        'whole_selected_feature_length_m':float(selection.length_m.sum()),
        'road_osm_ids_unique': bool(selection.osm_id.is_unique),
        'road_geometries_valid':bool(selection.geometry.is_valid.all()),
        'missing_lanes':int(selection.lanes.isna().sum()), 'missing_maxspeed':int(selection.maxspeed.isna().sum()),
        'oneway_counts':selection.oneway.fillna('<missing>').value_counts().to_dict(),
        'station_candidates':len(selected_stations), 'water_record_candidates':len(levels),
        'label_consistent_stations':int((~selected_stations.district_label_conflict).sum()),
        'label_consistent_water_records':len(label_only),
        'label_conflict_station_ids': selected_stations.loc[selected_stations.district_label_conflict, 'CZBM'].tolist(),
        'candidate_SW_peak_m':float(levels.water_level_raw.max()),
        'station_to_road_median_m':float(candidates.groupby('CZBM').candidate_distance_m.min().median()),
        'station_to_road_max_m':float(candidates.candidate_distance_m.max()),
        'raw_SW_reference_verified':False, 'station_road_association_verified':False,
        'new_measured_rainfall':False,'new_measured_OD':False,'new_measured_traffic_flow':False,
        'raster_extent_checks':rasters, 'traffic_assignment_rerun':False,
        'discrepancies':['Dictionary lists motor_all_bbox, but delivered GPKG contains only two layers',
            'Claimed BBBike original archive and gpkg/ provenance directory are absent from all five files',
            'Boundary JSON has no explicit CRS/source; WGS84 is a supplier claim, independently unverified',
            'Road features have no authoritative u/v/node IDs; endpoint-only joining cannot certify topology',
            'Dictionary overlay proximity is not evidence of sensor location or SW road-relative datum'],
        'next_steps':['Rebuild directional topology with shared junctions and grade separation; validate oneway=-1, access and busway',
            'Audit supplied boundary datum against an independent source',
            'Review station label conflict and surveyed road/sensor association',
            'Clip DSM/population, acquire Longgang facilities, create new TAZ/gateways and synthetic or calibrated OD',
            'Generate new inundation and rerun assignment/resilience/SUMO; retain Nanshan historical results']}
    write(out/'intake_report.json', report)
    import shutil
    shutil.copy2(config, out/'config.yaml');shutil.copy2(__file__, out/'intake_longgang_data.py')
    inputs = [config, Path(__file__).resolve(), source/'source_manifest.json',
        *[source/e['name'] for e in original], ROOT/cfg['station_source'], ROOT/cfg['water_source']]
    manifest = {'run_id':name,'status':'intake_complete_graph_and_models_pending',
        'inputs':[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p),'bytes':p.stat().st_size} for p in inputs],
        'outputs':[{'path':p.relative_to(out).as_posix(),'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(out.iterdir())]}
    write(out/'manifest.json',manifest)
    checks = {'five_sources_hash_match':len(original)==5, 'zip_crc':all(a['crc_passed'] for a in archives),
        'gpkg_integrity':integrity=='ok', 'duplicate_road_formats_match':True,
        'nonempty_valid_selection':len(selection)>0 and bool(selection.geometry.is_valid.all()),
        'station_record_subset':set(levels.CZBM)==set(selected_stations.CZBM),
        'manifest_output_hashes':all(digest(out/e['path'])==e['sha256'] for e in manifest['outputs'])}
    if not include_dapeng:
        checks.update({'no_roads_intersect_dapeng':report['selected_roads_intersect_excluded_component']==0,
            'no_stations_in_dapeng':report['selected_stations_in_excluded_component']==0,
            'source_reconstructed_from_selected_and_excluded':geom.union(removed_geom).equals(source_geom)})
    assert all(checks.values()), checks
    write(out/'intake_checks.json',{'checks':checks,'all_checks_passed':True,
        'scope':'Data-copy, format and selection consistency only; not topology, datum, field or model validation'})
    print(json.dumps({'directory':out.relative_to(ROOT).as_posix(),'road_features':len(selection),
        'stations':len(selected_stations),'water_records':len(levels),'checks':checks},ensure_ascii=False))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,default=ROOT/'configs/longgang_data_intake.yaml')
    run(p.parse_args().config.resolve())
