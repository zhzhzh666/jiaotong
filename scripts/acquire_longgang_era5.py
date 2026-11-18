"""Acquire public ERA5 precipitation; pin raw replies, query and validation."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import traceback
import uuid
import geopandas as gpd
import numpy as np
import requests
import yaml
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]


def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def acquire(config):
    cfg = yaml.safe_load(config.read_text(encoding='utf-8'))
    if cfg['region'] != 'longgang' or cfg['include_dapeng'] is not False:
        raise ValueError('wrong scope')
    rid = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_era5_'+uuid.uuid4().hex[:8]
    out = ROOT/cfg['rainfall_output_root']/rid
    out.mkdir(parents=True, exist_ok=False)
    print('OUTPUT '+str(out), flush=True)
    write(out/'status.json', {'status':'running'})
    try:
        od = ROOT/cfg['od_package']
        boundary = gpd.read_file(od/'study_boundary.geojson').to_crs(cfg['domain']['crs'])
        if boundary.include_dapeng.any():
            raise ValueError('Dapeng included')
        buffer_m = max(cfg['domain']['buffer_m'], cfg['domain'].get('buffer_verification_m',0))
        xmin,ymin,xmax,ymax = boundary.geometry.union_all().buffer(buffer_m).bounds
        # All closest ERA5 centers potentially selected by the model rectangle.
        tr = Transformer.from_crs(cfg['domain']['crs'], 4326, always_xy=True)
        lon,lat = tr.transform([xmin,xmin,xmax,xmax], [ymin,ymax,ymin,ymax])
        grid = cfg['rainfall']['grid_degrees']
        lons = np.arange(round(min(lon)/grid), round(max(lon)/grid)+1)*grid
        lats = np.arange(round(min(lat)/grid), round(max(lat)/grid)+1)*grid
        points = [(float(a),float(b)) for a in lats for b in lons]
        r = cfg['rainfall']
        start = datetime.fromisoformat(r['simulation_start'])
        end = datetime.fromisoformat(r['simulation_end'])
        params = {'latitude':','.join(str(a) for a,b in points),
                  'longitude':','.join(str(b) for a,b in points),
                  'start_date':start.date().isoformat(), 'end_date':end.date().isoformat(),
                  'hourly':'precipitation', 'models':r['model'], 'timezone':r['timezone'],
                  'cell_selection':r['cell_selection']}
        write(out/'request.json', {'endpoint':r['endpoint'], 'params':params,
              'requested_points_lat_lon':points, 'configuration_sha256':sha(config),
              'simulation_start':start.isoformat(), 'simulation_end':end.isoformat()})
        response = requests.get(r['endpoint'], params=params, timeout=60)
        (out/'response.json').write_bytes(response.content)
        write(out/'response_metadata.json', {'url':response.url,'status_code':response.status_code,
              'retrieved_utc':datetime.now(timezone.utc).isoformat(),
              'content_type':response.headers.get('Content-Type'), 'sha256':sha(out/'response.json')})
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict): data = [data]
        if len(data) != len(points): raise ValueError('wrong response count')
        records=[]; rain=[]; time_reference=None
        for j,(item,(a,b)) in enumerate(zip(data,points)):
            if item['utc_offset_seconds'] != 28800 or item['hourly_units']['precipitation'] != 'mm':
                raise ValueError('wrong time/units')
            if not np.isclose(item['latitude'],a,atol=1e-5) or not np.isclose(item['longitude'],b,atol=1e-5):
                raise ValueError('returned ERA5 grid center differs from requested center')
            times = np.array(item['hourly']['time'], dtype='datetime64[m]')
            values = np.asarray(item['hourly']['precipitation'],float)
            # Label t denotes precipitation on (t-1hour,t]. Start excluded, end included.
            keep = (times>np.datetime64(start.replace(tzinfo=None))) & (times<=np.datetime64(end.replace(tzinfo=None)))
            times,values=times[keep],values[keep]
            if len(times)!=(end-start).total_seconds()/3600 or not np.all(np.diff(times)==np.timedelta64(60,'m')):
                raise ValueError('incomplete hourly time grid')
            if not np.isfinite(values).all() or (values<0).any(): raise ValueError('invalid precipitation')
            if time_reference is None: time_reference=times
            if not np.array_equal(times,time_reference): raise ValueError('unaligned grid times')
            rain.append(values)
            records.append({'rain_grid_id':j,'latitude':a,'longitude':b,
                            'total_mm':float(values.sum()),'max_hour_mm':float(values.max()),
                            'record_count':len(times),'source':'ERA5_reanalysis_via_Open_Meteo_not_station'})
        np.savez_compressed(out/'hourly_rainfall.npz',time_end_local=time_reference.astype(str),
                            precipitation_mm=np.array(rain).T,
                            latitude=np.array([a for a,b in points]),longitude=np.array([b for a,b in points]))
        write(out/'grid_metadata.json',records)
        write(out/'attribution.json',{'attribution':'Weather data by Open-Meteo.com; Copernicus Climate Change Service / ECMWF ERA5',
              'provider_url':'https://open-meteo.com/', 'license':'CC BY 4.0',
              'license_url':'https://creativecommons.org/licenses/by/4.0/',
              'provider_licence_url':'https://open-meteo.com/en/licence',
              'changes':'Raw response unchanged; selected complete simulation intervals and packed values into NPZ.',
              'classification':'reanalysis_not_gauge_observation'})
        write(out/'status.json',{'status':'complete','grid_count':len(points),'hours':len(time_reference)})
        write(out/'manifest.json',{'run_id':rid,'inputs':[{'path':config.relative_to(ROOT).as_posix(),'sha256':sha(config)},
              {'path':Path(__file__).relative_to(ROOT).as_posix(),'sha256':sha(__file__)},
              {'path':(od/'study_boundary.geojson').relative_to(ROOT).as_posix(),'sha256':sha(od/'study_boundary.geojson')}],
              'outputs':[{'path':p.relative_to(out).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
              for p in sorted(out.iterdir()) if p.is_file()]})
        print(json.dumps({'path':str(out),'grids':records},ensure_ascii=False),flush=True)
        return out
    except Exception:
        write(out/'status.json',{'status':'failed','traceback':traceback.format_exc()})
        raise


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',default='configs/longgang_era5_surface.yaml')
    acquire((ROOT/parser.parse_args().config).resolve())
