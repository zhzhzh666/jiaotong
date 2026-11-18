"""PPT-defined resilience, bounded-memory full OD UE and facility coverage.

Independent time slices with BPR costs, not dynamic user equilibrium. Structural
efficiency can use fixed sampled origins; all denominators remain fixed.
"""
import numpy as np
from scipy.sparse import coo_matrix, csr_matrix, bmat
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.sparse.linalg import spsolve_triangular
from .assignment import TrafficNetwork


def tree_load(distances, predecessor, demand):
    """Accumulate a positive-cost shortest-path tree in compiled sparse solve."""
    distances = np.asarray(distances, float)
    predecessor = np.asarray(predecessor, int)
    n = len(predecessor)
    order = np.argsort(distances)[::-1]
    position = np.empty(n, int); position[order] = np.arange(n)
    children = np.flatnonzero(predecessor >= 0)
    parent_position = position[predecessor[children]]
    child_position = position[children]
    if np.any(parent_position <= child_position) or np.any(distances[predecessor[children]] >= distances[children]):
        raise ValueError('Shortest tree must have strictly positive edge costs')
    rows = np.r_[np.arange(n), parent_position]
    cols = np.r_[np.arange(n), child_position]
    values = np.r_[np.ones(n), -np.ones(len(children))]
    matrix = coo_matrix((values, (rows, cols)), shape=(n, n)).tocsr()
    load = spsolve_triangular(matrix, np.asarray(demand)[order], lower=True, unit_diagonal=True)
    answer = np.empty(n); answer[order] = load
    return answer


class BatchedTrafficNetwork(TrafficNetwork):
    """Same Frank-Wolfe solver, compiled tree loading, one origin in memory."""
    def aon(self, cost, active, prepared):
        q, origin, destination, intra, valid, groups = prepared
        flow = np.zeros(len(self.edges)); od_time = np.full(len(q), np.inf)
        served = np.zeros(len(q), bool)
        graph, lookup = self.graph(cost, active)
        chosen = np.array(list(lookup.values()), dtype=int)
        pairs = self.pair[chosen]
        for source, ids in groups:
            distance, predecessor = dijkstra(graph, indices=int(source), directed=True, return_predecessors=True)
            reachable = ids[np.isfinite(distance[destination[ids]])]
            served[reachable] = True; od_time[reachable] = distance[destination[reachable]]
            weights = np.bincount(destination[reachable], weights=q[reachable], minlength=len(self.nodes))
            load = tree_load(distance, predecessor, weights)
            nodes = np.flatnonzero((predecessor >= 0) & (load > 0))
            keys = predecessor[nodes].astype(np.int64)*len(self.nodes)+nodes
            np.add.at(flow, chosen[np.searchsorted(pairs, keys)], load[nodes])
        return flow, od_time, served


def structure_metrics(network, times, closed, origins, batch_size=8):
    if not len(origins) or batch_size < 1:
        raise ValueError('Positive efficiency origin count and batch size required')
    graph, _ = network.graph(times, ~closed)
    n = len(network.nodes)
    result = {'available_edge_fraction': float(np.mean(~closed))}
    for connection in ['weak', 'strong']:
        _, labels = connected_components(graph, directed=True, connection=connection)
        result[connection+'_fraction'] = float(np.bincount(labels).max()/n)
    indices = [network.node_index[int(v)] for v in origins]
    total = 0.
    for begin in range(0, len(indices), batch_size):
        distances = dijkstra(graph, directed=True, indices=indices[begin:begin+batch_size])
        total += np.divide(1., distances, out=np.zeros_like(distances),
                           where=np.isfinite(distances) & (distances > 0)).sum()
    result['time_efficiency'] = float(total/(len(indices)*max(n-1, 1)))
    return result


def facility_coverage(network, times, closed, origins, facilities):
    graph, _ = network.graph(times, ~closed)
    n = len(network.nodes)
    population = origins.population_estimate.to_numpy(float)
    denominator = population.sum()
    if denominator <= 0:
        raise ValueError('Positive population denominator required')
    result = {}
    for category in ['hospital', 'fire_station']:
        part = facilities.loc[(facilities.category == category) & facilities.connected]
        if part.empty:
            raise ValueError('No connected public OSM '+category+'; do not invent Qf')
        # A super-source adds each entrance connector cost before reversing roads.
        # Co-located POIs use minimum access cost rather than sparse sum duplicates.
        nodes = np.array([network.node_index[int(x)] for x in part.node_id])
        extra = part.access_time_s.to_numpy(float)
        unique = np.unique(nodes)
        best = np.array([extra[nodes == j].min() for j in unique])
        row = csr_matrix((best+1e-9, (np.zeros(len(unique), int), unique)), shape=(1, n))
        augmented = bmat([[graph.T.tocsr(), None], [row, csr_matrix((1, 1))]], format='csr')
        distances = dijkstra(augmented, directed=True, indices=n)[:n]-1e-9
        access = np.full(len(origins), np.inf)
        for k, item in enumerate(origins.itertuples()):
            if item.node_id in network.node_index:
                access[k] = distances[network.node_index[item.node_id]]+item.access_time_s
        for minutes in [15, 30]:
            result[f'{category}_{minutes}min'] = float(population[access <= minutes*60].sum()/denominator)
    return result


def ppt_quality(metrics, baseline, weights=(.27, .41, .32)):
    skeys = ['available_edge_fraction', 'weak_fraction', 'strong_fraction', 'time_efficiency']
    fkeys = [f'{category}_{m}min' for category in ['hospital', 'fire_station'] for m in [15, 30]]
    weights = np.asarray(weights, float)
    if weights.shape != (3,) or (weights < 0).any() or not np.isclose(weights.sum(), 1):
        raise ValueError('Three nonnegative weights summing to one required')
    for key in skeys+fkeys+['cost_veh_s_h']:
        if baseline[key] <= 0 or not np.isfinite(baseline[key]):
            raise ValueError('PPT normalization undefined for dry baseline: '+key)
        if metrics[key] < 0 or not np.isfinite(metrics[key]):
            raise ValueError('Invalid metric: '+key)
    qs = float(np.mean([metrics[k]/baseline[k] for k in skeys]))
    qp = baseline['cost_veh_s_h']/metrics['cost_veh_s_h'] if metrics['cost_veh_s_h'] > 0 else float('inf')
    # Equal mean of hospital/fire ratios at each threshold, then equal mean of
    # the two thresholds. K=2 types; both threshold results are also reported.
    qf15 = float(np.mean([metrics[f'{c}_15min']/baseline[f'{c}_15min'] for c in ['hospital', 'fire_station']]))
    qf30 = float(np.mean([metrics[f'{c}_30min']/baseline[f'{c}_30min'] for c in ['hospital', 'fire_station']]))
    qf = (qf15+qf30)/2
    quality = float(np.dot(weights, [qs, qp, qf]))
    if not np.isfinite(quality):
        raise ValueError('Nonfinite PPT quality')
    return {'Qs': qs, 'Qp': qp, 'Qf': qf, 'Qf15': qf15, 'Qf30': qf30, 'Q': quality,
            'above_one': bool(quality > 1+1e-8)}


def integrate_quality(seconds, quality):
    t = np.asarray(seconds, float); q = np.asarray(quality, float)
    if t.ndim != 1 or q.shape != t.shape or len(t) < 2 or not np.isfinite(t).all() or np.any(np.diff(t) <= 0) or not np.isfinite(q).all():
        raise ValueError('Ordered finite endpoint series required')
    return float(np.trapezoid(q, t)/(t[-1]-t[0]))
