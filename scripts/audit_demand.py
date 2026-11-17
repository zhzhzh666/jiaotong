"""Independent audit of written Phase 03 outputs and an optional replay."""
import argparse
import json
from pathlib import Path
import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd
import numpy as np
import rasterio
from shapely.geometry import Point
from shapely.ops import unary_union
from uftr.archive import file_hash, write_json

p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);p.add_argument('--compare-run');p.add_argument('--output',default='docs/validation/phase03/demand_audit.json');args=p.parse_args()
root=Path.cwd().resolve()
def report(run):return json.loads((root/'results/runs'/run/'raw/demand_report.json').read_text(encoding='utf-8'))
r=report(args.run_id);out=root/r['processed_root'];syn=root/r['synthetic_root']
config=json.loads((root/'results/runs'/args.run_id/'config.json').read_text(encoding='utf-8'));s=config['demand']
z=gpd.read_file(out/'traffic_zones.geojson').to_crs(32650);v=pd.read_csv(out/'zone_population.csv');a=pd.read_csv(out/'population_allocation.csv')
connect=pd.read_csv(out/'zone_connectors.csv',dtype={'node_id':'Int64'})
boundary=gpd.read_file(root/s['network_directory']/'study_boundary.geojson').to_crs(32650).geometry.iloc[0]
union=unary_union(z.geometry)
assert union.symmetric_difference(boundary).area<1e-3
assert abs(z.area.sum()-union.area)<1e-3
assert (a.allocated_people>=0).all()
assert np.allclose(a.groupby('cell_id').weight.sum(),1,rtol=1e-12,atol=1e-12)
assert np.allclose(a.groupby('cell_id').allocated_people.sum(),a.groupby('cell_id').native_cell_people.first(),rtol=1e-12)
with rasterio.open(root/s['spatial_directory']/'population_2020_native_1km.tif') as f:total=float(f.read(1,masked=True).astype('float64').sum())
assert np.isclose(v.population_estimate.sum(),total,rtol=1e-12)
assert set(v.loc[(v.production_share>0)|(v.attraction_share>0),'zone_id'])==set(connect.loc[connect.zone_kind.eq('internal'),'zone_id'])
graph=ox.load_graphml(root/s['network_directory']/'road_network.graphml',edge_dtypes={'free_flow_time_s':float})
nodes=gpd.read_file(root/s['network_directory']/'road_nodes.geojson').to_crs(32650).set_index('node_id')
indexed=z.set_index('zone_id')
for row in connect.itertuples():
    if not row.connected:assert pd.isna(row.node_id);continue
    assert int(row.node_id) in graph
    if row.zone_kind=='internal':
        zone=indexed.loc[row.zone_id];point=nodes.loc[int(row.node_id)].geometry
        assert zone.geometry.buffer(1e-6).covers(point)
        assert np.isclose(Point(zone.centre_x_m,zone.centre_y_m).distance(point),row.connector_distance_m,atol=1e-5)
        assert row.connector_distance_m<=s['max_connector_distance_m']
gate=gpd.read_file(out/'boundary_gateways.geojson')
for g in gate.itertuples():
    n=int(g.node_id);assert not boundary.covers(nodes.loc[n].geometry)
    assert any(boundary.covers(nodes.loc[int(x)].geometry) for x in set(graph.predecessors(n))|set(graph.successors(n)))
od=pd.read_csv(syn/'od_all_periods.csv',dtype={'origin_node':'Int64','destination_node':'Int64'})
targets=pd.read_csv(out/'zone_targets.csv');trace=pd.read_csv(out/'ipf_trace.csv')
assert (od.flow_veh_h>0).all() and np.isfinite(od.flow_veh_h).all() and not od.observed_od.any()
assert not od.duplicated(['period','origin_zone','destination_zone']).any()
errors=[]
for period,spec in s['periods'].items():
    q=od[od.period.eq(period)];expected=total*s['person_trip_rate_per_hour']*s['motorized_person_trip_share']/s['vehicle_occupancy']*spec['factor']
    for block,factor in [('internal',1),('inbound',s['boundary_inbound_fraction']),('outbound',s['boundary_outbound_fraction'])]:
        assert np.isclose(q.loc[q.block.eq(block),'flow_veh_h'].sum(),expected*factor,rtol=1e-10)
    t=targets[targets.period.eq(period)].set_index('zone_id')
    for key,target in [('origin_zone','production_veh_h'),('destination_zone','attraction_veh_h')]:
        sums=q.groupby(key).flow_veh_h.sum().reindex(t.index,fill_value=0)
        assert np.allclose(sums,t[target],rtol=2e-9,atol=1e-7)
        errors.append(float((sums-t[target]).abs().max()))
    assert q.loc[q.route_status.eq('unreachable_normal_network'),'flow_veh_h'].sum()>0
assert (trace.groupby(['period','block']).tail(1).relative_margin_error<=s['ipf_tolerance']).all()
assert not ((od.origin_zone.str.startswith('EXT'))&(od.destination_zone.str.startswith('EXT'))).any()
assert od.loc[od.route_status.ne('routable'),'free_flow_with_access_s'].isna().all()
sample=od[od.period.eq('offpeak')].groupby('route_status',group_keys=False).head(25)
look=connect.set_index('zone_id');checked=0
for q in sample.itertuples():
    if q.route_status=='intrazonal_not_graph_loaded':assert q.origin_zone==q.destination_zone;continue
    if pd.isna(q.origin_node) or pd.isna(q.destination_node):assert q.route_status=='unreachable_normal_network';continue
    try:cost=nx.shortest_path_length(graph,int(q.origin_node),int(q.destination_node),weight='free_flow_time_s')
    except nx.NetworkXNoPath:assert q.route_status=='unreachable_normal_network';continue
    access=(look.loc[q.origin_zone,'connector_distance_m']+look.loc[q.destination_zone,'connector_distance_m'])/(s['access_speed_kph']/3.6)
    assert q.route_status=='routable' and np.isclose(q.free_flow_with_access_s,cost+access,rtol=1e-10)
    checked+=1
water=json.loads((out/'user_water/user_water_quality.json').read_text(encoding='utf-8'))
raw=pd.read_csv(out/'user_water/user_water_levels_all.csv');assert not raw.usable_as_road_depth.any()
assert water['stations']==45 and water['water_level_records']==18123 and water['stations_within_study']==6
assert water['risk_labels_match_confirmed_thresholds'] and water['summary_peak_max_difference']==0
inv=json.loads((root/r['user_source_snapshot']/'source_inventory.json').read_text(encoding='utf-8'))
for item in inv['files']:
    assert file_hash(root/r['user_source_snapshot']/item['path'])==item['sha256']
    assert file_hash(root/item['path'])==item['sha256'],'root original changed'
comparison=None
if args.compare_run:
    previous=report(args.compare_run);previous_out=root/previous['processed_root'];previous_syn=root/previous['synthetic_root']
    names=['traffic_zones.geojson','zone_population.csv','population_allocation.csv','zone_connectors.csv','network_skims.csv','zone_targets.csv','ipf_trace.csv','boundary_gateways.geojson','user_water/user_water_levels_all.csv','user_water/user_stations_all.geojson']
    for name in names:assert file_hash(out/name)==file_hash(previous_out/name),name
    assert file_hash(syn/'od_all_periods.csv')==file_hash(previous_syn/'od_all_periods.csv')
    comparison={'previous_run':args.compare_run,'data_outputs_identical':True,'outputs_compared':len(names)+1}
result={'status':'passed','run_id':args.run_id,'zones':len(z),'native_people':total,'max_margin_error_veh_h':max(errors),'shortest_path_samples_verified':checked,'all_positive_demand_zones_retained':True,'raw_user_files_unchanged':True,'water_depth_quarantined':True,'compare':comparison}
write_json(root/args.output,result);print(json.dumps(result,ensure_ascii=False,indent=2))
