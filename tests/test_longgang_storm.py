from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString,box
import yaml
from uftr.longgang_storm import rain_profile,rain_factors,make_road_sites,aggregate_road_depth,graph_road_identities

ROOT=Path(__file__).parents[1]
CFG=yaml.safe_load((ROOT/'configs/longgang_storm.yaml').read_text(encoding='utf-8'))
NET=yaml.safe_load((ROOT/'configs/longgang_od.yaml').read_text(encoding='utf-8'))['network']


def test_rain_totals_support_and_units():
    rain=rain_profile(24,.25,CFG['rainfall'])
    for name,total in CFG['rainfall']['total_mm'].items():
        frame=rain[rain.scenario.eq(name)]
        assert len(frame)==96 and frame.rain_mm_interval.sum()==pytest.approx(total)
        assert (frame.loc[(frame.start_h<5)|(frame.start_h>=13),'rain_mm_interval']==0).all()
        assert np.allclose(frame.intensity_mm_h*.25,frame.rain_mm_interval)
    wrong={**CFG['rainfall'],'event_start_hour':5.1}
    with pytest.raises(ValueError):rain_profile(24,.25,wrong)


def test_spatial_rain_reproducible_and_collocated():
    xy=np.array([[0,0],[0,0],[2000,1000],[10000,10000]])
    f=rain_factors(xy,CFG['rainfall'],42)
    assert (f>0).all() and f.mean()==pytest.approx(1)
    assert f[0]==f[1]
    assert np.array_equal(f,rain_factors(xy,CFG['rainfall'],42))
    assert not np.array_equal(f,rain_factors(xy,CFG['rainfall'],43))


def test_road_proxy_max_and_unknown_kept_nan():
    site=pd.DataFrame({'site_id':['a','b']});features=pd.DataFrame({'source_feature_position':[10,20,30]})
    links=pd.DataFrame({'source_feature_position':[10,10,20],'site_id':['a','b','a']})
    depth=np.array([[0,0],[.1,.3],[.2,.1]])
    result=aggregate_road_depth(depth,site,features,links)
    assert np.allclose(result[:,:2],[[0,0],[.3,.1],[.2,.2]])
    assert np.isnan(result[:,2]).all()


def test_ground_vs_bridge_and_missing_dsm(tmp_path):
    raster=tmp_path/'dsm.tif'
    with rasterio.open(raster,'w',driver='GTiff',width=20,height=20,count=1,dtype='float32',crs=4326,
                       transform=from_origin(114,22.002,.0001,.0001),nodata=-9999) as dst:
        array=np.ones((20,20),dtype='float32')*10;array[:,15:]=-9999;dst.write(array,1)
    roads=gpd.GeoDataFrame([
        {'osm_id':'a','highway':'primary','geometry':LineString([(114.0001,22.001),(114.0008,22.001)])},
        {'osm_id':'b','highway':'primary','bridge':'yes','geometry':LineString([(114.0001,22.0005),(114.0008,22.0005)])},
        {'osm_id':'c','highway':'primary','geometry':LineString([(114.0016,22.001),(114.0019,22.001)])}],crs=4326)
    sites,features,links,samples=make_road_sites(roads,box(114,22,114.002,22.002),raster,CFG['spatial'],NET)
    status=features.set_index('osm_id').status
    assert status.a=='modelled_ground_samples'
    assert status.b=='elevated_tunnel_or_nonzero_layer_not_modelled'
    assert status.c=='missing_dsm_not_modelled'
    assert len(sites)>0 and links.source_feature_position.eq(0).all()
    assert (samples.loc[samples.source_feature_position.eq(2),'valid_dsm']==False).all()


def test_exact_graph_identity_and_spatial_filter(tmp_path):
    source=tmp_path/'g.graphml'
    source.write_text('''<graphml><key id="a" attr.name="source_feature_position"/>
    <key id="b" attr.name="segment_index"/><key id="c" attr.name="edge_id"/><key id="d" attr.name="length_m"/>
    <graph><edge source="7" target="8" id="2"><data key="a">0</data><data key="b">1</data>
    <data key="c">arbitrary_exact_ID</data><data key="d">23</data></edge>
    <edge source="6" target="7" id="0"><data key="a">0</data><data key="b">0</data>
    <data key="c">outside_ID</data><data key="d">12</data></edge></graph></graphml>''',encoding='utf-8')
    roads=gpd.GeoDataFrame(geometry=[LineString([(0,0),(1,0),(2,0)])],crs=4326)
    frame=graph_road_identities(source,roads,box(1.5,-1,3,1),[0])
    assert frame.edge_id.tolist()==['arbitrary_exact_ID']
    assert frame[['u','v','key']].iloc[0].tolist()==[7,8,2]
    assert frame.crosses_study_boundary.all()
