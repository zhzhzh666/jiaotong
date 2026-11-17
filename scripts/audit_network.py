"""Independent saved-output checks against original OSM ways and export tables."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as E
import math

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd
from pyproj import Transformer
from shapely.ops import transform

from uftr.archive import file_hash,write_json
from uftr.network import shortest_route

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--run-id',required=True); parser.add_argument('--compare-run'); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); root=Path.cwd()
    report=json.loads((root/'results/runs'/args.run_id/'raw/network_report.json').read_text(encoding='utf-8'))
    source=root/report['source_snapshot']; processed=root/report['processed_root']
    project=Transformer.from_crs(4326,32650,always_xy=True).transform
    result={'run_id':args.run_id,'status':'passed','regions':{}}
    for name in ['small','nanshan']:
        directory=processed/name
        g=ox.load_graphml(directory/'road_network.graphml',edge_dtypes={'length_m':float,'free_flow_time_s':float,'capacity_veh_h':float,'free_flow_speed_kph':float,'lanes_per_direction':int,'speed_limit_kph':float})
        ways={int(w.attrib['id']):w for w in E.parse(source/name/'drive_filtered.osm').getroot().findall('way')}
        oneway_checked=0; bidirectional_checked=0
        for u,v,k,d in g.edges(data=True,keys=True):
            way=ways[int(d['osmid'])]; refs=[int(n.attrib['ref']) for n in way.findall('nd')]
            assert u in refs and v in refs
            assert math.dist(d['geometry'].coords[0],(g.nodes[u]['x'],g.nodes[u]['y']))<1e-7
            assert math.dist(d['geometry'].coords[-1],(g.nodes[v]['x'],g.nodes[v]['y']))<1e-7
            assert math.isclose(transform(project,d['geometry']).length,d['length_m'],rel_tol=1e-9)
            assert math.isclose(d['length_m']/(d['free_flow_speed_kph']/3.6),d['free_flow_time_s'],rel_tol=1e-10)
            if d['oneway'] and u!=v and refs[0]!=refs[-1] and refs.count(u)==refs.count(v)==1:
                raw={t.attrib['k']:t.attrib['v'] for t in way.findall('tag')}.get('oneway','missing')
                assert (refs.index(u)>refs.index(v))==(raw in {'-1','reverse','T'}),f'oneway direction mismatch {u} {v}'
                oneway_checked+=1
            elif not d['oneway']:
                assert any(r['osmid']==d['osmid'] for r in g[v].get(u,{}).values()),f'missing reverse road {u} {v}'
                bidirectional_checked+=1
        csv=pd.read_csv(directory/'road_attributes.csv'); edges=gpd.read_file(directory/'road_edges.geojson'); nodes=gpd.read_file(directory/'road_nodes.geojson')
        assert len(nodes)==len(g) and nodes.crs.to_epsg()==4326
        assert len(csv)==len(edges)==g.number_of_edges() and edges.crs.to_epsg()==4326
        ids={d['edge_id'] for _,_,d in g.edges(data=True)}
        assert set(csv.edge_id)==set(edges.edge_id)==ids
        assert csv.edge_id.is_unique and edges.edge_id.is_unique
        for field in ['length_m','lanes_per_direction','speed_limit_kph','free_flow_speed_kph','free_flow_time_s','capacity_veh_h']:
            byid=csv.set_index('edge_id')[field]
            assert all(math.isclose(byid[d['edge_id']],d[field],rel_tol=1e-10) for _,_,d in g.edges(data=True))
        # Deterministic start/target samples include both intra-component and cross-component cases.
        sample=report[name]['sample_route']; assert shortest_route(g,sample['nodes'][0],sample['nodes'][-1])==sample
        if args.compare_run:
            prior=json.loads((root/'results/runs'/args.compare_run/'raw/network_report.json').read_text(encoding='utf-8'))
            previous=pd.read_csv(root/prior['processed_root']/name/'road_attributes.csv')
            left=csv.set_index('edge_id').sort_index(); right=previous.set_index('edge_id').sort_index()
            if name=='nanshan' and report[name].get('scope_adjustment') and len(right)>len(left):
                excluded={r['edge_id'] for r in report[name]['scope_adjustment']['excluded_edges']}
                assert set(right.index)-set(left.index)==excluded
                right=right.loc[left.index]
            pd.testing.assert_frame_equal(left,right,check_dtype=False)
        result['regions'][name]={'nodes':len(g),'directed_edges':len(csv),'oneway_original_order_checked':oneway_checked,'two_way_reverse_edges_checked':bidirectional_checked,'geometry_endpoints_and_metric_lengths_checked':len(csv),'csv_geojson_graphml_agree':True,'same_edge_attributes_as_compare_run':bool(args.compare_run)}
    inventory=json.loads((processed/'output_inventory.json').read_text(encoding='utf-8'))
    assert all(file_hash(processed/f['path'])==f['sha256'] for f in inventory['files'])
    result['outputs_verified']=len(inventory['files'])
    write_json(args.output,result); print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
