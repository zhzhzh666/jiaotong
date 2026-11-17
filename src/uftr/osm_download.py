"""Bounded, provenance-preserving OSM official map API fallback for unavailable Overpass."""
from __future__ import annotations

from datetime import datetime,timezone
from pathlib import Path
import time
import xml.etree.ElementTree as E

import geopandas as gpd
import osmnx as ox
import requests
from shapely.geometry import box,shape,mapping

from .archive import file_hash,now,write_json

USER_AGENT='UFTR/0.1 (academic Shenzhen urban flood transportation resilience study; OSMnx 2.1.2)'
EXCLUDED={'abandoned','bridleway','bus_guideway','construction','corridor','cycleway','elevator','escalator','footway','no','path','pedestrian','planned','platform','proposed','raceway','razed','rest_area','service','services','steps','track'}
EXCLUDED_SERVICE={'alley','driveway','emergency_access','parking','parking_aisle','private'}
TAGS=['layer','lanes:forward','lanes:backward','maxspeed:forward','maxspeed:backward','access','motor_vehicle','motorcar','oneway','junction','highway','lanes','maxspeed','bridge','tunnel','name','ref']


def drive_way(tags):
    return bool(tags.get('highway')) and tags['highway'] not in EXCLUDED and tags.get('area')!='yes' and tags.get('access')!='private' and tags.get('motor_vehicle')!='no' and tags.get('motorcar')!='no' and tags.get('service') not in EXCLUDED_SERVICE


def fetch(url,path, *, params=None,timeout=60):
    response=requests.get(url,params=params,timeout=(15,timeout),headers={'User-Agent':USER_AGENT})
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(response.content)  # preserve failures too
    meta={'url':response.url,'accessed_at':now(),'http_status':response.status_code,'bytes':len(response.content),'sha256':file_hash(path)}
    write_json(path.with_suffix(path.suffix+'.source.json'),meta)
    response.raise_for_status()
    return response


def boundary_from_nominatim(directory,settings):
    path=directory/'nanshan_nominatim.json'
    payload=fetch(settings['boundary_url'],path,params={'q':settings['boundary_query'],'format':'jsonv2','polygon_geojson':1,'limit':5}).json()
    match=[r for r in payload if r.get('osm_type')=='relation' and int(r.get('osm_id',0))==settings['expected_relation_id'] and r.get('type')=='administrative']
    if len(match)!=1:
        raise ValueError('expected unique Nanshan administrative relation missing')
    r=match[0]; polygon=shape(r['geojson'])
    if not polygon.is_valid or polygon.geom_type not in {'Polygon','MultiPolygon'}:
        raise ValueError('invalid district boundary')
    write_json(directory/'nanshan_boundary.geojson',{'type':'FeatureCollection','features':[{'type':'Feature','properties':{'osm_relation_id':r['osm_id'],'display_name':r['display_name'],'licence':r['licence']},'geometry':mapping(polygon)}]})
    return polygon


def download_tiles(polygon,directory,settings,log=print):
    """Only query intersecting cells; split API node-limit errors, never fabricate data."""
    directory.mkdir(parents=True,exist_ok=False)
    buffer=gpd.GeoSeries([polygon],crs=4326).to_crs(settings['projected_crs']).buffer(settings['buffer_m']).to_crs(4326).iloc[0]
    left,bottom,right,top=buffer.bounds
    step=settings['tile_degrees']
    queue=[]; x=left
    while x<right:
        y=bottom
        while y<top:
            cell=(x,y,min(x+step,right),min(y+step,top))
            if buffer.intersects(box(*cell)): queue.append(cell)
            y+=step
        x+=step
    records=[]; requests_count=0
    while queue:
        bounds=queue.pop(0)
        if requests_count>=settings['max_requests']:
            raise RuntimeError('configured official API request budget exceeded')
        path=directory/f'tile-{requests_count:04d}.osm'
        requests_count+=1
        time.sleep(settings['request_pause_s'])
        log(f'OSM tile {requests_count}, remaining {len(queue)}, bbox {bounds}')
        try:
            fetch(settings['map_url'],path,params={'bbox':','.join(f'{n:.7f}' for n in bounds)},timeout=settings['timeout_s'])
        except requests.HTTPError as exc:
            if exc.response.status_code==400 and ('too many nodes' in exc.response.text.lower() or '50,000' in exc.response.text.lower()):
                a,b,c,d=bounds
                if min(c-a,d-b)<settings['minimum_tile_degrees']:
                    raise
                for cell in [(a,b,(a+c)/2,(b+d)/2),((a+c)/2,b,c,(b+d)/2),(a,(b+d)/2,(a+c)/2,d),((a+c)/2,(b+d)/2,c,d)]:
                    if buffer.intersects(box(*cell)): queue.append(cell)
                continue
            raise
        xml=E.parse(path).getroot()
        if xml.tag!='osm': raise ValueError('not an OSM XML response')
        records.append({'path':path.name,'bbox':bounds,'sha256':file_hash(path)})
    write_json(directory/'download_manifest.json',{'source':'OSM official map API','license':'ODbL 1.0','attribution':'© OpenStreetMap contributors','copyright_url':'https://www.openstreetmap.org/copyright','downloaded_at':now(),'requests':requests_count,'tiles':records,'network_filter':'OSMnx 2.1.2 drive equivalent; exclude service/private/non-motor highways','snapshot_note':'Live map API tiles acquired over a time interval, not a historical atomic snapshot'})
    return directory


def graph_from_tiles(directory,polygon):
    """Merge real XML primitives then use public OSMnx XML parser; retain all components."""
    nodes={}; ways={}; versions={}; duplicate_count=0
    manifest=__import__('json').loads((directory/'download_manifest.json').read_text(encoding='utf-8'))
    for item in manifest['tiles']:
        path=directory/item['path']
        if file_hash(path)!=item['sha256']: raise ValueError('OSM tile checksum changed')
        for element in E.parse(path).getroot():
            if element.tag not in {'node','way'}: continue
            identity=(element.tag,int(element.attrib['id']))
            version=element.attrib.get('version')
            if identity in versions:
                duplicate_count+=1
                if versions[identity]!=version: raise ValueError('OSM versions changed during live download; new snapshot required')
            versions[identity]=version
            if element.tag=='node': nodes[identity[1]]=element
            elif drive_way({t.attrib['k']:t.attrib['v'] for t in element.findall('tag')}): ways[identity[1]]=element
    needed={int(nd.attrib['ref']) for w in ways.values() for nd in w.findall('nd')}
    if needed-set(nodes): raise ValueError('OSM way nodes missing')
    xml=E.Element('osm',version='0.6',generator='UFTR official-map-api motor-road filter')
    for n in sorted(needed): xml.append(nodes[n])
    for w in sorted(ways): xml.append(ways[w])
    path=directory/'drive_filtered.osm'; E.ElementTree(xml).write(path,encoding='utf-8',xml_declaration=True)
    old_tags=ox.settings.useful_tags_way.copy()
    try:
        ox.settings.useful_tags_way=list(dict.fromkeys(old_tags+TAGS))
        g=ox.graph_from_xml(path,bidirectional=False,simplify=False,retain_all=True)
    finally:
        ox.settings.useful_tags_way=old_tags
    # Simplify buffered network first to preserve real junctions, then truncate study region.
    g=ox.simplify_graph(g,edge_attrs_differ=['osmid','reversed',*TAGS],remove_rings=False)
    g=ox.truncate.truncate_graph_polygon(g,polygon,truncate_by_edge=True)
    for u,v,k,d in g.edges(keys=True,data=True):
        osm=d['osmid']
        if isinstance(osm,list): raise ValueError('OSM ID merged unexpectedly')
        d['oneway_osm_raw']={t.attrib['k']:t.attrib['v'] for t in ways[int(osm)].findall('tag')}.get('oneway','missing')
    g.graph['source_method']='Official OSM map API fallback + OSMnx public XML parser'
    g.graph['data_license']='ODbL-1.0; © OpenStreetMap contributors'
    g.graph['duplicate_primitives_deduplicated']=duplicate_count
    return g
