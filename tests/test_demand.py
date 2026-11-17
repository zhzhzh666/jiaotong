from pathlib import Path
import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, box
from uftr.demand import (ipf, make_zones, allocate_population, add_attraction,
    connect_zones, boundary_gateways, network_skims, build_od)
from uftr.config import load_config, validate_config
from uftr.user_water import seal_user_sources, risk_band

ROOT=Path(__file__).resolve().parents[1]

def test_user_risk_breakpoints_are_left_inclusive():
    assert risk_band([0,.1499,.15,.2999,.3,.3999,.4,1.95]).tolist()==['蓝Ⅳ','蓝Ⅳ','黄Ⅲ','黄Ⅲ','橙Ⅱ','橙Ⅱ','红Ⅰ','红Ⅰ']

def test_ipf_known_margins_and_zero_margins():
    q,trace=ipf([[1,2,0],[3,4,0],[4,5,1]],[10,20,0],[18,12,0])
    np.testing.assert_allclose(q.sum(1),[10,20,0],rtol=1e-9)
    np.testing.assert_allclose(q.sum(0),[18,12,0],rtol=1e-9)
    assert trace[-1]['relative_margin_error']<=1e-9
    assert (q[2]==0).all() and (q[:,2]==0).all()

def test_ipf_zero_total():
    q,t=ipf([[1,2],[3,4]],[0,0],[0,0]);assert q.sum()==0 and t[-1]['iteration']==0

@pytest.mark.parametrize('seed,o,d',[
    ([[1]],[1],[2]),([[0]],[1],[1]),([[-1]],[1],[1]),([[np.nan]],[1],[1]),([[1,2]],[1],[1]),([[1]],[np.inf],[np.inf])])
def test_ipf_rejects_invalid_inputs(seed,o,d):
    with pytest.raises(ValueError):ipf(seed,o,d)

def test_ipf_incompatible_structural_support_does_not_fake_convergence():
    with pytest.raises(ValueError,match='converge'):ipf(np.eye(2),[1,2],[2,1],max_iterations=5)

def test_native_population_coastal_conservation(tmp_path):
    # Metric source to avoid any assumption about raster pixel dimensions.
    path=tmp_path/'p.tif'
    with rasterio.open(path,'w',driver='GTiff',width=2,height=1,count=1,dtype='float64',crs=32650,transform=from_origin(0,1000,1000,1000),nodata=-9999) as f:f.write(np.array([[100.,200.]]),1)
    zones=gpd.GeoDataFrame({'zone_id':['a','b'],'area_m2':[500000,1000000]},geometry=[box(0,0,500,1000),box(500,0,1500,1000)],crs=32650)
    p,a,q=allocate_population(zones,path)
    assert p.population_estimate.sum()==pytest.approx(300)
    assert a.groupby('cell_id').weight.sum().to_list()==pytest.approx([1,1])
    assert p.population_estimate.to_list()==pytest.approx([50,250])

def test_no_node_fallback_outside_zone():
    zones=gpd.GeoDataFrame({'zone_id':['a'],'centre_x_m':[100.],'centre_y_m':[100.]},geometry=[box(0,0,200,200)],crs=32650)
    nodes=gpd.GeoDataFrame({'node_id':[1]},geometry=[Point(201,100)],crs=32650)
    graph=nx.MultiDiGraph();graph.add_node(1)
    out=connect_zones(zones,nodes,graph,1500)
    assert not out.connected.iloc[0] and pd.isna(out.node_id.iloc[0])

def test_skims_preserve_directed_disconnect_and_parallel_edges():
    g=nx.MultiDiGraph();g.add_edge(1,2,free_flow_time_s=10);g.add_edge(1,2,free_flow_time_s=5);g.add_node(3)
    c=pd.DataFrame({'zone_id':['a','b','c'],'zone_kind':['internal']*3,'node_id':[1,2,3],'connected':[True]*3,'connector_distance_m':[0.]*3})
    t=network_skims(c,g,20,300)
    assert t[0,1]==5 and np.isnan(t[1,0]) and np.isnan(t[0,2]) and t[2,2]==300
    assert g.number_of_edges()==2

def test_boundary_gateways_require_actual_crossing_arcs():
    nodes=gpd.GeoDataFrame({'node_id':[1,2,3]},geometry=[Point(113.9,22.5),Point(113.89,22.5),Point(113.8,22.5)],crs=4326)
    g=nx.MultiDiGraph();g.add_edge(1,2);g.add_node(3)
    gates=boundary_gateways(g,nodes,box(113.895,22.49,113.91,22.51),6)
    assert gates.node_id.tolist()==[2] and gates.incoming_crossing_arcs.iloc[0]==1 and gates.outgoing_crossing_arcs.iloc[0]==0

def test_three_period_od_margins_unreachable_intrazonal_and_boundary():
    settings=load_config(ROOT/'configs/phase03.yaml')['demand']
    c=pd.DataFrame({'zone_id':['a','b','e'],'zone_kind':['internal','internal','external_gateway'],'node_id':pd.Series([1,None,2],dtype='Int64')})
    z=pd.DataFrame({'zone_id':['a','b'],'population_estimate':[100,200],'production_share':[1/3,2/3],'attraction_share':[.7,.3]})
    t=np.array([[300,np.nan,10],[np.nan,300,np.nan],[10,np.nan,0.]])
    od,targets,trace,summary=build_od(c,z,t,settings)
    for period,factor in [('offpeak',1),('morning_peak',2),('evening_peak',1.8)]:
        q=od[od.period.eq(period)];assert q.flow_veh_h.sum()==pytest.approx(300*.05*.5/1.25*factor*1.2)
        assert q[q.route_status.eq('unreachable_normal_network')].flow_veh_h.sum()>0
        assert q[q.route_status.eq('intrazonal_not_graph_loaded')].flow_veh_h.sum()>0
        assert not ((q.origin_zone=='e')&(q.destination_zone=='e')).any()
    assert (targets.actual_production_veh_h-targets.production_veh_h).abs().max()<1e-8
    assert (od.flow_veh_h>=0).all() and not od.observed_od.any()

@pytest.mark.parametrize('field,value',[('zone_size_m',0),('gravity_beta_per_s',float('nan')),('boundary_gateways',0),('motorized_person_trip_share',1.2),('network_directory','../escape')])
def test_phase03_config_rejects_bad_settings(field,value):
    c=load_config(ROOT/'configs/phase03.yaml');c['demand'][field]=value
    with pytest.raises(ValueError):validate_config(c)

def test_user_snapshot_preserves_bytes_and_attested_provenance(tmp_path):
    name='raw.csv';(tmp_path/name).write_bytes(b'raw\n123\n')
    snapshot=seal_user_sources(tmp_path,[name],tmp_path/'snapshot')
    assert (snapshot/name).read_bytes()==(tmp_path/name).read_bytes()
    import json
    inv=json.loads((snapshot/'source_inventory.json').read_text(encoding='utf-8'))
    assert inv['source_platform'].startswith('深圳') and inv['source_url'] is None
