"""Phase 02 GIS cleaning, conservative surface-road matching and data quality.

Synthetic risk locations are scenario inputs, never observed flood events.
"""
from pathlib import Path
import json
import xml.etree.ElementTree as E
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.merge import merge
from rasterio.mask import mask
from shapely.geometry import Point, Polygon, mapping
from shapely import normalize
from .archive import file_hash


def clip_rasters(paths, polygon, output):
    """Retain native raster values/grid: never interpolate population counts."""
    from contextlib import ExitStack
    with ExitStack() as stack:
        sources = [stack.enter_context(rasterio.open(p)) for p in paths]
        if any(s.crs != 'EPSG:4326' for s in sources):
            raise ValueError('source raster CRS must be EPSG:4326')
        from rasterio.windows import from_bounds, Window, bounds
        window=from_bounds(*polygon.bounds,transform=sources[0].transform)
        left,top=int(np.floor(window.col_off)),int(np.floor(window.row_off))
        right,bottom=int(np.ceil(window.col_off+window.width)),int(np.ceil(window.row_off+window.height))
        aligned=bounds(Window(left,top,right-left,bottom-top),sources[0].transform)
        values, transform = merge(sources, bounds=aligned, nodata=-9999, dtype='float32')
        profile = sources[0].profile.copy()
        profile.update(driver='GTiff', width=values.shape[2], height=values.shape[1],
                       transform=transform, dtype='float32', nodata=-9999,
                       compress='deflate', count=1)
        # Use an in-memory mosaic then polygon mask on native pixel centres.
        from rasterio.io import MemoryFile
        with MemoryFile() as mem:
            with mem.open(**profile) as mosaic: mosaic.write(values)
            with mem.open() as mosaic:
                clipped, tx = mask(mosaic, [mapping(polygon)], crop=True, all_touched=False,
                                   nodata=-9999)
        profile.update(width=clipped.shape[2], height=clipped.shape[1], transform=tx)
        output.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output, 'w', **profile) as dst: dst.write(clipped)
    good = clipped[0][np.isfinite(clipped[0]) & (clipped[0] != -9999)]
    if not len(good): raise ValueError('no valid raster cells in study boundary')
    return {'crs': 'EPSG:4326', 'resolution_degrees': [abs(tx.a), abs(tx.e)],
            'valid_cells': int(len(good)), 'min': float(good.min()), 'max': float(good.max()),
            'sum_native_cells': float(good.sum(dtype=np.float64)),
            'boundary_rule': 'Native cells whose centres fall inside polygon; no fractional-cell redistribution',
            'nodata': -9999}


def normalize_points(frame, polygon, *, id_col='point_id'):
    if frame.crs is None: raise ValueError('point CRS required; do not assume WGS84 or GCJ-02')
    frame = frame.to_crs(4326).copy()
    if not frame.geometry.geom_type.eq('Point').all(): raise ValueError('only Point geometry accepted')
    if frame.geometry.is_empty.any() or (~frame.geometry.is_valid).any(): raise ValueError('invalid point')
    if frame[id_col].isna().any(): raise ValueError('point identifier required')
    frame = frame.drop_duplicates(subset=id_col)
    if frame.geometry.x.abs().gt(180).any() or frame.geometry.y.abs().gt(90).any():
        raise ValueError('invalid WGS84 coordinate bounds')
    return frame[frame.geometry.map(polygon.covers)].reset_index(drop=True)


def read_osm_facilities(snapshot, polygon):
    """Reuse unfiltered original OSM XML; no additional requests or geocoding."""
    coords, objects = {}, {}
    manifest = json.loads((snapshot/'download_manifest.json').read_text(encoding='utf-8'))
    for item in manifest['tiles']:
        path = snapshot/item['path']
        if file_hash(path) != item['sha256']: raise ValueError('OSM source checksum mismatch')
        for element in E.parse(path).getroot():
            if element.tag == 'node':
                coords[int(element.attrib['id'])] = (float(element.attrib['lon']), float(element.attrib['lat']))
            if element.tag not in {'node','way'}: continue
            tags = {t.attrib['k']: t.attrib['v'] for t in element.findall('tag')}
            category = None
            if tags.get('amenity') == 'hospital' or tags.get('healthcare') == 'hospital': category = 'hospital'
            elif tags.get('amenity') == 'fire_station': category = 'fire_station'
            elif tags.get('emergency') == 'shelter' or (tags.get('amenity') == 'shelter' and tags.get('shelter_type') in {'emergency','disaster'}): category = 'emergency_shelter'
            elif tags.get('emergency') == 'assembly_point': category = 'assembly_point'
            if category:
                objects[(element.tag, int(element.attrib['id']))] = (tags, category,
                    [int(nd.attrib['ref']) for nd in element.findall('nd')])
    rows=[]; skipped=[]
    for (kind, osm_id),(tags, category, refs) in sorted(objects.items()):
        if kind == 'node':
            geom = Point(coords[osm_id]); method='OSM node'
        elif len(refs) >= 4 and refs[0] == refs[-1] and all(n in coords for n in refs):
            area = Polygon([coords[n] for n in refs])
            if not area.is_valid or area.is_empty:
                skipped.append(f'{kind}/{osm_id}'); continue
            geom=area.representative_point(); method='polygon interior point; entrance unknown'
        else:
            skipped.append(f'{kind}/{osm_id}'); continue
        if not polygon.covers(geom): continue
        rows.append({'poi_id':f'osm_{kind}_{osm_id}', 'name':tags.get('name',''),
                     'category':category, 'osm_type':kind, 'osm_id':osm_id,
                     'source_kind':'real_osm_snapshot', 'location_method':method,
                     'entrance_verified':False, 'geometry':geom})
    cols=['poi_id','name','category','osm_type','osm_id','source_kind','location_method','entrance_verified','geometry']
    frame=gpd.GeoDataFrame(rows,columns=cols,geometry='geometry',crs=4326)
    return frame, {'counts':frame.category.value_counts().to_dict(), 'skipped_unsupported_geometries':skipped,
                   'coverage':'Incomplete OSM inventory, not official complete list; node/way duplicates across types or nearby entrances not merged without evidence. Assembly points are not designated shelters.'}


def read_gsod(path, station):
    source=pd.read_csv(path,dtype={'STATION':str,'PRCP_ATTRIBUTES':str})
    if set(source.STATION) != {station}: raise ValueError('unexpected rainfall station')
    dates=pd.to_datetime(source.DATE,errors='raise')
    if dates.duplicated().any(): raise ValueError('duplicate station date')
    rain=pd.to_numeric(source.PRCP,errors='raise')
    if rain.lt(0).any(): raise ValueError('negative rainfall')
    flags=source.PRCP_ATTRIBUTES.fillna('').str.strip()
    valid=rain.ne(99.99) & flags.isin(list('ABCDEFG'))
    frame=pd.DataFrame({'station_id':station,'date_gmt':dates.dt.strftime('%Y-%m-%d'),
        'precipitation_mm':(rain*25.4).where(valid), 'raw_precipitation_inches':rain,
        'source_flag':flags, 'valid':valid,'resolution':'daily report; accumulation may include previous day',
        'source_kind':'observed_station_daily','is_nanshan_areal_mean':False,
        'latitude':source.LATITUDE,'longitude':source.LONGITUDE})
    return frame.sort_values('date_gmt').reset_index(drop=True)


def _present(value):
    return str(value).lower() not in {'','nan','none','no','false','0','0.0'}


def surface_reason(row):
    if _present(row.get('bridge','')): return 'bridge; surface point cannot identify elevated carriageway'
    if _present(row.get('tunnel','')): return 'tunnel; separate flood exposure required'
    value=row.get('layer',0)
    try:
        if pd.notna(value) and float(value) != 0: return 'nonzero layer; separate vertical exposure required'
    except (ValueError,TypeError): return 'unknown complex layer'
    return ''


def match_surface_roads(points, edges, settings):
    """Return all nearby candidates, exclusions and conservative geometric choices.

    Selection does not declare a road flooded. Reverse arcs sharing geometry form
    one physical group; ambiguous parallel roads remain separate candidates.
    """
    p=points.to_crs(32650); e=edges.to_crs(32650).reset_index(drop=True).copy()
    if not e.edge_id.is_unique: raise ValueError('edge_id must be unique')
    e['exclusion_reason']=e.apply(surface_reason,axis=1)
    e['physical_group']=[normalize(g).wkb_hex for g in e.geometry]
    rows=[]
    for _,point in p.iterrows():
        ids=e.sindex.query(point.geometry.buffer(settings['search_radius_m']),predicate='intersects')
        candidates=e.iloc[ids].copy()
        candidates['distance_m']=candidates.geometry.distance(point.geometry)
        candidates=candidates[candidates.distance_m<=settings['search_radius_m']]
        eligible=candidates[candidates.exclusion_reason.eq('')]
        grouped=eligible.groupby('physical_group').distance_m.min().sort_values()
        best=grouped.index[0] if len(grouped) and grouped.iloc[0]<=settings['max_match_distance_m'] else None
        gap=float(grouped.iloc[1]-grouped.iloc[0]) if len(grouped)>1 else None
        confidence='low'
        if best is not None:
            nearest=eligible[eligible.physical_group.eq(best)].iloc[0]
            ramp=str(nearest.get('road_class','')).endswith('_link')
            if grouped.iloc[0]<=settings['high_distance_m'] and (gap is None or gap>=settings['high_gap_m']) and not ramp:
                confidence='high'
            elif grouped.iloc[0]<=settings['medium_distance_m'] and (gap is None or gap>=settings['medium_gap_m']):confidence='medium'
        if not len(candidates):
            rows.append({'point_id':point.point_id,'edge_id':None,'distance_m':None,'selected_geometry':False,
                         'match_confidence':'unmatched','exclusion_reason':'no road in search radius',
                         'ambiguity_gap_m':None,'source_kind':point.source_kind,'flood_observation':'not established'})
        for _,edge in candidates.sort_values(['distance_m','edge_id']).iterrows():
            selected=best is not None and edge.physical_group==best and not edge.exclusion_reason
            rows.append({'point_id':point.point_id,'edge_id':edge.edge_id,'distance_m':float(edge.distance_m),
                'selected_geometry':bool(selected),'match_confidence':confidence if selected else 'candidate_only',
                'exclusion_reason':edge.exclusion_reason,'ambiguity_gap_m':gap,
                'source_kind':point.source_kind,'flood_observation':'not established'})
    return pd.DataFrame(rows,columns=['point_id','edge_id','distance_m','selected_geometry','match_confidence',
                                      'exclusion_reason','ambiguity_gap_m','source_kind','flood_observation'])


def synthetic_risk_points(edges, polygon, dem_path, settings, seed):
    """Cluster around low-DSM surface roads, then jitter; no historical claim."""
    surface=edges[edges.apply(surface_reason,axis=1).eq('')].to_crs(32650).copy()
    surface['canon']=[normalize(g).wkb_hex for g in surface.geometry]
    surface=surface.drop_duplicates('canon')
    centres=surface.geometry.interpolate(.5,normalized=True)
    centres=gpd.GeoSeries(centres,crs=32650).to_crs(4326)
    with rasterio.open(dem_path) as src:
        heights=np.array([v[0] for v in src.sample([(g.x,g.y) for g in centres])])
        valid=np.isfinite(heights)&(heights!=src.nodata)&(heights>=0)&(heights<=settings['max_dsm_m'])
        candidates=np.flatnonzero(valid & centres.map(polygon.covers).to_numpy())
        if len(candidates)<settings['clusters']: raise ValueError('insufficient valid low-elevation surface-road seeds')
        rng=np.random.default_rng(seed)
        weights=np.exp(-heights[candidates]/settings['elevation_scale_m']);weights/=weights.sum()
        chosen=rng.choice(candidates,size=settings['clusters'],replace=False,p=weights)
        seed_points=gpd.GeoSeries(centres.iloc[chosen].to_list(),crs=4326).to_crs(32650)
        rows=[]
        for attempt in range(settings['count']*100):
            cluster=len(rows)%settings['clusters']; centre=seed_points.iloc[cluster]
            xy=np.array([centre.x,centre.y])+rng.normal(0,settings['cluster_sd_m'],2)
            geom=gpd.GeoSeries([Point(xy)],crs=32650).to_crs(4326).iloc[0]
            if not polygon.covers(geom):continue
            z=float(next(src.sample([(geom.x,geom.y)]))[0])
            if not np.isfinite(z) or z==src.nodata or z<0 or z>settings['max_dsm_m']:continue
            rows.append({'point_id':f'synthetic_risk_{len(rows):04d}','cluster_id':cluster,
                         'source_kind':'synthetic','dsm_m':z,'observed_depth_m':None,
                         'event_date':None,'method':'low-DSM road seeds + Gaussian clusters; not hydrodynamic',
                         'geometry':geom})
            if len(rows)==settings['count']:break
        if len(rows)!=settings['count']: raise ValueError('risk generation acceptance budget exceeded')
    return gpd.GeoDataFrame(rows,geometry='geometry',crs=4326)
