import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import rasterio
import yaml
from pathlib import Path
from shapely.geometry import LineString, box
from rasterio.transform import from_origin
from uftr.longgang_od import direction_and_speed, inferred_graph, population_allocation, fast_network_skims, schedule


CFG=yaml.safe_load((Path(__file__).parents[1]/'configs/longgang_od.yaml').read_text(encoding='utf-8'))


def test_access_direction_and_unit_conversion():
    row={'highway':'primary','oneway':'-1','maxspeed':'30 mph'}
    d,s,observed,_=direction_and_speed(row,CFG['network'])
    assert d==-1 and observed and abs(s-48.28032)<1e-8
    assert direction_and_speed({'highway':'primary','other_tags':'"access"=>"no"'},CFG['network']) is None
    assert direction_and_speed({'highway':'primary','other_tags':'"access"=>"no","motorcar"=>"yes"'},CFG['network']) is not None
    assert direction_and_speed({'highway':'primary','other_tags':'"junction"=>"roundabout"'},CFG['network'])[0]==1


def test_no_geometric_crossing_or_cross_grade_interior_join():
    # All lines have a geometric centre vertex, but bridge interior stays separate.
    roads=gpd.GeoDataFrame([
        {'osm_id':'1','highway':'primary','bridge':None,'layer':None,'oneway':'no','geometry':LineString([(114,22),(114.001,22),(114.002,22)])},
        {'osm_id':'2','highway':'primary','bridge':'yes','layer':'1','oneway':'no','geometry':LineString([(114.001,21.999),(114.001,22),(114.001,22.001)])},
        {'osm_id':'3','highway':'primary','bridge':None,'layer':None,'oneway':'no','geometry':LineString([(114.0005,21.999),(114.0005,22.001)])},
    ],crs=4326)
    graph,_,_,report=inferred_graph(roads,CFG['network'])
    assert report['weak_components']==3
    assert graph.number_of_edges()==10


def test_boundary_population_fraction_not_whole_cell(tmp_path):
    raster=tmp_path/'people.tif'
    with rasterio.open(raster,'w',driver='GTiff',height=1,width=1,count=1,dtype='float64',crs=4326,transform=from_origin(114,23,0.01,0.01),nodata=-99999) as dst:
        dst.write(np.array([[100.]]),1)
    # Half a source cell is inside the region; do not assign all 100 people.
    zones=gpd.GeoDataFrame({'zone_id':['a'],'geometry':[box(114,22.99,114.005,23)]},crs=4326).to_crs(32650)
    zones['area_m2']=zones.area
    values,allocation,report=population_allocation(zones,raster)
    assert abs(values.population_estimate.sum()-50)<0.01
    assert report['valid_area_fraction']>0.9999
    assert allocation.allocated_people.sum()<100


def test_scipy_skim_parallel_min_and_direction():
    graph=nx.MultiDiGraph()
    graph.add_nodes_from(range(3))
    graph.add_edge(0,1,free_flow_time_s=10)
    graph.add_edge(0,1,free_flow_time_s=3)
    graph.add_edge(1,2,free_flow_time_s=4)
    c=pd.DataFrame({'zone_id':['a','b','c'],'zone_kind':['internal']*3,'node_id':[0,1,2],'connected':[True]*3,'connector_distance_m':[0.]*3})
    t=fast_network_skims(c,graph,20,300)
    assert t[0,2]==7 and t[0,1]==3
    assert np.isnan(t[2,0]) and t[0,0]==300


def test_time_profile_rates_convert_to_interval_counts():
    m={p:np.array([[10.*s['factor']]]) for p,s in CFG['periods'].items()}
    frame=schedule(m,CFG['time'])
    assert len(frame)==96 and frame.iloc[-1].end_minute==1440
    assert frame.period.value_counts().to_dict()=={'offpeak':72,'morning_peak':12,'evening_peak':12}
    assert frame.iloc[28].expected_vehicle_trips==5
    assert abs(frame.expected_vehicle_trips.sum()-294)<1e-10
