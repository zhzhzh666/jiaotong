"""Synthetic OSM fixtures test direction/parallel edges, never masquerade as Shenzhen input."""
from pathlib import Path
import json
import xml.etree.ElementTree as E
import geopandas as gpd
import networkx as nx
import osmnx as ox
import pytest
from shapely.geometry import box

from uftr.archive import file_hash,write_json
from uftr.config import load_config,validate_config
from uftr.network import parse_positive_tag,normalize_roads,network_statistics,shortest_route,export_network
from uftr.osm_download import graph_from_tiles,drive_way

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def osm_fixture(tmp_path):
    osm=E.Element('osm',version='0.6')
    points={1:(113.93,22.53),2:(113.932,22.53),3:(113.931,22.5303),4:(113.934,22.53),5:(113.94,22.54),6:(113.941,22.54)}
    for n,(lon,lat) in points.items(): E.SubElement(osm,'node',id=str(n),lon=str(lon),lat=str(lat),version='1')
    ways=[(101,[1,2],{'highway':'primary','lanes':'4','maxspeed':'50'}),(102,[1,3,2],{'highway':'primary','oneway':'yes','lanes':'2','maxspeed':'60'}),(103,[2,4],{'highway':'secondary','oneway':'-1','lanes':'1','maxspeed:backward':'20 mph'}),(104,[5,6],{'highway':'residential'}),(105,[1,4],{'highway':'footway'})]
    for ident,refs,tags in ways:
        w=E.SubElement(osm,'way',id=str(ident),version='1')
        for ref in refs: E.SubElement(w,'nd',ref=str(ref))
        for k,v in tags.items(): E.SubElement(w,'tag',k=k,v=v)
    path=tmp_path/'tile.osm'; E.ElementTree(osm).write(path,encoding='utf-8')
    write_json(tmp_path/'download_manifest.json',{'tiles':[{'path':'tile.osm','sha256':file_hash(path)}]})
    return tmp_path

def make_graph(path):
    g=graph_from_tiles(path,box(113.92,22.52,113.95,22.55))
    return normalize_roads(g,load_config(ROOT/'configs/phase01.yaml')['network']['attributes'])

def test_real_osm_semantics_parallel_reverse_and_disconnected_retained(osm_fixture):
    g=make_graph(osm_fixture)
    assert len(g[1][2])==2
    assert g.has_edge(4,2) and not g.has_edge(2,4)
    assert not any(d['osmid']==105 for _,_,d in g.edges(data=True))
    assert nx.number_weakly_connected_components(g)==2
    reverse=next(d for _,_,d in g.edges(data=True) if d['osmid']==103)
    assert reverse['speed_limit_kph']==pytest.approx(32.18688)
    assert reverse['oneway_osm_raw']=='-1'
    two=next(d for _,_,d in g.edges(data=True) if d['osmid']==101)
    assert two['lanes_per_direction']==2 and two['lanes_source']=='estimated_bidirectional_split'
    with pytest.raises(nx.NetworkXNoPath): shortest_route(g,1,5)
    path=shortest_route(g,1,2)
    assert path['travel_time_s']==min(d['free_flow_time_s'] for d in g[1][2].values())
    assert len(path['edge_ids'])==1

def test_stable_ids_metric_length_and_graphml_geojson_roundtrip(osm_fixture):
    g=make_graph(osm_fixture); again=make_graph(osm_fixture)
    assert {d['edge_id'] for _,_,d in g.edges(data=True)}=={d['edge_id'] for _,_,d in again.edges(data=True)}
    assert all(80<d['length_m']<500 for _,_,d in g.edges(data=True))
    assert all(d['capacity_source'].startswith('estimated') for _,_,d in g.edges(data=True))
    export_network(g,osm_fixture/'processed')
    reloaded=ox.load_graphml(osm_fixture/'processed/road_network.graphml',edge_dtypes={'free_flow_time_s':float,'length_m':float,'capacity_veh_h':float,'free_flow_speed_kph':float,'lanes_per_direction':int,'speed_limit_kph':float})
    assert shortest_route(reloaded,1,2)==shortest_route(g,1,2)
    edges=gpd.read_file(osm_fixture/'processed/road_edges.geojson')
    assert len(edges)==g.number_of_edges() and edges.crs.to_epsg()==4326
    assert edges.edge_id.nunique()==len(edges)
    stats=network_statistics(reloaded,sample_origins=len(g))
    assert stats['weak_components']==2 and stats['parallel_directed_pairs']==1

@pytest.mark.parametrize('tag,expected',[('50',50),('20 mph',32.18688),('30;50',30),('signals',None),('50 @ wet',None),('0',None),('nan',None),('-30',None)])
def test_speed_tag_units_and_unsupported_values(tag,expected):
    value=parse_positive_tag(tag,speed=True)
    assert value==pytest.approx(expected) if expected is not None else value is None

def test_source_tamper_rejected(osm_fixture):
    (osm_fixture/'tile.osm').write_text('altered')
    with pytest.raises(ValueError,match='checksum'): graph_from_tiles(osm_fixture,box(113,22,114,23))

def test_offline_replay_preserves_existing_windows_xml_bytes(osm_fixture):
    first=make_graph(osm_fixture)
    path=osm_fixture/'drive_filtered.osm'
    path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    fingerprint=file_hash(path)
    second=make_graph(osm_fixture)
    assert file_hash(path)==fingerprint
    assert {d['edge_id'] for _,_,d in first.edges(data=True)}=={d['edge_id'] for _,_,d in second.edges(data=True)}

def test_isolated_roundabout_and_conditional_data_are_not_silently_lost(osm_fixture):
    path=osm_fixture/'tile.osm'; tree=E.parse(path); osm=tree.getroot()
    for n,lon,lat in [(7,113.942,22.542),(8,113.943,22.542),(9,113.9425,22.543)]:
        E.SubElement(osm,'node',id=str(n),lon=str(lon),lat=str(lat),version='1')
    w=E.SubElement(osm,'way',id='106',version='1')
    for n in [7,8,9,7]: E.SubElement(w,'nd',ref=str(n))
    E.SubElement(w,'tag',k='highway',v='residential'); E.SubElement(w,'tag',k='junction',v='roundabout')
    tree.write(path,encoding='utf-8')
    write_json(osm_fixture/'download_manifest.json',{'tiles':[{'path':'tile.osm','sha256':file_hash(path)}]})
    g=make_graph(osm_fixture)
    assert nx.number_weakly_connected_components(g)==3
    assert any(d['osmid']==106 for _,_,d in g.edges(data=True))
    assert all(d['oneway'] for _,_,d in g.edges(data=True) if d['osmid']==106)

@pytest.mark.parametrize('tags',[{'highway':'footway'},{'highway':'primary','access':'private'},{'highway':'primary','motor_vehicle':'no'},{'highway':'residential','area':'yes'},{'highway':'service'}])
def test_drive_filter(tags): assert not drive_way(tags)

def test_network_config_rejects_degree_order_and_unsafe_parameters():
    cfg=load_config(ROOT/'configs/phase01.yaml')
    cfg['network']['small_bbox']=[22.5,113.9,22.6,114]
    with pytest.raises(ValueError,match='bbox'):validate_config(cfg)
    cfg=load_config(ROOT/'configs/phase01.yaml'); cfg['network']['attributes']['defaults']['fallback']['capacity_per_lane_veh_h']=0
    with pytest.raises(ValueError,match='capacity'):validate_config(cfg)
