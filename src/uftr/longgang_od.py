"""Longgang synthetic OD from supplied linework; topology is inferred, not certified.

Only identical existing vertices are joined. Geometric line intersections are
never noded, and missing road connections are never fabricated. All disconnected
demand stays in the matrix. This is a demand prototype, not measured demand.
"""
from collections import defaultdict
import json
import math
import re
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import Point, Polygon, LineString


def tag_string(value):
    return '' if value is None or pd.isna(value) else str(value).strip().lower()


def parse_tags(value):
    return dict(re.findall(r'"([^"\\]+)"=>"([^"\\]*)"', str(value or '')))


def direction_and_speed(row, settings):
    tags = parse_tags(row.get('other_tags'))
    highway = tag_string(row.get('highway'))
    prohibited = {str(v).lower() for v in settings['prohibited_access']}
    access = next((tag_string(tags[k]) for k in ['motorcar', 'motor_vehicle', 'vehicle', 'access'] if k in tags), '')
    if access in prohibited or highway in {'busway', 'construction', 'proposed', 'footway', 'cycleway', 'path', 'steps', 'pedestrian'}:
        return None
    one = tag_string(row.get('oneway')) or tag_string(tags.get('oneway'))
    if one in {'-1', 'reverse'}:
        direction = -1
    elif one in {'yes', '1', 'true'}:
        direction = 1
    elif one in {'no', '0', 'false'}:
        direction = 0
    elif one:
        # Reversible/alternating operation has no known schedule: retain separately.
        return None
    else:
        direction = 1 if highway == 'motorway' or tags.get('junction') in {'roundabout', 'circular'} else 0
    speed_text = tag_string(row.get('maxspeed')) or tags.get('maxspeed', '')
    speeds = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', speed_text)]
    speed = min(speeds) * (1.609344 if 'mph' in speed_text else 1) if speeds else 0
    observed = 0 < speed <= 160
    if not observed:
        speed = settings['default_speed_kph'].get(highway, settings['default_speed_fallback_kph'])
    grade = (tag_string(row.get('layer')) or '0',
             tag_string(row.get('bridge')) not in {'', 'no', '0', 'false'},
             tag_string(row.get('tunnel')) not in {'', 'no', '0', 'false'})
    return direction, float(speed), observed, grade


def inferred_graph(roads, settings):
    """Keep source feature/segment IDs and parallel arcs; no coordinate rounding.

    Cross-grade joins require an existing shared endpoint on BOTH source lines.
    Interior crossings on different grades remain separate. These transitions
    are an explicit inference because the delivered source has no OSM node IDs.
    """
    projected = roads.to_crs(32650)
    features = []
    vertices = defaultdict(list)
    rejected = []
    for position, (_, row) in enumerate(roads.iterrows()):
        parsed = direction_and_speed(row, settings)
        if parsed is None:
            rejected.append({'source_feature_position': position, 'osm_id': str(row.osm_id), 'reason': 'restricted_or_unsupported_access_direction_or_class'})
            continue
        geom = row.geometry
        if geom.geom_type != 'LineString':
            raise ValueError('Review non-LineString source before graph inference')
        coords = list(geom.coords)
        metric = list(projected.geometry.iloc[position].coords)
        direction, speed, speed_from_tag, grade = parsed
        idx = len(features)
        features.append((position, row, coords, metric, direction, speed, speed_from_tag, grade))
        for k, xy in enumerate(coords):
            vertices[tuple(xy[:2])].append((idx, k, grade, k in {0, len(coords)-1}))
    graph = nx.MultiDiGraph(crs='EPSG:4326', topology='inferred_shared_vertices_not_certified')
    node_lookup = {}
    for xy, occurrences in vertices.items():
        # If distinct grade lines both terminate here, allow their shared endpoint.
        end_grades = {g for _, _, g, end in occurrences if end}
        for idx, k, grade, endpoint in occurrences:
            token = ('endpoint_transition',) if endpoint and len(end_grades) > 1 else grade
            key = (xy, token)
            if key not in node_lookup:
                node = len(node_lookup)
                node_lookup[key] = node
                graph.add_node(node, x=xy[0], y=xy[1], inferred_grade=str(token))
    transition_nodes = 0
    for position, row, coords, metric, direction, speed, speed_from_tag, grade in features:
        ids = []
        for k, xy0 in enumerate(coords):
            xy = tuple(xy0[:2])
            end_grades = {g for _, _, g, end in vertices[xy] if end}
            endpoint = k in {0, len(coords)-1}
            token = ('endpoint_transition',) if endpoint and len(end_grades) > 1 else grade
            ids.append(node_lookup[(xy, token)])
        for k, (u, v) in enumerate(zip(ids[:-1], ids[1:])):
            length = math.dist(metric[k][:2], metric[k+1][:2])
            if length <= 0:
                continue
            attributes = dict(source_feature_position=position, osm_id=str(row.osm_id),
                segment_index=k, length_m=length, speed_kph=speed,
                speed_from_source_tag=speed_from_tag, free_flow_time_s=length/(speed/3.6),
                highway=tag_string(row.highway), grade=str(grade))
            if direction >= 0:
                graph.add_edge(u, v, edge_id=f'fidpos{position}_seg{k}_f', **attributes)
            if direction <= 0:
                graph.add_edge(v, u, edge_id=f'fidpos{position}_seg{k}_r', **attributes)
    for node in graph:
        transition_nodes += graph.nodes[node]['inferred_grade'] == "('endpoint_transition',)"
    nodes = gpd.GeoDataFrame([{'node_id': n, 'geometry': Point(d['x'], d['y'])} for n, d in graph.nodes(data=True)], crs=4326)
    weak = sorted((len(c) for c in nx.weakly_connected_components(graph)), reverse=True)
    strong = sorted((len(c) for c in nx.strongly_connected_components(graph)), reverse=True)
    report = {'source_features': len(roads), 'accepted_features': len(features),
        'excluded_features': len(rejected), 'nodes': len(graph), 'directed_arcs': graph.number_of_edges(),
        'weak_components': len(weak), 'largest_weak_component_nodes': weak[0],
        'strong_components': len(strong), 'largest_strong_component_nodes': strong[0],
        'cross_grade_endpoint_transition_nodes': transition_nodes,
        'source_authoritative_node_ids_available': False,
        'topology_certified': False, 'arbitrary_line_intersections_joined': False,
        'scope': 'Entire supplied Shenzhen motor layer for skims; OD internal zones only Longgang excluding Dapeng',
        'limitations': ['Exact shared coordinates are inferred shared nodes, not original OSM node identities',
            'No missing junctions or connections to outside Shenzhen added',
            'Turn restrictions, conditional access and directional speed limits unavailable',
            'Missing maxspeed uses configured road-class estimates; speeds are not measured']}
    return graph, nodes, pd.DataFrame(rejected), report


def population_allocation(zones, raster_path):
    """Clip counts by overlap / FULL native cell area, preserving boundary fractions."""
    study = zones.to_crs(4326).geometry.union_all()
    with rasterio.open(raster_path) as source:
        if source.crs.to_epsg() != 4326:
            raise ValueError('Expected source WorldPop EPSG4326')
        win = from_bounds(*study.bounds, source.transform).round_offsets().round_lengths()
        # Include the surrounding native cells at all four sides.
        from rasterio.windows import Window
        win = Window(max(0, int(win.col_off)-1), max(0, int(win.row_off)-1), int(win.width)+3, int(win.height)+3)
        array = source.read(1, window=win, masked=True)
        transform = source.window_transform(win)
        records = []
        valid_area = 0.
        nodata_area = 0.
        cell_count = 0
        for r in range(array.shape[0]):
            for c in range(array.shape[1]):
                corners = [transform*(c,r), transform*(c+1,r), transform*(c+1,r+1), transform*(c,r+1)]
                cell = gpd.GeoSeries([Polygon(corners)], crs=4326).to_crs(32650).iloc[0]
                indices = zones.sindex.query(cell, predicate='intersects')
                overlaps = [(int(i), cell.intersection(zones.geometry.iloc[i]).area) for i in indices]
                overlaps = [(i,a) for i,a in overlaps if a > 1e-6]
                if not overlaps:
                    continue
                if np.ma.is_masked(array[r,c]):
                    nodata_area += sum(a for _,a in overlaps)
                    continue
                value = float(array[r,c])
                if not math.isfinite(value) or value < 0:
                    raise ValueError('Invalid WorldPop count')
                valid_area += sum(a for _,a in overlaps)
                cell_count += 1
                for i, area in overlaps:
                    records.append({'cell_id': f'r{int(win.row_off)+r}_c{int(win.col_off)+c}',
                        'zone_id': zones.zone_id.iloc[i], 'native_cell_people': value,
                        'native_cell_area_m2': cell.area, 'overlap_area_m2': area,
                        'allocated_people': value*area/cell.area})
    allocation = pd.DataFrame(records)
    values = zones[['zone_id', 'area_m2']].copy()
    values['population_estimate'] = values.zone_id.map(allocation.groupby('zone_id').allocated_people.sum()).fillna(0.)
    values['production_share'] = values.population_estimate / values.population_estimate.sum()
    values['attraction_share'] = values.production_share
    area = float(zones.area.sum())
    report = {'native_cells_intersecting': cell_count, 'allocated_people': float(values.population_estimate.sum()),
        'boundary_area_km2': area/1e6, 'valid_raster_overlap_area_km2': valid_area/1e6,
        'nodata_overlap_area_km2': nodata_area/1e6, 'valid_area_fraction': valid_area/area,
        'allocation': 'population count times intersection area divided by full native cell area; no edge-cell inflation',
        'attraction_proxy': 'population_only; no employment or commercial POI data available',
        'population_year': 2020, 'population_is_modelled_not_census': True}
    # Projected straight-edge cell/zone approximations can leave sub-metre edge
    # slivers; expose this rather than silently normalizing native-cell counts.
    report['projected_area_closure_error_m2'] = valid_area+nodata_area-area
    if abs(valid_area+nodata_area-area) > max(1., area*1e-4):
        raise ValueError(f'Raster window does not cover all zones: {valid_area+nodata_area-area} m2')
    return values, allocation, report


def fast_network_skims(connectors, graph, access_speed_kph, intrazonal_time_s):
    """SciPy directed Dijkstra; explicit minimum cost for parallel-arc skim only."""
    count = len(graph)
    minimum = {}
    for u,v,d in graph.edges(data=True):
        minimum[(u,v)] = min(minimum.get((u,v), math.inf), d['free_flow_time_s'])
    keys = list(minimum)
    csr = coo_matrix(([minimum[k] for k in keys], ([k[0] for k in keys], [k[1] for k in keys])), shape=(count,count)).tocsr()
    times = np.full((len(connectors),len(connectors)), np.nan)
    linked = np.flatnonzero(connectors.connected.to_numpy(bool))
    indices = connectors.iloc[linked].node_id.astype(int).to_numpy()
    # Batch origins to keep intermediate memory bounded on the full source graph.
    for start in range(0, len(linked), 32):
        rows = linked[start:start+32]
        distances = dijkstra(csr, directed=True, indices=indices[start:start+32])[:, indices]
        access = (connectors.iloc[rows].connector_distance_m.to_numpy(float)[:,None]
                  + connectors.iloc[linked].connector_distance_m.to_numpy(float)[None,:])/(access_speed_kph/3.6)
        times[np.ix_(rows,linked)] = np.where(np.isfinite(distances), distances+access, np.nan)
    for i in range(len(connectors)):
        if connectors.zone_kind.iloc[i] == 'internal':
            times[i,i] = intrazonal_time_s
    return times


def schedule(period_matrices, settings):
    interval = settings['interval_minutes']
    duration = settings['duration_hours']
    if interval <= 0 or (duration*60) % interval:
        raise ValueError('Time window must divide into complete intervals')
    records = []
    for k in range(duration*60//interval):
        hour = k*interval/60
        a,b = settings['morning_peak_hours']; c,d = settings['evening_peak_hours']
        period = 'morning_peak' if a <= hour < b else ('evening_peak' if c <= hour < d else 'offpeak')
        if int(a*60)%interval or int(b*60)%interval or int(c*60)%interval or int(d*60)%interval:
            raise ValueError('Peak boundaries must align with interval edges')
        records.append({'interval':k, 'start_minute':k*interval, 'end_minute':(k+1)*interval,
            'start_time':f'{int(hour):02d}:{k*interval%60:02d}', 'period':period,
            'duration_hours':interval/60, 'expected_vehicle_trips':float(period_matrices[period].sum()*interval/60)})
    return pd.DataFrame(records)
