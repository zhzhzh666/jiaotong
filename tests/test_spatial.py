from pathlib import Path
import json
import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, LineString, box
from uftr.archive import file_hash, write_json
from uftr.config import load_config, validate_config
from uftr.spatial import (clip_rasters, normalize_points, match_surface_roads, read_gsod,
                          read_osm_facilities, synthetic_risk_points, surface_reason)
from uftr.spatial_sources import seal_snapshot, verify_snapshot

SETTINGS={'search_radius_m':100,'max_match_distance_m':60,'high_distance_m':15,
          'medium_distance_m':40,'high_gap_m':15,'medium_gap_m':5}


def points(xys):
    return gpd.GeoDataFrame({'point_id':[f'p{i}' for i in range(len(xys))],
                            'source_kind':['synthetic']*len(xys)},geometry=[Point(xy) for xy in xys],crs=32650)


def roads():
    a=LineString([(183000,2495000),(183200,2495000)])
    return gpd.GeoDataFrame({'edge_id':['bridge','ground_fwd','ground_rev','ramp'],
                            'bridge':['yes','','',''],'tunnel':['','','',''],
                            'layer':[1,0,0,0],'road_class':['primary','primary','primary','primary_link']},
        geometry=[LineString([(183000,2494998),(183200,2494998)]),a,LineString(list(a.coords)[::-1]),
                  LineString([(183000,2495050),(183200,2495050)])],crs=32650)


def test_surface_match_excludes_closer_bridge_and_keeps_both_directions():
    result=match_surface_roads(points([(183100,2494998)]),roads(),SETTINGS)
    selected=result[result.selected_geometry]
    assert set(selected.edge_id)=={'ground_fwd','ground_rev'}
    assert set(selected.match_confidence)=={'high'}
    assert selected.distance_m.tolist()==[2,2]
    assert result[result.edge_id.eq('bridge')].exclusion_reason.str.contains('bridge').all()
    assert result.flood_observation.eq('not established').all()


def test_ambiguous_ground_roads_not_assigned_high_confidence():
    e=roads(); e.loc[e.edge_id.eq('bridge'),'bridge']='';e.loc[e.edge_id.eq('bridge'),'layer']=0
    result=match_surface_roads(points([(183100,2494999)]),e,SETTINGS)
    assert result[result.selected_geometry].match_confidence.eq('low').all()


def test_far_point_preserved_as_unmatched():
    result=match_surface_roads(points([(184000,2496000)]),roads(),SETTINGS)
    assert len(result)==1 and result.match_confidence.iloc[0]=='unmatched'
    assert pd.isna(result.edge_id.iloc[0]) and not result.selected_geometry.any()


@pytest.mark.parametrize('row',[{'bridge':'viaduct'},{'tunnel':'yes'},{'layer':-1},{'layer':'[0,1]'}])
def test_vertical_surface_exclusions(row): assert surface_reason(row)


def test_native_population_counts_and_nodata_not_interpolated(tmp_path):
    path=tmp_path/'population.tif'
    with rasterio.open(path,'w',driver='GTiff',height=2,width=2,count=1,dtype='float32',
                       crs=4326,transform=from_origin(113,23,1,1),nodata=-9999) as dst:
        dst.write(np.array([[[10,20],[30,-9999]]],dtype='float32'))
    stats=clip_rasters([path],box(113,21,114,23),tmp_path/'clipped.tif')
    assert stats['sum_native_cells']==40 and stats['valid_cells']==2
    with rasterio.open(tmp_path/'clipped.tif') as src:assert src.res==(1,1)
    # Non-grid-aligned boundary must not shift/resample count pixels.
    clip_rasters([path],box(113.1,21.1,114.9,22.9),tmp_path/'offset_boundary.tif')
    with rasterio.open(tmp_path/'offset_boundary.tif') as src:
        assert src.transform.c==113 and src.transform.f==23
        assert src.read(1,masked=True).sum()==60


def test_station_rain_inch_conversion_missing_and_incomplete_flags(tmp_path):
    path=tmp_path/'rain.csv'
    pd.DataFrame({'STATION':['123']*4,'DATE':['2023-09-07','2023-09-08','2023-09-09','2023-09-10'],
                  'PRCP':[1,99.99,0,0],'PRCP_ATTRIBUTES':['G','G','I','G'],
                  'LATITUDE':[22]*4,'LONGITUDE':[114]*4}).to_csv(path,index=False)
    rain=read_gsod(path,'123')
    assert rain.precipitation_mm.iloc[0]==25.4
    assert rain.precipitation_mm.iloc[1:3].isna().all()
    assert rain.precipitation_mm.iloc[3]==0
    assert not rain.is_nanshan_areal_mean.any()
    with pytest.raises(ValueError,match='station'): read_gsod(path,'different')


def test_input_point_crs_bounds_clip_and_deduplication():
    p=gpd.GeoDataFrame({'point_id':['a','a','b']},geometry=[Point(114,22.5),Point(114,22.5),Point(116,22.5)],crs=4326)
    clean=normalize_points(p,box(113,22,115,23))
    assert len(clean)==1
    p=p.set_crs(None,allow_override=True)
    with pytest.raises(ValueError,match='CRS'):normalize_points(p,box(113,22,115,23))


def test_immutable_snapshot_checksum_and_contract(tmp_path):
    (tmp_path/'source.txt').write_text('actual bytes')
    seal_snapshot(tmp_path,{'example':1})
    verify_snapshot(tmp_path,{'example':1})
    with pytest.raises(FileExistsError):seal_snapshot(tmp_path,{})
    with pytest.raises(ValueError,match='contract'):verify_snapshot(tmp_path,{'different':1})
    (tmp_path/'source.txt').write_text('changed')
    with pytest.raises(ValueError,match='checksum'):verify_snapshot(tmp_path)


def test_facility_types_do_not_turn_bus_shelters_into_emergency_shelters(tmp_path):
    xml='''<osm><node id="1" lon="114" lat="22.5"><tag k="amenity" v="shelter"/><tag k="shelter_type" v="public_transport"/></node>
    <node id="2" lon="114.01" lat="22.5"><tag k="amenity" v="hospital"/></node>
    <node id="3" lon="114.02" lat="22.5"><tag k="emergency" v="assembly_point"/></node>
    <node id="4" lon="114.03" lat="22.5"><tag k="emergency" v="shelter"/></node></osm>'''
    p=tmp_path/'a.osm';p.write_text(xml)
    write_json(tmp_path/'download_manifest.json',{'tiles':[{'path':'a.osm','sha256':file_hash(p)}]})
    frame,quality=read_osm_facilities(tmp_path,box(113,22,115,23))
    assert set(frame.category)=={'hospital','assembly_point','emergency_shelter'}
    assert len(frame)==3 and not frame.entrance_verified.any()


def test_synthetic_points_reproducible_and_never_observed(tmp_path):
    dem=tmp_path/'dsm.tif'
    with rasterio.open(dem,'w',driver='GTiff',width=100,height=100,count=1,dtype='float32',
                       crs=4326,transform=from_origin(113.9,22.6,.001,.001),nodata=-9999) as dst:
        dst.write(np.full((1,100,100),10,dtype='float32'))
    e=gpd.GeoDataFrame({'bridge':['']*3,'layer':[0]*3,'tunnel':['']*3},geometry=[
        LineString([(113.94,22.54+i*.001),(113.95,22.54+i*.001)]) for i in range(3)],crs=4326)
    settings={'count':10,'clusters':2,'cluster_sd_m':40,'max_dsm_m':40,'elevation_scale_m':10}
    a=synthetic_risk_points(e,box(113.9,22.5,114,22.6),dem,settings,42)
    b=synthetic_risk_points(e,box(113.9,22.5,114,22.6),dem,settings,42)
    assert a.geometry.equals(b.geometry) and len(a)==10
    assert a.source_kind.eq('synthetic').all() and a.observed_depth_m.isna().all() and a.event_date.isna().all()


def test_spatial_config_distance_order_and_external_paths_rejected():
    root=Path(__file__).resolve().parents[1]
    cfg=load_config(root/'configs/phase02.yaml')
    cfg['spatial']['matching']['high_distance_m']=1000
    with pytest.raises(ValueError,match='ordering'):validate_config(cfg)
    cfg=load_config(root/'configs/phase02.yaml');cfg['spatial']['osm_snapshot']='../elsewhere'
    with pytest.raises(ValueError,match='inside project'):validate_config(cfg)


def test_historical_clean_source_uses_git_revision_but_dirty_source_is_not_accepted(tmp_path,monkeypatch):
    from hashlib import sha256
    from types import SimpleNamespace
    from uftr.archive import verify_recorded_input
    path=tmp_path/'source.py';path.write_bytes(b'new version')
    item={'path':str(path),'sha256':sha256(b'original version').hexdigest()}
    monkeypatch.setattr('uftr.archive.subprocess.run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=b'original version'))
    assert verify_recorded_input(tmp_path,item,{'commit':'a'*40,'dirty':False})=='git_blob_at_recorded_commit'
    with pytest.raises(ValueError,match='checksum'):
        verify_recorded_input(tmp_path,item,{'commit':'a'*40,'dirty':True})
