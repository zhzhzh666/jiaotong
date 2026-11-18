"""Longgang microscopic pilot: frozen source IDs, boundary OD and rolling routes.

Capacity is represented by an uncalibrated headway proxy, NOT imposed veh/h.
No future flood states are used by online routing. Flat OSG is visualization only.
"""
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET
import numpy as np


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def contiguous_visits(path, inside):
    """Retain every contiguous visit; a re-entry is an explicitly separate visit."""
    visits = []; current = []
    for edge in path:
        if inside[edge]:
            current.append(int(edge))
        elif current:
            visits.append(current); current = []
    if current:
        visits.append(current)
    return visits


def prefer_route(old_route, new_route, weights, closed, minimum_seconds, minimum_fraction):
    if not new_route or any(e in closed for e in new_route):
        return False
    if any(e in closed for e in old_route):
        return True
    old = sum(weights[e] for e in old_route)
    new = sum(weights[e] for e in new_route)
    return old-new > max(minimum_seconds, old*minimum_fraction)


def accounting(planned, invalid, external, loaded, pending, running, arrived):
    """Disjoint planned outcomes, including SUMO's loaded-but-not-departed queue."""
    residual = int(planned-invalid-external-pending-running-arrived)
    loaded_residual = int(loaded-pending-running-arrived)
    return {'planned': int(planned), 'invalid': int(invalid), 'external_pending': int(external),
            'sumo_pending': int(pending), 'running': int(running), 'arrived': int(arrived),
            'injected': int(loaded), 'balance_error': residual,
            'injected_balance_error': loaded_residual}


def read_nodes(graphml):
    """Stream only nodes of the frozen graph, whose nodes precede its edges."""
    nodes = {}
    keys = {}
    for event, element in ET.iterparse(graphml, events=('end',)):
        tag = element.tag.rsplit('}', 1)[-1]
        if tag == 'key':
            keys[element.attrib['id']] = element.attrib.get('attr.name')
        elif tag == 'node':
            values = {keys[d.attrib['key']]: d.text for d in element}
            nodes[int(element.attrib['id'])] = (float(values['x']), float(values['y']))
            element.clear()
        elif tag == 'edge':
            break
    return nodes


def window_start(depths, duration_seconds, threshold):
    count = np.count_nonzero(depths >= threshold, axis=1)
    peak = int(np.argmax(count))
    steps = duration_seconds//900
    return max(0, min(peak-steps//2, len(depths)-1-steps)), peak, count


def tau_proxy(normal_capacity, normal_speed_m_s, capacity_factor):
    # 5m vehicle + 2.5m minimum gap; kinematic approximation, not calibration.
    base = max(1., 3600/normal_capacity-7.5/normal_speed_m_s)
    return base/max(.2, capacity_factor)


def route_stage_paths(corridors, chains, source_inside, connector_nodes, matrices):
    """Full eligible OD -> dry shortest paths -> every ROI visit, no OD sampling."""
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra
    nodes = np.array(sorted(set(corridors.u)|set(corridors.v)))
    lookup = {int(n): i for i, n in enumerate(nodes)}
    u = np.array([lookup[int(n)] for n in corridors.u]); v = np.array([lookup[int(n)] for n in corridors.v])
    pairkey = u*len(nodes)+v
    ids = np.flatnonzero(u != v)
    time = corridors.normal_time_s.to_numpy()
    order = ids[np.lexsort((ids, time[ids], pairkey[ids]))]
    chosen = order[np.r_[True, np.diff(pairkey[order]) != 0]]
    graph = csr_matrix((time[chosen], (u[chosen], v[chosen])), shape=(len(nodes), len(nodes)))
    edge_lookup = {int(pairkey[j]): int(j) for j in chosen}
    affected = np.array([source_inside[c].any() for c in chains])
    positions = np.array([lookup.get(int(n), -1) for n in connector_nodes])
    rows = []; disconnected_rate = 0.; outside_rate = 0.; eligible_rate = 0.
    for i in np.flatnonzero(positions >= 0):
        if i % 40 == 0: print('OD shortest paths origin', int(i), flush=True)
        distances, predecessor = dijkstra(graph, indices=int(positions[i]), directed=True, return_predecessors=True)
        for j in np.flatnonzero((positions >= 0) & (matrices[0][i] > 0)):
            if i == j: continue
            rate = float(matrices[0][i, j]); eligible_rate += rate
            target = int(positions[j]); origin = int(positions[i])
            if not np.isfinite(distances[target]):
                disconnected_rate += rate; continue
            path = []; hit = False
            while target != origin:
                previous = int(predecessor[target])
                if previous < 0: raise ValueError('broken frozen predecessor')
                edge = edge_lookup[previous*len(nodes)+target]
                path.append(edge); hit = hit or affected[edge]; target = previous
            if not hit:
                outside_rate += rate; continue
            source_path = [int(e) for c in path[::-1] for e in chains[c]]
            visits = contiguous_visits(source_path, source_inside)
            for visit_number, visit in enumerate(visits):
                rows.append({'origin_zone': int(i), 'destination_zone': int(j),
                             'visit': visit_number, 'visits_for_original_trip': len(visits),
                             'source_arc_positions': visit,
                             'rates_veh_h': [float(m[i, j]) for m in matrices]})
    return rows, {'eligible_offpeak_veh_h': eligible_rate,
                  'disconnected_offpeak_veh_h': disconnected_rate,
                  'outside_offpeak_veh_h': outside_rate,
                  'roi_visit_offpeak_veh_h': sum(r['rates_veh_h'][0] for r in rows),
                  'roi_visits': len(rows),
                  'note': 'Every dry shortest-path ROI visit; re-entries count as separate visits. Boundary routes fixed from dry network, not a citywide rerouting model.'}


def make_plan(visits, edge_ids, net, start_seconds, settings, seed):
    rng = np.random.default_rng(seed); records = []; expected = 0.
    for visit_index, row in enumerate(visits):
        route = [str(edge_ids[e]) for e in row['source_arc_positions']]
        valid = all(net.getEdge(a).getConnections(net.getEdge(b)) for a, b in zip(route, route[1:]))
        # SUMO's own route can remedy a dry turning mismatch; retain original endpoints.
        if not valid:
            candidate, _ = net.getShortestPath(net.getEdge(route[0]), net.getEdge(route[-1]), vClass='passenger')
            if candidate: route = [e.getID() for e in candidate]; valid = True
        for t in range(0, settings['departure_seconds'], 900):
            hour = ((start_seconds+t)/3600) % 24
            period = 1 if 7 <= hour < 10 else (2 if 17 <= hour < 20 else 0)
            lam = row['rates_veh_h'][period]*.25*settings['demand_fraction']; expected += lam
            for _ in range(int(rng.poisson(lam))):
                records.append({'vehicle_id': f'v{len(records):07d}', 'depart_s': float(t+rng.uniform(0, 900)),
                                'visit_index': visit_index, 'origin_zone': row['origin_zone'],
                                'destination_zone': row['destination_zone'], 'visit': row['visit'],
                                'normal_route': ' '.join(route), 'valid': valid})
    records.sort(key=lambda r: (r['depart_s'], r['vehicle_id']))
    return records, {'expected_scaled_visit_departures': expected, 'planned_vehicles': len(records),
                     'valid_planned': sum(r['valid'] for r in records),
                     'invalid_planned': sum(not r['valid'] for r in records),
                     'demand_fraction': settings['demand_fraction'], 'poisson_seed': seed,
                     'assumption': 'Poisson departures from synthetic full OD ROI visit rates; scaled physical demand, not weighted full-demand vehicles'}
