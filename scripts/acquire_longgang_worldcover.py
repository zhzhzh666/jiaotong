"""Archive unresampled WorldCover window crops and derived class fractions."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import math
import shutil
import struct
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import rasterio
from rasterio.warp import transform_bounds, reproject, Resampling
from rasterio.windows import from_bounds, Window
from rasterio.transform import Affine
import requests
import yaml
from acquire_longgang_era5 import ROOT, sha, write


def cached_window(url, path, model_bounds, model_crs):
    """Fetch only native-resolution TIFF blocks, validating every byte range.

    The local backing file is explicitly incomplete outside the selected
    window. It is never labelled an original complete remote TIFF.
    """
    def get_bytes(start, end):
        last_error = None
        for attempt in range(3):
            try:
                response = requests.get(url, headers={'Range': f'bytes={start}-{end}'}, timeout=(15, 30))
                response.raise_for_status()
                crange = response.headers.get('Content-Range', '')
                if response.status_code != 206 or not crange.startswith(f'bytes {start}-{end}/'):
                    raise ValueError('incorrect range response')
                if len(response.content) != end-start+1: raise ValueError('truncated range response')
                return response.content, int(crange.split('/')[-1]), response.headers.get('ETag')
            except (requests.RequestException, ValueError) as error:
                last_error = error
        raise last_error
    header, total, etag = get_bytes(0, 65535)
    endian = '<' if header[:2] == b'II' else '>'
    if struct.unpack_from(endian+'H', header, 2)[0] != 42:
        raise ValueError('only classic TIFF block indexing supported')
    ifd = struct.unpack_from(endian+'I', header, 4)[0]
    count = struct.unpack_from(endian+'H', header, ifd)[0]
    tags = {}
    for j in range(count):
        tag, kind, size, value = struct.unpack_from(endian+'HHII', header, ifd+2+j*12)
        if tag not in [322, 323, 324, 325]: continue
        code, width = {3: ('H', 2), 4: ('I', 4)}[kind]
        if size*width <= 4:
            array = struct.unpack_from(endian+code*size, header, ifd+2+j*12+8)
        else:
            if value+size*width > len(header): raise ValueError('TIFF index exceeds cached header')
            array = struct.unpack_from(endian+code*size, header, value)
        tags[tag] = array
    with path.open('wb') as stream:
        stream.write(header); stream.truncate(total)
    with rasterio.open(path) as src:
        b = transform_bounds(model_crs, src.crs, *model_bounds, densify_pts=21)
        window = from_bounds(*b, src.transform).round_offsets().round_lengths()
        window = Window(window.col_off-2, window.row_off-2, window.width+4, window.height+4)
        window = window.intersection(Window(0, 0, src.width, src.height))
        bw, bh = tags[322][0], tags[323][0]; columns = math.ceil(src.width/bw)
        ids = [r*columns+c for r in range(int(window.row_off)//bh, math.ceil((window.row_off+window.height)/bh))
               for c in range(int(window.col_off)//bw, math.ceil((window.col_off+window.width)/bw))]
    ranges = []
    for index in ids:
        start = tags[324][index]; end = start+tags[325][index]
        ranges.extend((a, min(a+65536, end)-1) for a in range(start, end, 65536))
    def fetch(item):
        a, b = item; data, length, current_etag = get_bytes(a, b)
        if length != total or current_etag != etag: raise ValueError('source changed during crop')
        return a, data
    print(f'Fetching {len(ids)} native TIFF blocks in {len(ranges)} validated ranges', flush=True)
    with ThreadPoolExecutor(max_workers=4) as executor, path.open('r+b') as stream:
        for a, data in executor.map(fetch, ranges):
            stream.seek(a); stream.write(data)
    with rasterio.open(path) as src:
        array = src.read(1, window=window)
        crop_transform = src.window_transform(window); crop_crs = src.crs
    return array, crop_transform, crop_crs, window, etag, total, len(ids)


def acquire(config):
    cfg = yaml.safe_load(config.read_text(encoding='utf-8'))
    rid = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_worldcover_'+uuid.uuid4().hex[:8]
    out = ROOT/cfg['landcover_output_root']/rid
    out.mkdir(parents=True)
    write(out/'status.json', {'status': 'running'})
    try:
        terrain = ROOT/cfg['surface_package']/'gis/terrain_dsm_mean_150m.tif'
        with rasterio.open(terrain) as src:
            bounds = src.bounds
            crs = src.crs
            transform = src.transform
            shape = src.shape
            geographic = transform_bounds(crs, 4326, *bounds, densify_pts=21)
        categorical = np.zeros((shape[0]*5, shape[1]*5), np.uint8)
        fine_transform = transform*Affine.scale(.2, .2)
        sources = []
        for lat in range(math.floor(geographic[1]/3)*3, math.floor(geographic[3]/3)*3+1, 3):
            for lon in range(math.floor(geographic[0]/3)*3, math.floor(geographic[2]/3)*3+1, 3):
                tile = f'N{lat:02d}E{lon:03d}'
                url = cfg['landcover']['url_template'].format(tile=tile)
                path = out/(tile+'_crop.tif')
                print('Reading source window '+url, flush=True)
                cache = out/(tile+'_INCOMPLETE_block_cache.tif')
                array, crop_transform, crop_crs, window, etag, total, blocks = cached_window(url, cache, bounds, crs)
                with rasterio.open(path, 'w', driver='GTiff', height=array.shape[0],
                                       width=array.shape[1], count=1, dtype='uint8', crs=crop_crs,
                                       transform=crop_transform, nodata=0, compress='deflate') as dst:
                    dst.write(array, 1)
                sources.append({'url': url, 'file': path.name, 'etag': etag,
                                    'remote_bytes': total, 'native_blocks': blocks,
                                    'sha256': sha(path), 'bytes': path.stat().st_size,
                                    'transport': 'validated 64KiB HTTP range reads of native TIFF blocks',
                                    'window_col_row_width_height': list(window.flatten()),
                                    'changes': 'Native categorical window re-encoded losslessly as GeoTIFF; not original whole-file bytes.'})
                reproject(array, categorical, src_transform=crop_transform,
                              src_crs=crop_crs, src_nodata=0, dst_transform=fine_transform,
                              dst_crs=crs, dst_nodata=0, init_dest_nodata=False,
                              resampling=Resampling.nearest, num_threads=1)
                print(f'Archived {tile} native crop {array.shape}', flush=True)
        groups = {'built': [50], 'vegetation': [10, 20, 30, 40, 90, 95, 100],
                  'bare': [60, 70], 'water': [80]}
        if not np.isin(categorical, sum(groups.values(), [])).all():
            raise ValueError('Missing or unsupported land-cover classes in model domain')
        fractions = {}
        for name, codes in groups.items():
            a = np.isin(categorical, codes).reshape(shape[0], 5, shape[1], 5).mean(axis=(1, 3))
            fractions[name] = a.ravel()
        loss = sum(fractions[k]*v for k, v in cfg['landcover']['loss_mm_h'].items())
        np.savez_compressed(out/'landcover_parameters.npz', **fractions, loss_mm_h=loss,
                            categorical_30m=categorical, shape=np.array(shape))
        write(out/'source.json', {'dataset': cfg['landcover']['version'], 'year': 2021,
              'license': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
              'attribution': 'ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021), processed by ESA WorldCover consortium',
              'dataset_doi': 'https://doi.org/10.5281/zenodo.7254221',
              'sources': sources, 'classification': 'satellite_land_cover_not_measured_infiltration',
              'processing': '10m categories nearest-sampled at 30m; 5x5 class fractions at 150m. Not exact 10m areal fractions.',
              'loss_assumptions_mm_h': cfg['landcover']['loss_mm_h'],
              'domain_cells': int(loss.size), 'loss_min_mm_h': float(loss.min()),
              'loss_max_mm_h': float(loss.max()),
              'fraction_means': {k: float(v.mean()) for k, v in fractions.items()}})
        shutil.copy2(config, out/config.name)
        write(out/'status.json', {'status': 'complete', 'run_id': rid})
        write(out/'manifest.json', {'run_id': rid,
              'inputs': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
                         for p in [config, Path(__file__), terrain]],
              'outputs': [{'path': p.relative_to(out).as_posix(), 'sha256': sha(p)}
                          for p in sorted(out.iterdir()) if p.is_file()]})
        print('LANDCOVER_PACKAGE '+out.relative_to(ROOT).as_posix(), flush=True)
    except BaseException:
        write(out/'status.json', {'status': 'failed', 'traceback': traceback.format_exc()})
        raise
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='configs/longgang_adaptive.yaml')
    acquire(ROOT/parser.parse_args().config)
