"""Source-preserving directed corridor contraction and finite route library."""
from collections import defaultdict
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from .adaptive import road_factors


def contract(graph, connector_nodes, settings):
    rows = []
    for u, v, key, data in graph.edges(keys=True, data=True):
        highway = str(data['highway']).removesuffix('_link')
        cap = settings['capacity_per_direction_veh_h'].get(highway, settings['capacity_per_direction_veh_h']['fallback'])
        loss = settings['capacity_loss'].get(highway, settings['capacity_loss']['fallback'])
        rows.append({'u': int(u), 'v': int(v), 'key': int(key), 'edge_id': data['edge_id'],
                     'source_feature_position': int(data['source_feature_position']),
                     'length_m': float(data['length_m']), 'speed_kph': float(data['speed_kph']),
                     'highway': highway, 'capacity_veh_h': cap, 'capacity_loss': loss})
    edges = pd.DataFrame(rows)
    outgoing = defaultdict(list); incoming = defaultdict(list); neighbors = defaultdict(set)
    parallel = defaultdict(int)
    for j, (u, v) in enumerate(zip(edges.u, edges.v)):
        outgoing[u].append(j); incoming[v].append(j)
        neighbors[u].add(v); neighbors[v].add(u); parallel[u, v] += 1
    anchors = set(map(int, connector_nodes))
    anchors.update(n for n in neighbors if len(neighbors[n]) != 2 or len(outgoing[n]) > 2 or len(incoming[n]) > 2)
    for (u, v), count in parallel.items():
        if count > 1: anchors.update([u, v])
    u = edges.u.to_numpy(); v = edges.v.to_numpy(); used = np.zeros(len(edges), bool)
    chains = []; records = []
    starts = [j for j in range(len(edges)) if u[j] in anchors]
    for start in starts+list(range(len(edges))):
        if used[start]: continue
        chain = []; current = start
        while True:
            if used[current]: break
            used[current] = True; chain.append(current)
            node = v[current]
            if node in anchors or node == u[start]: break
            candidates = [j for j in outgoing[node] if v[j] != u[current]]
            if len(candidates) != 1 or used[candidates[0]]: break
            current = candidates[0]
        index = len(chains); chains.append(np.asarray(chain, int))
        records.append({'corridor_id': index, 'u': int(u[chain[0]]), 'v': int(v[chain[-1]]),
                        'source_arcs': len(chain)})
    if not used.all(): raise ValueError('source arcs missing in corridor contraction')
    corridors = pd.DataFrame(records)
    flat = np.concatenate(chains); offsets = np.r_[0, np.cumsum([len(x) for x in chains])[:-1]]
    normal_time = edges.length_m.to_numpy()*3.6/edges.speed_kph.to_numpy()
    corridors['normal_time_s'] = np.add.reduceat(normal_time[flat], offsets)
    corridors['normal_capacity_veh_h'] = np.minimum.reduceat(edges.capacity_veh_h.to_numpy()[flat], offsets)
    return edges, corridors, chains


def corridor_states(edges, chains, positions, depths, feature_lookup, settings):
    """Serial time sum / bottleneck capacity; unknown arcs assumed normal, labelled."""
    selected = [chains[int(j)] for j in positions]
    if not selected: raise ValueError('empty route-edge union')
    flat = np.concatenate(selected); offsets = np.r_[0, np.cumsum([len(x) for x in selected])[:-1]]
    depth_column = 'depth_feature_position' if 'depth_feature_position' in edges else 'source_feature_position'
    features = edges[depth_column].to_numpy()[flat]
    f = np.array([feature_lookup.get(int(fid), -1) for fid in features], int)
    length = edges.length_m.to_numpy()[flat]
    speed0 = edges.speed_kph.to_numpy()[flat]
    cap0 = edges.capacity_veh_h.to_numpy()[flat]
    loss = edges.capacity_loss.to_numpy()[flat]
    normalcap = np.minimum.reduceat(cap0, offsets)
    travel = []; capacity = []
    for snapshot in depths:
        h = np.full(len(flat), np.nan); known = f >= 0; h[known] = snapshot[f[known]]
        speed, factor, _ = road_factors(h, speed0, loss, settings['closure_depth_m'])
        tt = length*3.6/np.where(speed > 0, speed, speed0)
        travel.append(np.add.reduceat(tt, offsets))
        capacity.append(np.minimum.reduceat(cap0*factor, offsets)/normalcap)
    return np.asarray(travel, np.float32), np.asarray(capacity, np.float32)


def route_library(corridors, states, origins, destinations):
    nodes = np.array(sorted(set(corridors.u)|set(corridors.v)))
    lookup = {int(n): j for j, n in enumerate(nodes)}
    u = np.array([lookup[int(n)] for n in corridors.u]); v = np.array([lookup[int(n)] for n in corridors.v])
    pairkey = u*len(nodes)+v
    sources = np.array([lookup.get(int(n), -1) for n in origins])
    targets = np.array([lookup.get(int(n), -1) for n in destinations])
    routes = [[] for _ in origins]
    for cost, capacity in states:
        ids = np.flatnonzero((capacity > 0) & (u != v))
        order = ids[np.lexsort((ids, cost[ids], pairkey[ids]))]
        chosen = order[np.r_[True, np.diff(pairkey[order]) != 0]] if len(order) else order
        graph = csr_matrix((cost[chosen], (u[chosen], v[chosen])), shape=(len(nodes), len(nodes)))
        arc = {int(pairkey[j]): int(j) for j in chosen}
        for origin in np.unique(sources[sources >= 0]):
            distance, predecessor = dijkstra(graph, directed=True, indices=int(origin), return_predecessors=True)
            for p in np.flatnonzero((sources == origin) & (targets >= 0)):
                destination = targets[p]
                if destination == origin or not np.isfinite(distance[destination]): continue
                path = []; current = int(destination)
                while current != origin:
                    previous = int(predecessor[current])
                    if previous < 0: raise ValueError('broken shortest-path predecessor')
                    path.append(arc[previous*len(nodes)+current]); current = previous
                path = tuple(path[::-1])
                if path not in routes[p]: routes[p].append(path)
    return routes


def pack_paths(routes, extra_direct_pairs=()):
    all_paths = []; pairs = []
    for pair, alternatives in enumerate(routes):
        for path in alternatives:
            all_paths.append(path); pairs.append(pair)
    union = np.array(sorted(set(e for p in all_paths for e in p)), int)
    lookup = {int(e): j for j, e in enumerate(union)}
    mapped = [np.array([lookup[e] for e in p], int) for p in all_paths]
    # Coincident graph connectors use a declared synthetic access-only edge.
    for k, pair in enumerate(extra_direct_pairs):
        mapped.append(np.array([len(union)+k])); pairs.append(int(pair))
    first = []; last = []; nxt = []; edges = []; offset = 0
    for path in mapped:
        first.append(offset); last.append(offset+len(path)-1)
        nxt.extend(list(range(offset+1, offset+len(path)))+[-1])
        edges.extend(path); offset += len(path)
    return {'paths': mapped, 'pair_for_path': np.array(pairs, int),
            'edge_for_stage': np.array(edges, int), 'next_stage': np.array(nxt, int),
            'first_stage': np.array(first, int), 'last_stage': np.array(last, int),
            'corridor_union': union, 'direct_pairs': np.array(extra_direct_pairs, int)}
