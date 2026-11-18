"""Uncalibrated land-cover routing, fluid point queues and binary NSGA-II.

Queue service is proportional between path commodities, not strict FIFO.
Routes are chosen at departure from a finite library; this is dynamic network
loading, not dynamic user equilibrium. No physical queue spillback is modelled.
"""
from itertools import combinations
import numpy as np


def surface_route(grid, hourly_mm, loss_mm_h, multiplier, road_links, settings):
    n = len(grid['receiver'])
    loss = np.asarray(loss_mm_h, float)
    if loss.shape != (n,) or not np.isfinite(loss).all() or (loss < 0).any():
        raise ValueError('invalid spatial loss capacity')
    rain = np.asarray(hourly_mm, float)
    if not np.isfinite(rain).all() or (rain < 0).any() or multiplier < 0:
        raise ValueError('invalid rainfall')
    dt = settings['internal_seconds']; output = settings['output_seconds']
    if dt <= 0 or 3600 % dt or output % dt:
        raise ValueError('invalid surface time step')
    receiver = grid['receiver']; inside = receiver >= 0
    fraction = -np.expm1(-dt/grid['tau_s'])
    h = np.zeros(n); peak = h.copy(); area = settings['cell_size_m']**2
    cumulative = np.zeros(3); ledger = [[0., 0., 0., 0., 0., 0.]]
    links = np.asarray(road_links, int)
    samples = [h[links].astype(np.float32)]
    loss_step = loss*dt/3600000
    for k in range(len(rain)*3600//dt):
        r = rain[k*dt//3600, grid['rain_grid_id']]*multiplier*dt/3600000
        h += r
        removed = np.minimum(h, loss_step); h -= removed
        transfer = np.maximum(h-grid['spill_depth_m'], 0)*fraction; h -= transfer
        h += np.bincount(receiver[inside], weights=transfer[inside], minlength=n)
        cumulative += [r.sum()*area, removed.sum()*area, transfer[~inside].sum()*area]
        peak = np.maximum(peak, h)
        if (k+1)*dt % output == 0:
            stored = h.sum()*area
            residual = stored-cumulative[0]+cumulative[1]+cumulative[2]
            ledger.append([(k+1)*dt/3600, *cumulative, stored, residual])
            samples.append(h[links].astype(np.float32))
    if not np.isfinite(h).all() or (h < 0).any():
        raise ValueError('invalid water state')
    return {'sample_depth_m': np.asarray(samples), 'ledger': np.asarray(ledger),
            'peak_depth_m': peak, 'final_depth_m': h}


def road_factors(depth, normal_speed, capacity_loss, closure=.3):
    h = np.asarray(depth, float)
    known = np.isfinite(h)
    if (h[known] < 0).any() or closure <= 0 or closure > .3:
        raise ValueError('invalid road depth or closure')
    w = np.where(known, h, 0)*1000
    limit = np.maximum(0, .0009*w*w-.5529*w+86.9448)
    speed = np.where(w == 0, normal_speed, np.minimum(normal_speed, limit))
    closed = known & (h >= closure)
    speed = np.where(closed, 0, speed)
    capacity = np.where(closed, 0, np.maximum(.2, 1-capacity_loss*w/(closure*1000)))
    # NaN remains explicit in known; traffic uses a labelled assumed-normal case.
    return speed, capacity, known


def sample_od(matrices, connectors, per_origin, seed=42):
    """Systematic destination strata per origin; exact row totals every period.

    Period matrices must be proportional (true for this synthetic OD). Each
    stratum has equal row weight, repeated selected destinations are combined.
    Diagonal and disconnected-connector demand are kept outside road loading.
    """
    base = np.asarray(matrices[0], float)
    if base.ndim != 2 or base.shape[0] != base.shape[1] or per_origin < 1:
        raise ValueError('invalid OD sampling')
    n = len(base); connected = np.asarray(connectors, int) >= 0
    intra = np.eye(n, dtype=bool)
    valid = connected[:, None] & connected[None, :] & ~intra
    row = np.where(valid, base, 0).sum(axis=1)
    rng = np.random.default_rng(seed)
    origins = []; destinations = []; weights = []
    for i in np.flatnonzero(row > 0):
        cdf = np.cumsum(np.where(valid[i], base[i], 0)/row[i]); cdf[-1] = 1
        quantiles = (np.arange(per_origin)+rng.random())/per_origin
        dest, counts = np.unique(np.searchsorted(cdf, quantiles, side='right'), return_counts=True)
        for j, count in zip(dest, counts):
            origins.append(i); destinations.append(j); weights.append(row[i]*count/per_origin)
    weights = np.asarray(weights)
    rates = []; unlinked = []; intrazonal = []
    for matrix in matrices:
        a = np.asarray(matrix, float)
        factor = a.sum()/base.sum()
        if not np.allclose(a, base*factor, rtol=1e-8, atol=1e-10):
            raise ValueError('destination strata require proportional period matrices')
        rates.append(weights*factor)
        unlinked.append(float(a[~valid & ~intra].sum()))
        intrazonal.append(float(np.trace(a)))
    return {'origin_zone': np.array(origins), 'destination_zone': np.array(destinations),
            'rates': np.asarray(rates), 'unlinked_rates': np.asarray(unlinked),
            'intrazonal_rates': np.asarray(intrazonal), 'eligible_row_rates': row}


def point_queue(paths, pair_for_path, edge_for_stage, next_stage, first_stage,
                last_stage, base_time, capacity, times, capacity_factors,
                pair_rates, periods, access_seconds, settings, dt=None, save_series=True):
    """Conservative path-commodity fluid point queues with explicit transit lags.

    Finite paths chosen at quarter-hour departures by instantaneous time plus
    queue/capacity. Demand without an open library path waits at origin. An
    in-network commodity cannot discharge into a currently closed next link.
    Proportional service, unlimited point storage, no BPR double counting.
    """
    dt = int(dt or settings['internal_seconds'])
    if dt <= 0 or 900 % dt:
        raise ValueError('traffic step must divide 900 seconds')
    t = np.asarray(times, float); cf = np.asarray(capacity_factors, float)
    cap = np.asarray(capacity, float)
    if t.shape != cf.shape or t.shape[1] != len(cap) or (cf < 0).any() or not np.isfinite(cf).all():
        raise ValueError('invalid time-varying edge states')
    if not np.isfinite(t).all() or (t <= 0).any() or (cap <= 0).any():
        raise ValueError('invalid positive travel times or capacities')
    pair = np.asarray(pair_for_path, int); edge = np.asarray(edge_for_stage, int)
    nxt = np.asarray(next_stage, int); first = np.asarray(first_stage, int)
    last = np.asarray(last_stage, int)
    if len(np.unique(first)) != len(first) or len(np.unique(nxt[nxt >= 0])) != np.count_nonzero(nxt >= 0):
        raise ValueError('path stages must have unique first/successor indices')
    # Connector travel is included as a delay on the first route stage.
    maxlag = int(np.ceil((t.max()+np.max(access_seconds, initial=0))/dt))+2
    if maxlag*len(edge) > 100_000_000:
        raise ValueError('transit ring exceeds bounded memory')
    ring = np.zeros((maxlag, len(edge)), float); queue = np.zeros(len(edge))
    backlog = np.zeros(pair_rates.shape[1]); completed = released = area = 0.
    max_error = 0.; series = []; edge_peak = np.zeros(len(cap))
    mass_in_transit = 0.; horizon = (len(t)-1)*900
    path_lengths = np.array([len(p) for p in paths])
    if len(paths):
        path_index = np.repeat(np.arange(len(paths)), path_lengths)
        path_order = np.lexsort((np.arange(len(paths)), pair))
    else:
        path_index = np.array([], int); path_order = np.array([], int)
    for step in range(horizon//dt):
        seconds = step*dt; k = seconds//900; slot = step % maxlag
        arrived = ring[slot].copy(); ring[slot] = 0
        queue += arrived; mass_in_transit -= float(arrived.sum())
        active_cap = cap*cf[k]
        work = np.bincount(edge, weights=queue, minlength=len(cap))
        if seconds % 900 == 0:
            new = pair_rates[periods[k]]*.25
            released += float(new.sum()); backlog += new
            cost = t[k]+settings['routing_delay_weight']*np.divide(work, active_cap/3600,
                        out=np.zeros_like(work), where=active_cap > 0)
            stage_cost = cost[edge]
            pcost = np.bincount(path_index, weights=stage_cost, minlength=len(paths))
            path_closed = np.bincount(path_index, weights=(active_cap[edge] <= 0), minlength=len(paths)) > 0
            pcost[path_closed] = np.inf
            # Stable tie order: lower path-library index.
            best = np.full(len(backlog), np.inf); chosen = np.full(len(backlog), -1, int)
            for p in path_order:
                if pcost[p] < best[pair[p]]:
                    best[pair[p]] = pcost[p]; chosen[pair[p]] = p
            selected_pairs = np.flatnonzero((chosen >= 0) & (backlog > 0))
            selected_paths = chosen[selected_pairs]
            if len(selected_pairs):
                stages = first[selected_paths]; amount = backlog[selected_pairs].copy()
                backlog[selected_pairs] = 0
                lags = np.maximum(1, np.ceil((t[k, edge[stages]]+access_seconds[selected_pairs])/dt).astype(int))
                # Distinct path stages have distinct ring columns; indexed
                # addition is exact here and avoids scatter-add overhead.
                ring[(step+lags) % maxlag, stages] += amount
                mass_in_transit += float(amount.sum())
        # Block only commodities whose next edge is closed. Unlimited upstream
        # point queues do not physically obstruct other turning movements.
        eligible = np.ones(len(edge), bool)
        onward = nxt >= 0
        eligible[onward] = active_cap[edge[nxt[onward]]] > 0
        eligible_queue = queue*eligible
        demand = np.bincount(edge, weights=eligible_queue, minlength=len(cap))
        fraction = np.minimum(1, np.divide(active_cap*dt/3600, demand,
                               out=np.zeros_like(demand), where=demand > 0))
        sent = eligible_queue*fraction[edge]; queue -= sent
        discharge = np.bincount(edge, weights=sent, minlength=len(cap))
        if np.any(discharge > active_cap*dt/3600+1e-7):
            raise ValueError('point-queue capacity violation')
        completed += float(sent[last].sum())
        targets = nxt[onward]; values = sent[onward]
        positive = values > 1e-14; targets = targets[positive]; values = values[positive]
        lag = np.maximum(1, np.ceil(t[k, edge[targets]]/dt).astype(int))
        ring[(step+lag) % maxlag, targets] += values
        mass_in_transit += float(values.sum())
        current = float(queue.sum()+mass_in_transit+backlog.sum())
        residual = released-completed-current
        max_error = max(max_error, abs(residual))
        # Right-endpoint occupancy quadrature, convergence measured at dt/2.
        area += current*dt
        edge_peak = np.maximum(edge_peak, np.bincount(edge, weights=queue, minlength=len(cap)))
        if (step+1)*dt % 900 == 0 and save_series:
            series.append([(step+1)*dt/3600, released, completed, queue.sum(),
                           mass_in_transit, backlog.sum(), current, residual, area])
    if max_error > max(1e-5, released*1e-9):
        raise ValueError('vehicle conservation failure')
    # Finite-horizon occupancy cost and a separate terminal penalty; incomplete
    # trips remain incomplete, no fictitious completion at the end of the window.
    unfinished = released-completed
    return {'released_trips': released, 'completed_trips': completed,
            'unfinished_trips': unfinished, 'in_network_trips': float(queue.sum()+mass_in_transit),
            'origin_backlog_trips': float(backlog.sum()), 'vehicle_seconds': area,
            'penalized_vehicle_seconds': area+unfinished*settings['terminal_penalty_seconds'],
            'maximum_conservation_error_veh': max_error, 'series': np.asarray(series),
            'edge_peak_queue_veh': edge_peak,
            'transit_ring_remaining_veh': float(ring.sum()),
            'transit_counter_veh': mass_in_transit}


def feasible_masks(n, max_sites):
    return [sum(1 << j for j in c) for k in range(min(n, max_sites)+1)
            for c in combinations(range(n), k)]


def fronts(values):
    a = np.asarray(values, float)
    if a.ndim != 2 or not np.isfinite(a).all():
        raise ValueError('finite objective matrix required')
    dominates = np.all(a[:, None, :] <= a[None, :, :], axis=2) & np.any(a[:, None, :] < a[None, :, :], axis=2)
    count = dominates.sum(axis=0); remaining = np.ones(len(a), bool); result = []
    while remaining.any():
        layer = np.flatnonzero(remaining & (count == 0))
        if not len(layer): raise ValueError('invalid dominance relation')
        result.append(layer); remaining[layer] = False; count -= dominates[layer].sum(axis=0)
    return result


def crowding(values):
    a = np.asarray(values, float); score = np.zeros(len(a))
    if len(a) <= 2: return np.full(len(a), np.inf)
    for j in range(a.shape[1]):
        order = np.argsort(a[:, j], kind='stable'); span = a[order[-1], j]-a[order[0], j]
        if span <= 0: continue
        score[order[[0, -1]]] = np.inf
        score[order[1:-1]] += (a[order[2:], j]-a[order[:-2], j])/span
    return score


def nsga2(n, max_sites, evaluate, population=12, generations=8, seed=42):
    """Binary crossover/mutation, rank-crowding tournaments and elitist survival."""
    rng = np.random.default_rng(seed); feasible = feasible_masks(n, max_sites)
    size = min(population, len(feasible))
    initial = list(dict.fromkeys([0]+[1 << i for i in range(n)]))[:size]
    remaining = [m for m in feasible if m not in initial]
    if len(initial) < size: initial += list(rng.choice(remaining, size-len(initial), replace=False))
    pop = np.asarray(initial, int); seen = set(); history = []
    def objectives(masks):
        seen.update(map(int, masks)); return np.array([evaluate(int(m)) for m in masks])
    def select(masks, values):
        chosen = []
        for layer in fronts(values):
            order = layer[np.argsort(-crowding(values[layer]), kind='stable')]
            chosen.extend(order[:size-len(chosen)])
            if len(chosen) == size: break
        return masks[chosen]
    for generation in range(generations):
        value = objectives(pop); rank = np.empty(len(pop), int); distance = np.zeros(len(pop))
        for r, layer in enumerate(fronts(value)):
            rank[layer] = r; distance[layer] = crowding(value[layer])
        def tournament():
            a, b = rng.integers(len(pop), size=2)
            return int(pop[min((a, b), key=lambda i: (rank[i], -distance[i], int(pop[i])))])
        children = []
        for _ in range(size):
            a, b = tournament(), tournament(); child = 0
            for bit in range(n):
                chosen = ((a if rng.random() < .5 else b) >> bit) & 1
                if rng.random() < 1/n: chosen ^= 1
                child |= chosen << bit
            while child.bit_count() > max_sites:
                bits = [j for j in range(n) if child & (1 << j)]
                child &= ~(1 << int(rng.choice(bits)))
            children.append(child)
        union = np.array(sorted(set(map(int, pop)) | set(children)))
        uv = objectives(union); pop = select(union, uv)
        history.append({'generation': generation, 'evaluated_unique': len(seen),
                        'population': pop.tolist()})
    values = objectives(pop)
    return {'pareto_masks': pop[fronts(values)[0]].tolist(), 'evaluated_masks': sorted(seen),
            'history': history, 'seed': seed}
