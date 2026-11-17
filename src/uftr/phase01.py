"""Acquire, model, export, audit and archive the Phase 01 real road networks."""
from pathlib import Path
import json
import shutil
import sys

import geopandas as gpd
import networkx as nx
import osmnx as ox
from shapely.geometry import box,shape

from .archive import RunArchive,file_hash,now,write_json
from .config import load_config
from .network import normalize_roads,network_statistics,export_network
from .osm_download import boundary_from_nominatim,download_tiles,graph_from_tiles
from .sioux import download_sioux,parse_sioux


def plot_network(g,polygon,statistics,path,label,run_id,dpi):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    edges=ox.graph_to_gdfs(g,nodes=False).to_crs(32650)
    boundary=gpd.GeoSeries([polygon],crs=4326).to_crs(32650)
    fig,ax=plt.subplots(figsize=(10,9),layout='constrained')
    ax.add_collection(LineCollection([list(geom.coords) for geom in edges.geometry],colors='#597b92',linewidths=.65,alpha=.8))
    route=set(statistics['sample_route']['edge_ids'])
    selected=edges[edges.edge_id.isin(route)]
    ax.add_collection(LineCollection([list(geom.coords) for geom in selected.geometry],colors='#d54a35',linewidths=2,label='Verified shortest-time route'))
    # Fit actual roads, retaining an inset overview of the full administrative polygon.
    ax.autoscale(); ax.set_aspect('equal'); ax.ticklabel_format(style='plain',useOffset=False)
    ax.set_xlabel('Easting (m), EPSG:32650'); ax.set_ylabel('Northing (m), EPSG:32650')
    ax.set_title(f'{label}: actual OSM motor-road network\n{statistics["nodes"]:,} nodes | {statistics["directed_edges"]:,} directed edges | {statistics["weak_components"]} weak components')
    ax.legend(loc='lower right')
    inset=ax.inset_axes([.015,.025,.23,.23]); boundary.boundary.plot(ax=inset,color='#34465b',linewidth=.8)
    for geom in edges.geometry:
        xs,ys=geom.xy; inset.plot(xs,ys,color='#597b92',linewidth=.25)
    inset.set_xticks([]); inset.set_yticks([]); inset.set_title('Full study boundary',fontsize=8)
    fig.text(.01,.005,f'© OpenStreetMap contributors | ODbL 1.0 | {run_id} | Free-flow weights estimated',fontsize=8)
    for ext in ('png','svg'): fig.savefig(path.with_suffix('.'+ext),dpi=dpi)
    plt.close(fig)


def run_phase01(root,config_path,offline_source=None):
    config=load_config(config_path)
    if config['phase']!='01': raise ValueError('Phase 01 configuration required')
    settings=config['network']; params=settings['attributes']
    contract={k:settings[k] for k in ['small_bbox','expected_relation_id','buffer_m']}
    contract['filter_version']='OSMnx-2.1.2-drive-equivalent-v1'
    inputs=[config_path,*sorted((root/'src/uftr').glob('*.py'))]
    with RunArchive(root,config,inputs) as run:
        run.manifest['command']=[sys.executable,*sys.argv]; run.flush()
        if offline_source:
            snapshot=(root/offline_source).resolve(); snapshot.relative_to(root)
            source=json.loads((snapshot/'source_inventory.json').read_text(encoding='utf-8'))
            if source['contract']!=contract: raise ValueError('offline source differs from download contract')
            for item in source['files']:
                p=(snapshot/item['path']).resolve(); p.relative_to(snapshot)
                if file_hash(p)!=item['sha256']: raise ValueError('offline source checksum mismatch')
            payload=json.loads((snapshot/'nanshan_boundary.geojson').read_text(encoding='utf-8'))
            polygon=shape(payload['features'][0]['geometry'])
        else:
            snapshot=root/'data/raw/phase01'/run.run_id
            snapshot.mkdir(parents=True,exist_ok=False)
            polygon=boundary_from_nominatim(snapshot,settings)
            download_sioux(snapshot/'sioux_falls',settings['sioux'])
        processed=root/'data/processed/phase01'/run.run_id
        processed.mkdir(parents=True,exist_ok=False)
        reports={}; regions={'small':box(*settings['small_bbox']),'nanshan':polygon}
        for name,region in regions.items():
            run.log('region started: '+name); print('Region '+name,flush=True)
            source_dir=snapshot/name
            if not offline_source:
                download_tiles(region,source_dir,settings,log=lambda message:(run.log(message),print(message,flush=True)))
            raw_graph=graph_from_tiles(source_dir,region)
            original=set(raw_graph.edges(keys=True))
            graph=normalize_roads(raw_graph,params)
            if set(graph.edges(keys=True))!=original: raise ValueError('attribute normalization changed topology')
            stats=network_statistics(graph,seed=config['seed'],sample_origins=settings['routing_sample_origins'])
            stats.update(region=name,run_id=run.run_id,source_crs='EPSG:4326',length_crs='EPSG:32650',source_method=graph.graph['source_method'],boundary_area_km2=float(gpd.GeoSeries([region],crs=4326).to_crs(32650).area.iloc[0]/1e6),boundary_note='Include all administrative territory, including islands/sea where applicable. Boundary-crossing edges retained when endpoint adjacent; all components retained.')
            output=export_network(graph,processed/name)
            write_json(output/'network_statistics.json',stats)
            gpd.GeoSeries([region],crs=4326).to_file(output/'study_boundary.geojson',driver='GeoJSON')
            # Reload exactly what subsequent phases will use, and verify the route and edge IDs.
            reloaded=ox.load_graphml(output/'road_network.graphml',edge_dtypes={'u':int,'v':int,'key':int,'length_m':float,'free_flow_time_s':float,'capacity_veh_h':float,'free_flow_speed_kph':float,'lanes_per_direction':int,'speed_limit_kph':float})
            after=network_statistics(reloaded,seed=config['seed'],sample_origins=settings['routing_sample_origins'])
            if after['sample_route']!=stats['sample_route'] or after['unique_edge_ids']!=stats['unique_edge_ids']: raise ValueError('GraphML roundtrip route mismatch')
            figure=run.path/'figures'/('road_network' if name=='nanshan' else 'small_road_network')
            plot_network(graph,region,stats,figure,'Nanshan' if name=='nanshan' else 'Shenzhen University pilot',run.run_id,config['outputs']['dpi'])
            shutil.copy2(figure.with_suffix('.png'),output/'road_network.png')
            for ext in ('png','svg'):
                run.add_artifact(figure.with_suffix('.'+ext),title=('南山区' if name=='nanshan' else '小区域')+'真实机动车路网与最短路',kind='figure',data_kind='mixed',source_paths=[output/'road_network.graphml',output/'network_statistics.json',snapshot/'nanshan_boundary.geojson'],units={'coordinates':'EPSG:32650 m','time':'s'})
            reports[name]=stats
            print(name,stats['nodes'],stats['directed_edges'],stats['weak_components'],flush=True)
        reports['sioux_falls']=parse_sioux(snapshot/'sioux_falls',processed/'sioux_falls')
        if not offline_source:
            write_json(snapshot/'source_inventory.json',{'created_at':now(),'contract':contract,'files':[{'path':p.relative_to(snapshot).as_posix(),'sha256':file_hash(p)} for p in sorted(snapshot.rglob('*')) if p.is_file()]})
        run.manifest['inputs'].extend({'path':str(p.resolve()),'sha256':file_hash(p)} for p in sorted(snapshot.rglob('*')) if p.is_file())
        reports.update(run_id=run.run_id,source_snapshot=str(snapshot.relative_to(root)),processed_root=str(processed.relative_to(root)),source_replay=bool(offline_source),status='passed')
        write_json(run.path/'raw/network_report.json',reports)
        run.flush()
        print(json.dumps({'run_id':run.run_id,'status':'passed','processed_root':str(processed),'source_snapshot':str(snapshot)},ensure_ascii=False),flush=True)
    return run.path
