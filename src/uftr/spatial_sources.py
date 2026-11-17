"""Public, bounded downloads and immutable local snapshot verification."""
from pathlib import Path
import json
import requests
from .archive import file_hash, now, write_json
from .osm_download import USER_AGENT


def acquire_sources(directory: Path, sources: dict, timeout=60):
    directory.mkdir(parents=True, exist_ok=False)
    records = {}
    for name, spec in sources.items():
        path = (directory / name).resolve()
        path.relative_to(directory.resolve())
        record = {'url': spec['url'], 'accessed_at': now(), 'license': spec['license']}
        try:
            response = requests.get(spec['url'], timeout=(15, timeout), stream=True,
                                    headers={'User-Agent': USER_AGENT})
            with response:
                record.update(http_status=response.status_code, url=response.url,
                              etag=response.headers.get('ETag'))
                with path.open('wb') as stream:
                    for chunk in response.iter_content(1024*1024):
                        stream.write(chunk)
                record.update(bytes=path.stat().st_size, sha256=file_hash(path))
                response.raise_for_status()
                if name.endswith('.tif'):
                    import rasterio
                    with rasterio.open(path) as src:
                        if src.crs is None: raise ValueError('raster lacks CRS')
                elif name.endswith('.csv'):
                    if not path.read_bytes().startswith(b'"STATION"'):
                        raise ValueError('expected NOAA GSOD CSV, received non-data response')
            record['status'] = 'downloaded'
        except Exception as exc:
            record.update(status='unavailable', error=str(exc))
            if spec.get('required'):
                write_json(path.with_suffix(path.suffix+'.source.json'), record)
                raise
        write_json(path.with_suffix(path.suffix+'.source.json'), record)
        records[name] = record
    return records


def seal_snapshot(directory: Path, contract: dict):
    inventory = {'created_at': now(), 'contract': contract, 'files': [
        {'path': p.relative_to(directory).as_posix(), 'sha256': file_hash(p)}
        for p in sorted(directory.rglob('*')) if p.is_file() and p.name != 'source_inventory.json']}
    path = directory / 'source_inventory.json'
    if path.exists(): raise FileExistsError('immutable source snapshot already sealed')
    write_json(path, inventory)
    return inventory


def verify_snapshot(directory: Path, contract=None):
    directory = directory.resolve()
    inventory = json.loads((directory/'source_inventory.json').read_text(encoding='utf-8'))
    if contract is not None and inventory['contract'] != contract:
        raise ValueError('snapshot contract mismatch')
    for item in inventory['files']:
        p = (directory/item['path']).resolve()
        p.relative_to(directory)
        if file_hash(p) != item['sha256']:
            raise ValueError('snapshot checksum mismatch: '+item['path'])
    return inventory
