"""OSM road attributes and directed multigraph validation (no traffic assignment)."""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import math
from pathlib import Path
import re

import geopandas as gpd
import networkx as nx
import osmnx as ox
from shapely.geometry import LineString, Point

from .archive import write_json


def parse_positive_tag(value, *, speed=False):
    """Conservative minimum of semicolon/list alternatives; reject conditional text."""
    values = value if isinstance(value, list) else [value]
    numbers = []
    for item in values:
        for token in str(item or '').split(';'):
            match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(mph|km/h|kph)?\s*', token)
            if not match:
                return None
            number = float(match[1])
            if match[2] == 'mph':
                if not speed:
                    return None
                number *= 1.609344
            if not math.isfinite(number) or number <= 0:
                return None
            if not speed and number != int(number):
                return None
            numbers.append(number)
    return min(numbers) if numbers else None


def normalize_roads(graph, parameters):
    """Preserve topology; all lengths measured on EPSG:32650 geometries."""
    g = graph.copy()
    if not isinstance(g, nx.MultiDiGraph) or not len(g.edges):
        raise ValueError('nonempty MultiDiGraph required')
    classes = parameters['defaults']
    ids = set()
    for u,v,key,d in g.edges(keys=True,data=True):
        road = d.get('highway','unclassified')
        if isinstance(road,list):
            raise ValueError('simplification merged differing highway tags')
        default = classes.get(road,classes['fallback'])
        geometry = d.get('geometry',LineString([(g.nodes[u]['x'],g.nodes[u]['y']),(g.nodes[v]['x'],g.nodes[v]['y'])]))
        if Point(geometry.coords[-1]).distance(Point(g.nodes[u]['x'],g.nodes[u]['y'])) < Point(geometry.coords[0]).distance(Point(g.nodes[u]['x'],g.nodes[u]['y'])):
            geometry = LineString(list(geometry.coords)[::-1])
        d['geometry'] = geometry
        osm = d['osmid']
        osm_ids = sorted(osm) if isinstance(osm,list) else [osm]
        token = json.dumps([osm_ids,u,v,key,list(geometry.coords)],separators=(',',':'))
        d['edge_id'] = 'osm_'+sha256(token.encode()).hexdigest()[:24]
        if d['edge_id'] in ids:
            raise ValueError('duplicate stable edge ID')
        ids.add(d['edge_id'])
        d.update(u=int(u),v=int(v),key=int(key),osm_id=json.dumps(osm_ids),road_class=road)
        # OSMnx records whether travel is reversed relative to original way order.
        reversed_way = d.get('reversed',False)
        if not isinstance(reversed_way,bool):
            raise ValueError('mixed direction attributes after simplification')
        # OSMnx reverses the node list for oneway=-1 before setting reversed=False.
        if d.get('oneway_osm_raw') in {'-1','reverse','T'}:
            reversed_way=not reversed_way
        suffix = 'backward' if reversed_way else 'forward'
        one = d.get('oneway')
        if not isinstance(one,bool):
            raise ValueError('normalized oneway boolean required')
        lane_tag = d.get('lanes:'+suffix)
        lanes = parse_positive_tag(lane_tag)
        lane_source = 'osm_lanes:'+suffix
        if lanes is None:
            total = parse_positive_tag(d.get('lanes'))
            if total is not None:
                if one:
                    lanes,lane_source = total,'osm_lanes_oneway'
                else:
                    opposite = parse_positive_tag(d.get('lanes:'+('forward' if reversed_way else 'backward')))
                    if opposite is not None and total > opposite:
                        lanes,lane_source=total-opposite,'estimated_total_minus_opposite'
                    else:
                        lanes,lane_source=max(1,math.floor(total/2)),'estimated_bidirectional_split'
            else:
                lanes,lane_source=default['lanes_per_direction'],'estimated_class_default'
        speed_tag=d.get('maxspeed:'+suffix)
        speed=parse_positive_tag(speed_tag,speed=True)
        speed_source='osm_maxspeed:'+suffix
        if speed is None:
            speed=parse_positive_tag(d.get('maxspeed'),speed=True)
            speed_source='osm_maxspeed'
        if speed is None:
            speed,speed_source=default['speed_kph'],'estimated_class_default'
        d.update(lanes_raw=json.dumps(d.get('lanes')),maxspeed_raw=json.dumps(d.get('maxspeed')),
                 lanes_per_direction=int(lanes),lanes_source=lane_source,speed_limit_kph=float(speed),
                 speed_source=speed_source,free_flow_speed_kph=float(speed)*parameters['free_flow_factor'],
                 free_flow_speed_source='estimated_limit_times_factor',
                 capacity_veh_h=float(lanes)*default['capacity_per_lane_veh_h'],capacity_source='estimated_class_per_lane')
    projected=ox.project_graph(g,to_crs=parameters['projected_crs'])
    for u,v,k,d in g.edges(keys=True,data=True):
        # project_graph projects geometries only for simplified graphs; source is always simplified here.
        pd=projected.edges[u,v,k]
        length=float(pd['geometry'].length)
        if not math.isfinite(length) or length<=0:
            raise ValueError('nonpositive projected road length')
        d['length_osmnx_m']=float(d['length'])
        d['length']=d['length_m']=length
        d['length_source']='OSM geometry projected EPSG:32650'
        d['free_flow_time_s']=length/(d['free_flow_speed_kph']/3.6)
    g.graph.update(edge_id_scheme='sha256(osmid,u,v,key,oriented_geometry)[:24]; stable for same topology/snapshot',
                   length_crs=parameters['projected_crs'],capacity_note='estimated veh/h, not measured')
    return g


def shortest_route(g,source,target):
    """Dijkstra supports every reachable pair; select the actual parallel edge key."""
    nodes=nx.shortest_path(g,source,target,weight='free_flow_time_s')
    edges=[]
    for u,v in zip(nodes,nodes[1:]):
        k=min(g[u][v],key=lambda k:(g[u][v][k]['free_flow_time_s'],g[u][v][k]['edge_id']))
        edges.append((u,v,k))
    return {'nodes':nodes,'edge_ids':[g.edges[e]['edge_id'] for e in edges],
            'travel_time_s':sum(g.edges[e]['free_flow_time_s'] for e in edges),
            'length_m':sum(g.edges[e]['length_m'] for e in edges)}


def network_statistics(g, *, seed=42, sample_origins=20):
    ids=[d['edge_id'] for *_,d in g.edges(data=True,keys=True)]
    if len(ids)!=len(set(ids)):
        raise ValueError('duplicate edge IDs')
    required=['length_m','free_flow_speed_kph','free_flow_time_s','capacity_veh_h','lanes_per_direction','speed_limit_kph']
    for _,_,d in g.edges(data=True):
        if any(not math.isfinite(d[k]) or d[k]<=0 for k in required):
            raise ValueError('invalid positive road attributes')
    weak=sorted(nx.weakly_connected_components(g),key=len,reverse=True)
    strong=sorted(nx.strongly_connected_components(g),key=lambda x:(-len(x),min(x)))
    largest=strong[0]
    import random
    origins=random.Random(seed).sample(sorted(g.nodes),min(sample_origins,len(g)))
    # For each sampled origin, check ALL reachable targets against the SCC condensation.
    condensation=nx.condensation(g)
    mapping=condensation.graph['mapping']
    reach_counts=[]
    for origin in origins:
        reachable=nx.single_source_dijkstra_path_length(g,origin,weight='free_flow_time_s')
        components=nx.descendants(condensation,mapping[origin])|{mapping[origin]}
        expected=sum(len(condensation.nodes[c]['members']) for c in components)
        if len(reachable)!=expected or any(not math.isfinite(v) for v in reachable.values()):
            raise ValueError('reachable shortest-path audit failed')
        reach_counts.append({'origin':origin,'reachable_nodes':len(reachable)})
    source=min(largest)
    distances=nx.single_source_dijkstra_path_length(g,source,weight='free_flow_time_s')
    target=max(largest,key=lambda n:distances[n])
    sample=shortest_route(g,source,target)
    parallel_pairs=sum(1 for u in g for v in g[u] if len(g[u][v])>1)
    return {
        'nodes':len(g),'directed_edges':g.number_of_edges(),'unique_edge_ids':len(set(ids)),
        'weak_components':len(weak),'strong_components':len(strong),
        'largest_weak_nodes':len(weak[0]),'largest_strong_nodes':len(largest),
        'strong_component_fraction':len(largest)/len(g),'parallel_directed_pairs':parallel_pairs,
        'oneway_edges':sum(d['oneway'] for *_,d in g.edges(data=True,keys=True)),
        'self_loops':nx.number_of_selfloops(g),'total_directed_length_m':sum(d['length_m'] for *_,d in g.edges(data=True,keys=True)),
        'missing_required_attributes':0,'length_min_m':min(d['length_m'] for *_,d in g.edges(data=True,keys=True)),
        'attribute_sources':{k:dict(Counter(d[k] for *_,d in g.edges(data=True,keys=True))) for k in ['lanes_source','speed_source','capacity_source']},
        'routing_audit':{'sampled_origins':len(origins),'checked_reachable_pairs':sum(x['reachable_nodes'] for x in reach_counts),'per_origin':reach_counts,'scope':'All destinations for sampled origins; SCC reachability independently compared. General API supports arbitrary reachable pairs.'},
        'sample_route':sample,
        'limitations':['OSM snapshot, not survey ground truth','Disconnected components retained; no invented edges','OSM turn restriction relations and conditional access not enforced','Capacity and free-flow assumptions require later calibration']
    }


def export_network(g,directory):
    directory.mkdir(parents=True,exist_ok=False)
    ox.save_graphml(g,directory/'road_network.graphml')
    nodes,edges=ox.graph_to_gdfs(g)
    # GeoJSON/CSV scalar fields preserve lists explicitly as JSON strings.
    for frame in (nodes,edges):
        for column in frame.columns:
            if column!='geometry':
                frame[column]=frame[column].map(lambda x:json.dumps(x,ensure_ascii=False) if isinstance(x,(list,tuple,dict,set)) else x)
    nodes=nodes.reset_index().rename(columns={'osmid':'node_id'})
    edges=edges.reset_index(drop=True)
    nodes.to_file(directory/'road_nodes.geojson',driver='GeoJSON')
    edges.to_file(directory/'road_edges.geojson',driver='GeoJSON')
    import pandas as pd
    csv=pd.DataFrame(edges.drop(columns='geometry')); csv['geometry']=edges.geometry.to_wkt(); csv.to_csv(directory/'road_attributes.csv',index=False,encoding='utf-8-sig')
    return directory
