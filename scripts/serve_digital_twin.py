"""Loopback-only, self-contained viewer server; no third-party network requests."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import webbrowser
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


class ViewerHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = Path(self.translate_path(self.path))
        compressed = path.with_suffix(path.suffix+'.gz')
        if (path.suffix == '.json' and 'gzip' in self.headers.get('Accept-Encoding', '')
                and path.is_file() and compressed.is_file()
                and compressed.stat().st_mtime >= path.stat().st_mtime):
            stream = compressed.open('rb')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Vary', 'Accept-Encoding')
            self.send_header('Content-Length', str(compressed.stat().st_size))
            self.end_headers()
            return stream
        return super().send_head()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=8766)
    p.add_argument('--no-browser', action='store_true')
    args = p.parse_args()
    directory = ROOT/'dashboard/digital-twin'
    for file in ['network.json', 'dry.json', 'rain_rolling.json', 'governed_rolling.json', 'audit.json']:
        if not (directory/'data'/file).is_file():
            raise SystemExit('Missing data/'+file+'. Run .conda-env/python.exe scripts/export_digital_twin.py first.')
    handler = partial(ViewerHandler, directory=str(directory))
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler)
    except OSError as exc:
        if not args.no_browser:
            url = f'http://127.0.0.1:{args.port}/'
            try:
                with urlopen(url, timeout=2) as response:
                    if response.read() == (directory/'index.html').read_bytes():
                        webbrowser.open(url)
                        return
            except OSError:
                pass
        raise SystemExit(f'Port {args.port} unavailable; use --port with another port. {exc}')
    url = f'http://127.0.0.1:{server.server_port}/'
    print('Digital twin: '+url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
