"""Independent coverage, vehicle-time and resource audit for a whole-district baseline."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
from uftr.sumo_dynamic import write_json

ROOT = Path(__file__).resolve().parents[1]


def audit(out):
    inputs = json.loads((out/'inputs.json').read_text(encoding='utf-8'))
    for item in inputs:
        h = hashlib.sha256()
        with (ROOT/item['path']).open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                h.update(block)
        assert h.hexdigest() == item['sha256'], item['path']
    scope = json.loads((out/'raw/scope.json').read_text(encoding='utf-8'))
    mapping = pd.read_csv(out/'raw/source_sumo_mapping.csv')
    assert scope['district_arcs_in_sumo'] == scope['district_source_arcs'] == mapping.intersects_district.sum()
    # Independently reconstruct spatial coverage from the original frozen nodes
    # and full source arcs, instead of trusting the preparation count alone.
    import geopandas as gpd
    import shapely
    from pyproj import Transformer
    from uftr.sumo_dynamic import read_nodes
    sources_by_name = {Path(item['path']).name: ROOT/item['path'] for item in inputs}
    source = pd.read_parquet(sources_by_name['source_edges.parquet'])
    assert np.array_equal(source.iloc[mapping.source_arc_position].edge_id.to_numpy(), mapping.edge_id.to_numpy())
    coords = read_nodes(sources_by_name['inferred_source_network.graphml'])
    endpoints = np.array([[coords[int(u)], coords[int(v)]] for u, v in zip(source.u, source.v)])
    transformer = Transformer.from_crs(4326, 32650, always_xy=True)
    x, y = transformer.transform(endpoints[:, :, 0], endpoints[:, :, 1])
    original_segments = shapely.linestrings(np.stack([x, y], axis=-1))
    boundary = gpd.read_file(sources_by_name['study_boundary.geojson']).to_crs(32650).geometry.union_all()
    district = shapely.intersects(original_segments, boundary)
    usable = (source.u != source.v).to_numpy() & (source.length_m.to_numpy() > .1)
    assert set(source.loc[district & usable, 'edge_id']) == set(mapping.loc[mapping.intersects_district, 'edge_id'])
    assert int(np.count_nonzero(district & ~usable)) == scope['excluded_district_degenerate_arcs']
    del coords, endpoints, x, y, original_segments, source
    # Stream edge and connection elements instead of loading a second large graph.
    edges = set(); connections = set()
    for _, element in ET.iterparse(out/'raw/network.net.xml', events=('end',)):
        if element.tag == 'edge' and element.attrib.get('function') != 'internal':
            edges.add(element.attrib['id'])
        elif element.tag == 'connection' and not element.attrib['from'].startswith(':'):
            connections.add((element.attrib['from'], element.attrib['to']))
        element.clear()
    assert edges == set(mapping.edge_id)
    plan = pd.read_csv(out/'raw/departure_plan.csv').fillna({'normal_route': ''})
    checked = set()
    connectors = pd.read_csv(sources_by_name['zone_connectors.csv'])
    source_nodes = dict(zip(mapping.edge_id, zip(mapping.u, mapping.v)))
    for r in plan.loc[plan.valid].itertuples():
        endpoints = r.normal_route.split()
        assert source_nodes[endpoints[0]][0] == connectors.node_id.iloc[r.origin_zone]
        assert source_nodes[endpoints[-1]][1] == connectors.node_id.iloc[r.destination_zone]
        if r.normal_route in checked:
            continue
        path = r.normal_route.split()
        assert set(path) <= edges
        assert all((a, b) in connections for a, b in zip(path, path[1:]))
        checked.add(r.normal_route)
    folder = out/'cases/dry'
    result = json.loads((folder/'result.json').read_text(encoding='utf-8'))
    assert result['planned'] == len(plan)
    assert result['invalid'] == (~plan.valid).sum()
    assert result['planned'] == sum(result[k] for k in ['invalid', 'external_pending', 'sumo_pending', 'running', 'arrived'])
    series = pd.read_csv(folder/'traffic_series.csv')
    assert (series.injected == series.arrived+series.running+series.sumo_pending).all()
    assert (series.released_valid == series.injected+series.external_pending).all()
    complete = {}
    for _, element in ET.iterparse(folder/'tripinfo.xml', events=('end',)):
        if element.tag == 'tripinfo' and float(element.attrib['arrival']) >= 0:
            complete[element.attrib['id']] = float(element.attrib['arrival'])
        element.clear()
    assert len(complete) == result['arrived']
    independent = sum(complete.get(r.vehicle_id, result['duration_seconds'])+1-np.ceil(r.depart_s)
                      for r in plan.loc[plan.valid].itertuples())
    assert abs(independent-result['vehicle_seconds']) < 1e-6
    hourly = pd.read_csv(folder/'hourly_performance.csv')
    assert hourly.simulation_hour.tolist() == [1, 2, 3, 4]
    assert np.all(hourly.wall_seconds > 0)
    assert np.allclose(hourly.wall_seconds.cumsum(), hourly.cumulative_loop_wall_seconds)
    resource_summary = json.loads((out/'resources_summary.json').read_text(encoding='utf-8'))
    trace = pd.read_csv(out/resource_summary['trace'])
    assert np.isclose(trace.combined_rss_mib.max(), resource_summary['peak_combined_rss_mib'])
    assert np.allclose(trace.python_rss_mib+trace.children_rss_mib, trace.combined_rss_mib)
    assert (hourly.peak_combined_rss_mib > 0).all()
    assert result['headless'] is True
    command = json.loads((folder/'command.json').read_text(encoding='utf-8'))
    assert 'sumo-gui' not in command[0]
    assert result['balance_error'] == result['injected_balance_error'] == 0
    assert result['teleports'] == 0
    actual_routes = 0
    vehicle_ids = set(plan.loc[plan.valid, 'vehicle_id'])
    with gzip.open(folder/'vehicle_routes.xml.gz', 'rb') as stream:
        for _, element in ET.iterparse(stream, events=('end',)):
            if element.tag == 'vehicle':
                assert element.attrib['id'] in vehicle_ids
                route_elements = element.findall('.//route')
                assert route_elements
                path = route_elements[-1].attrib['edges'].split()
                assert set(path) <= edges
                assert all((a, b) in connections for a, b in zip(path, path[1:]))
                actual_routes += 1
                element.clear()
    assert actual_routes == result['injected']
    fcd_rows = 0
    with gzip.open(folder/'fcd.xml.gz', 'rb') as stream:
        for _, element in ET.iterparse(stream, events=('end',)):
            if element.tag == 'timestep':
                fcd_rows += 1
            element.clear()
    report = {'source_sha_verified': len(inputs), 'source_sumo_arcs': len(edges),
        'whole_district_arcs_checked': scope['district_source_arcs'], 'unique_valid_paths_checked': len(checked),
        'planned': len(plan), 'valid': int(plan.valid.sum()), 'invalid': int((~plan.valid).sum()),
        'arrived': len(complete), 'vehicle_seconds_independent': float(independent),
        'hourly_records_checked': len(hourly), 'resource_samples_checked': len(trace),
        'fcd_timestep_records': fcd_rows, 'headless_verified': True, 'vehicle_balance_error': 0,
        'actual_injected_routes_checked': actual_routes,
        'teleports': result['teleports'], 'collision_vehicle_events': result['collision_vehicle_events'],
        'note': 'Internal consistency, not calibration against observed traffic; coverage is against the frozen source road topology.'}
    write_json(out/'independent_audit.json', report)
    print(json.dumps(report, indent=2), flush=True)
    return report


def figures(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder = out/'figures'; folder.mkdir(exist_ok=True)
    hourly = pd.read_csv(out/'cases/dry/hourly_performance.csv')
    summary = json.loads((out/'resources_summary.json').read_text(encoding='utf-8'))
    trace = pd.read_csv(out/summary['trace'])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout='constrained')
    axes[0].bar(hourly.simulation_hour, hourly.wall_seconds/60)
    axes[0].set(xlabel='Simulation hour', ylabel='Wall minutes per simulated hour', xticks=[1, 2, 3, 4])
    axes[1].plot(trace.wall_s/60, trace.combined_rss_mib/1024, label='Python + descendants RSS')
    axes[1].plot(trace.wall_s/60, trace.host_available_mib/1024, label='Host available memory', alpha=.7)
    axes[1].set(xlabel='Wall minutes (includes preparation)', ylabel='GiB')
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('Whole Longgang | 5% synthetic demand | headless dry baseline')
    fig.savefig(folder/'performance.png', dpi=160)
    fig.savefig(folder/'performance.svg')
    plt.close(fig)
    # Administrative boundary and retained connecting roads, with dense road
    # collections rasterized inside SVG to keep the evidence compact.
    import geopandas as gpd
    from matplotlib.collections import LineCollection
    mapping = pd.read_csv(out/'raw/source_sumo_mapping.csv')
    positions = {}
    node_file = out/'raw/network.nod.xml'
    node_stream = node_file.open('rb') if node_file.exists() else gzip.open(str(node_file)+'.gz', 'rb')
    for _, element in ET.iterparse(node_stream, events=('end',)):
        if element.tag == 'node':
            positions[int(element.attrib['id'])] = (float(element.attrib['x']), float(element.attrib['y']))
        element.clear()
    node_stream.close()
    segments = np.array([[positions[int(u)], positions[int(v)]] for u, v in zip(mapping.u, mapping.v)])
    fig, ax = plt.subplots(figsize=(9, 8), layout='constrained')
    inside = mapping.intersects_district.to_numpy(bool)
    for mask, color, label in [(~inside, '#aaaaaa', 'Surroundings and complete dry-path connectors'),
                               (inside, '#2774a6', 'Source road arcs intersecting Longgang')]:
        ax.add_collection(LineCollection(segments[mask], colors=color, linewidths=.25, rasterized=True, label=label))
    boundary = gpd.read_file(out/'raw/study_boundary.geojson').to_crs(32650).geometry.union_all()
    offset = json.loads((out/'raw/window.json').read_text(encoding='utf-8'))['projected_offset_m']
    for polygon in getattr(boundary, 'geoms', [boundary]):
        xy = np.array(polygon.exterior.coords)-np.array(offset)
        ax.plot(xy[:, 0], xy[:, 1], color='#a52a2a', linewidth=1)
    ax.autoscale(); ax.set_aspect('equal')
    ax.set(title='Whole Longgang excluding Dapeng | full district + connecting roads',
           xlabel='Local east (m)', ylabel='Local north (m)')
    ax.legend(fontsize=7, loc='lower left')
    fig.savefig(folder/'whole_district_coverage.png', dpi=160)
    fig.savefig(folder/'whole_district_coverage.svg')
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('run')
    args = parser.parse_args(); out = (ROOT/args.run).resolve()
    audit(out); figures(out)
