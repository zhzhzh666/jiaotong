"""Road-grid pond proxies for Longgang. No calibrated hydraulics or water levels."""
import math
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.windows import Window
from pyproj import Transformer
from shapely.geometry import LineString
from .longgang_od import direction_and_speed


def rain_profile(duration_h, dt_h, settings):
    if dt_h <= 0 or duration_h <= 0 or not np.isclose(duration_h/dt_h, round(duration_h/dt_h)):
        raise ValueError('invalid time grid')
    times=np.arange(round(duration_h/dt_h))*dt_h
    mid=times+dt_h/2
    peaks, widths, factors=(np.asarray(settings[k],float) for k in ['peaks_hour','peak_width_hours','peak_weights'])
    if len(peaks)!=len(widths) or len(peaks)!=len(factors) or (widths<=0).any() or (factors<0).any():
        raise ValueError('invalid rainfall peaks')
    a,b=settings['event_start_hour'],settings['event_end_hour']
    if not 0 <= a < b <= duration_h or not np.isclose(a/dt_h,round(a/dt_h)) or not np.isclose(b/dt_h,round(b/dt_h)):
        raise ValueError('event boundaries must align with time grid')
    weights=sum(w*np.exp(-.5*((mid-p)/sd)**2) for w,p,sd in zip(factors,peaks,widths))
    weights[(mid<a)|(mid>=b)]=0
    if not weights.sum()>0:raise ValueError('empty storm')
    weights/=weights.sum()
    records=[]
    for scenario,total in settings['total_mm'].items():
        if not np.isfinite(total) or total<0:raise ValueError('invalid rain total')
        rain=weights*total
        records.append(pd.DataFrame({'scenario':scenario,'interval':np.arange(len(times)),
            'start_h':times,'end_h':times+dt_h,'rain_mm_interval':rain,'intensity_mm_h':rain/dt_h,
            'cumulative_mm':rain.cumsum(),'observed':False}))
    return pd.concat(records,ignore_index=True)


def rain_factors(xy, settings, seed):
    """Finite Fourier approximation of a Gaussian correlated field, site mean 1.

    Normalization is over road-proxy locations, NOT district areal rainfall.
    """
    xy=np.asarray(xy,float)
    if xy.ndim!=2 or xy.shape[1]!=2 or not len(xy) or not np.isfinite(xy).all():raise ValueError('invalid sites')
    length=settings['spatial_correlation_m'];sd=settings['spatial_log_sd'];m=settings['random_fourier_modes']
    if length<=0 or sd<0 or type(m)!=int or m<1:raise ValueError('invalid spatial rainfall settings')
    rng=np.random.default_rng(seed)
    frequencies=rng.normal(size=(2,m))/length
    phase=rng.uniform(0,2*np.pi,m)
    coefficients=rng.normal(size=m)
    field=np.sqrt(2/m)*np.cos((xy-xy.mean(0))@frequencies+phase)@coefficients
    factor=np.exp(np.clip(sd*field,-10,10))
    return factor/factor.mean()


def line_parts(geometry):
    if geometry.is_empty:return []
    if geometry.geom_type=='LineString':return [geometry]
    if hasattr(geometry,'geoms'):
        return [p for g in geometry.geoms for p in line_parts(g)]
    return []


def make_road_sites(roads,boundary,dsm_path,spatial,network_settings):
    """Every accepted ground source line is sampled, with missing coverage explicit."""
    metric=roads.to_crs(32650)
    poly=gpd.GeoSeries([boundary],crs=4326).to_crs(32650).iloc[0]
    selected=np.flatnonzero(roads.geometry.intersects(boundary).to_numpy())
    rows=[];samples=[]
    for pos in selected:
        row=roads.iloc[pos];parsed=direction_and_speed(row,network_settings)
        if parsed is None:continue
        _,_,_,grade=parsed
        clipped=metric.geometry.iloc[pos].intersection(poly)
        parts=line_parts(clipped)
        if not parts or sum(p.length for p in parts)<=1e-6:continue
        ground=grade[0] in {'0','0.0'} and not grade[1] and not grade[2]
        rows.append({'source_feature_position':int(pos),'osm_id':str(row.osm_id),
            'ground_model_eligible':ground,'grade':str(grade),'inside_length_m':sum(p.length for p in parts),
            'status':'pending_dsm' if ground else 'elevated_tunnel_or_nonzero_layer_not_modelled',
            'geometry':clipped})
        if ground:
            for part in parts:
                distances=np.linspace(0,part.length,max(2,math.ceil(part.length/spatial['road_sample_spacing_m'])+1))
                for point in (part.interpolate(d) for d in distances):
                    samples.append((int(pos),point.x,point.y))
    if not samples:raise ValueError('no ground road samples')
    sample=pd.DataFrame(samples,columns=['source_feature_position','x_m','y_m']).drop_duplicates()
    to_geo=Transformer.from_crs(32650,4326,always_xy=True)
    xx,yy=to_geo.transform(sample.x_m.to_numpy(),sample.y_m.to_numpy())
    with rasterio.open(dsm_path) as src:
        if src.crs.to_epsg()!=4326:raise ValueError('expected WGS84 DSM')
        heights=np.ma.asarray(list(src.sample(zip(xx,yy),masked=True)))[:,0]
        sample['dsm_m']=np.ma.filled(heights,np.nan)
        sample['valid_dsm']=np.isfinite(sample.dsm_m)&(sample.dsm_m!=src.nodata)
        size=spatial['cell_size_m']
        sample['grid_x']=np.floor(sample.x_m/size).astype(int)
        sample['grid_y']=np.floor(sample.y_m/size).astype(int)
        valid=sample[sample.valid_dsm].copy()
        if valid.empty:raise ValueError('no valid DSM coverage')
        # Pick an actual road-sample position with minimum DSM in each grid cell.
        chosen=valid.sort_values(['grid_x','grid_y','dsm_m','x_m','y_m']).drop_duplicates(['grid_x','grid_y']).copy()
        chosen['site_id']=['LGF_%d_%d'%(a,b) for a,b in zip(chosen.grid_x,chosen.grid_y)]
        chosen=chosen.sort_values('site_id').reset_index(drop=True)
        medians=[];radius=spatial['local_dsm_radius_pixels']
        for r in chosen.itertuples():
            x,y=to_geo.transform(r.x_m,r.y_m);rr,cc=src.index(x,y)
            values=src.read(1,window=Window(cc-radius,rr-radius,2*radius+1,2*radius+1),boundless=True,masked=True)
            values=values.compressed();values=values[np.isfinite(values)]
            medians.append(float(np.median(values)) if len(values) else r.dsm_m)
    chosen['local_median_dsm_m']=medians
    chosen['local_low_score']=np.clip((chosen.local_median_dsm_m-chosen.dsm_m)/spatial['local_low_scale_m'],0,1)
    chosen['source_kind']='synthetic_low_DSM_road_grid_proxy'
    chosen['observed']=False
    sites=gpd.GeoDataFrame(chosen,geometry=gpd.points_from_xy(chosen.x_m,chosen.y_m),crs=32650)
    sample=sample.merge(sites[['grid_x','grid_y','site_id']],on=['grid_x','grid_y'],how='left')
    sample.loc[~sample.valid_dsm,'site_id']=None
    links=sample.dropna(subset=['site_id'])[['source_feature_position','site_id']].drop_duplicates()
    features=gpd.GeoDataFrame(rows,crs=32650)
    totals=sample.groupby('source_feature_position').size()
    valid_counts=sample[sample.valid_dsm].groupby('source_feature_position').size()
    features['sample_count']=features.source_feature_position.map(totals).fillna(0).astype(int)
    features['valid_sample_count']=features.source_feature_position.map(valid_counts).fillna(0).astype(int)
    features['status']=np.select([~features.ground_model_eligible,features.valid_sample_count.eq(0),features.valid_sample_count.lt(features.sample_count)],
        ['elevated_tunnel_or_nonzero_layer_not_modelled','missing_dsm_not_modelled','partial_dsm_coverage'],default='modelled_ground_samples')
    return sites,features,links,sample


def aggregate_road_depth(depth,sites,features,links):
    """Maximum linked proxy depth; unmodelled features remain NaN, never dry zero."""
    si={v:i for i,v in enumerate(sites.site_id)};fi={v:i for i,v in enumerate(features.source_feature_position)}
    result=np.full((depth.shape[0],len(features)),np.nan)
    for fid,frame in links.groupby('source_feature_position'):
        result[:,fi[fid]]=np.max(depth[:,[si[s] for s in frame.site_id]],axis=1)
    return result


def graph_road_identities(graphml,roads,boundary,selected_positions):
    """Read exact IDs from the frozen inferred OD graph; do not invent IDs."""
    names={};rows=[];scope={};selected=set(selected_positions)
    for _,element in ET.iterparse(graphml,events=['end']):
        tag=element.tag.rsplit('}',1)[-1]
        if tag=='key':names[element.get('id')]=element.get('attr.name')
        elif tag=='edge':
            values={names.get(d.get('key')):d.text for d in element if d.tag.rsplit('}',1)[-1]=='data'}
            pos=int(values['source_feature_position']);segment=int(values['segment_index'])
            if pos in selected:
                key=(pos,segment)
                if key not in scope:
                    coords=list(roads.geometry.iloc[pos].coords)
                    geometry=LineString([coords[segment],coords[segment+1]])
                    scope[key]=(geometry.intersects(boundary),not boundary.covers(geometry))
                intersects,crossing=scope[key]
                if intersects:
                    rows.append({'edge_id':values['edge_id'],'u':int(element.get('source')),'v':int(element.get('target')),
                        'key':int(element.get('id')),'source_feature_position':pos,'segment_index':segment,
                        'length_m':float(values['length_m']),'crosses_study_boundary':crossing,
                        'identity_status':'exact_ID_from_inferred_OD_graph_not_authoritative_OSM'})
            element.clear()
        elif tag=='node':element.clear()
    result=pd.DataFrame(rows)
    if result.empty or not result.edge_id.is_unique:raise ValueError('missing/nonunique graph mapping')
    return result
