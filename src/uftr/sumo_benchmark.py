"""Whole-district demand and resource measurements (desktop SUMO, no GPU solver)."""
from pathlib import Path
import csv
import os
import threading
import time

import numpy as np
import psutil


def sample_full_od(matrices, start_seconds, settings, seed):
    """Draw whole trips before routing; retain intrazonal/unreachable draws."""
    rng = np.random.default_rng(seed)
    rows = []
    expected = 0.
    for t in range(0, settings['departure_seconds'], 900):
        hour = ((start_seconds+t)/3600) % 24
        period = 1 if 7 <= hour < 10 else (2 if 17 <= hour < 20 else 0)
        means = matrices[period]*.25*settings['demand_fraction']
        counts = rng.poisson(means)
        expected += float(means.sum())
        for i, j in zip(*np.nonzero(counts)):
            for _ in range(int(counts[i, j])):
                rows.append({'vehicle_id': f'v{len(rows):07d}',
                             'depart_s': float(t+rng.uniform(0, 900)),
                             'origin_zone': int(i), 'destination_zone': int(j)})
    rows.sort(key=lambda r: (r['depart_s'], r['vehicle_id']))
    return rows, expected


def sampled_source_routes(corridors, chains, connector_nodes, pairs):
    """Route sampled whole trips on the frozen complete source graph, not ROI visits."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra
    nodes = np.array(sorted(set(corridors.u)|set(corridors.v)))
    lookup = {int(n): i for i, n in enumerate(nodes)}
    u = np.array([lookup[int(n)] for n in corridors.u])
    v = np.array([lookup[int(n)] for n in corridors.v])
    keys = u*len(nodes)+v
    ids = np.flatnonzero(u != v)
    costs = corridors.normal_time_s.to_numpy()
    order = ids[np.lexsort((ids, costs[ids], keys[ids]))]
    chosen = order[np.r_[True, np.diff(keys[order]) != 0]]
    graph = csr_matrix((costs[chosen], (u[chosen], v[chosen])), shape=(len(nodes), len(nodes)))
    edge_lookup = {int(keys[e]): int(e) for e in chosen}
    positions = [lookup.get(int(n), -1) for n in connector_nodes]
    routes = {}
    for origin in sorted({i for i, _ in pairs}):
        targets = sorted(j for i, j in pairs if i == origin)
        source = positions[origin]
        distances, predecessor = (dijkstra(graph, indices=source, directed=True, return_predecessors=True)
                                  if source >= 0 else (None, None))
        for destination in targets:
            target = positions[destination]
            if origin == destination:
                routes[origin, destination] = ([], 'intrazonal_not_loaded')
            elif source < 0 or target < 0:
                routes[origin, destination] = ([], 'missing_connector')
            elif not np.isfinite(distances[target]):
                routes[origin, destination] = ([], 'source_disconnected')
            else:
                path = []
                while target != source:
                    previous = int(predecessor[target])
                    if previous < 0:
                        raise ValueError('Broken source predecessor')
                    path.append(edge_lookup[previous*len(nodes)+target])
                    target = previous
                arc_path = [int(e) for corridor in path[::-1] for e in chains[corridor]]
                routes[origin, destination] = (arc_path, 'source_reachable' if arc_path else 'same_connector_not_loaded')
        if origin % 40 == 0:
            print('Whole-trip source routes origin', origin, flush=True)
    return routes


class ResourceMonitor:
    """Sample summed resident working sets of Python and live descendants.

    RSS sums can count shared pages twice; this is not unique physical memory.
    Host used memory includes unrelated applications. Polling misses sub-second peaks.
    """
    def __init__(self, path, interval=1.):
        self.path = Path(path)
        self.interval = interval
        self.phase = 'preparation'
        self.started = time.perf_counter()
        self.process = psutil.Process(os.getpid())
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.samples = []
        self.stream = self.path.open('w', newline='', encoding='utf-8')
        self.writer = csv.DictWriter(self.stream, fieldnames=['wall_s', 'phase', 'python_rss_mib',
            'children_rss_mib', 'combined_rss_mib', 'host_available_mib', 'host_used_mib'])
        self.writer.writeheader()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def sample(self):
        own = self.process.memory_info().rss
        child_rss = 0
        for process in self.process.children(recursive=True):
            try:
                child_rss += process.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        host = psutil.virtual_memory()
        row = {'wall_s': time.perf_counter()-self.started, 'phase': self.phase,
               'python_rss_mib': own/2**20, 'children_rss_mib': child_rss/2**20,
               'combined_rss_mib': (own+child_rss)/2**20,
               'host_available_mib': host.available/2**20, 'host_used_mib': (host.total-host.available)/2**20}
        with self.lock:
            self.samples.append(row)
            self.writer.writerow(row)
            self.stream.flush()
        return row

    def _run(self):
        while not self.stop_event.wait(self.interval):
            self.sample()

    def start(self):
        self.sample()
        self.thread.start()
        return self

    def summary(self, since=0.):
        with self.lock:
            rows = [r for r in self.samples if r['wall_s'] >= since]
        return {'samples': len(rows), 'peak_combined_rss_mib': max((r['combined_rss_mib'] for r in rows), default=0.),
                'peak_python_rss_mib': max((r['python_rss_mib'] for r in rows), default=0.),
                'peak_children_rss_mib': max((r['children_rss_mib'] for r in rows), default=0.),
                'minimum_host_available_mib': min((r['host_available_mib'] for r in rows), default=0.)}

    def close(self):
        self.stop_event.set()
        self.thread.join(timeout=5)
        self.sample()
        self.stream.close()
