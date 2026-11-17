"""Auditable normalized structure/performance/function metrics."""
import numpy as np
from scipy.sparse.csgraph import connected_components,dijkstra


def normalized(value,baseline):
    return float(value/baseline) if baseline>0 else None


def integrate(times_s,values):
    t=np.asarray(times_s,float);v=np.asarray(values,float)
    if len(t)<2 or np.any(np.diff(t)<=0) or not np.isfinite(v).all():raise ValueError('ordered endpoints and finite values required')
    return float(np.trapezoid(v,t)/(t[-1]-t[0]))


def structure(network,cost,closed,origin_nodes):
    graph,_=network.graph(cost,~closed);n=len(network.nodes)
    values={}
    for kind in ['weak','strong']:
        count,labels=connected_components(graph,directed=True,connection=kind)
        values[kind+'_components']=int(count);values['largest_'+kind+'_fraction']=float(np.bincount(labels).max()/n)
    idx=[network.node_index[x] for x in origin_nodes if x in network.node_index]
    distances=dijkstra(graph,indices=idx,directed=True)
    inverse=np.divide(1.,distances,out=np.zeros_like(distances),where=np.isfinite(distances)&(distances>0))
    values['sampled_time_efficiency_per_s']=float(inverse.sum()/(len(idx)*max(n-1,1))) if len(idx) else 0.
    values['available_edge_fraction']=float((~closed).mean())
    return values


def accessibility(network,cost,closed,origins,facilities):
    graph,_=network.graph(cost,~closed);records=origins[['zone_id','population_estimate']].copy()
    # Keep population with missing node connections in denominator, access = infinity.
    for category in ['hospital','fire_station','shelter']:
        part=facilities[facilities.category.eq(category)]
        times=np.full(len(origins),np.inf)
        if len(part):
            ids=[network.node_index[x] for x in part.node_id]
            distances=dijkstra(graph.T.tocsr(),directed=True,indices=ids)
            best=np.min(distances+part.access_time_s.to_numpy()[:,None],axis=0)
            for k,row in enumerate(origins.itertuples()):
                if row.node_id in network.node_index:times[k]=best[network.node_index[row.node_id]]+row.access_time_s
        records[category+'_time_s']=times
    population=origins.population_estimate.to_numpy();total=float(population.sum());summary={}
    for category in ['hospital','fire_station','shelter']:
        available=bool(facilities.category.eq(category).any());summary[category+'_available']=available
        for minutes in [15,30]:
            summary[f'{category}_{minutes}min_coverage']=float(population[records[category+'_time_s']<=minutes*60].sum()/total) if total>0 and available else None
    return summary,records


def evaluate_metrics(network,result,closed,origins,facilities,efficiency_origins,baseline=None,rho_s=14400,weights=None):
    st=structure(network,result.time,closed,efficiency_origins)
    access,records=accessibility(network,result.time,closed,origins,facilities)
    active=~closed
    travel=float(np.dot(result.flow[active],result.time[active]))
    # Intrazonal demand is explicitly retained at the same 300 s in all states.
    cost=travel+300*result.intrazonal_veh_h+rho_s*result.unserved_veh_h
    metrics={**st,**access,'travel_cost_veh_s_h':travel,'total_cost_veh_s_h':cost,
        'served_veh_h':result.served_veh_h,'unserved_veh_h':result.unserved_veh_h,
        'intrazonal_veh_h':result.intrazonal_veh_h,'total_veh_h':result.total_veh_h,
        'mean_served_network_time_s':travel/result.served_veh_h if result.served_veh_h else 0.,
        'congested_open_edge_fraction':float(np.mean(result.flow[active]/network.capacity[active]>.9)) if active.any() else 0.,
        'unserved_fraction':result.unserved_veh_h/result.total_veh_h if result.total_veh_h else 0.,
        'relative_gap':result.relative_gap,'converged':result.converged,'node_balance_error':result.node_balance_max_error}
    b=metrics if baseline is None else baseline
    skeys=['largest_weak_fraction','largest_strong_fraction','sampled_time_efficiency_per_s','available_edge_fraction']
    ratios=[normalized(metrics[k],b[k]) for k in skeys];metrics['Qs']=float(np.mean([x for x in ratios if x is not None]))
    metrics['Qp']=b['total_cost_veh_s_h']/cost if cost>0 else (1. if b['total_cost_veh_s_h']==0 else 0.)
    fkeys=[f'{c}_{m}min_coverage' for c in ['hospital','fire_station','shelter'] for m in [15,30]]
    ratios=[normalized(metrics[k],b[k]) for k in fkeys if metrics[k] is not None and b[k] is not None]
    ratios=[v for v in ratios if v is not None];metrics['Qf']=float(np.mean(ratios)) if ratios else None
    w=weights or {'structure':.2,'performance':.5,'functionality':.3}
    valid=[('structure','Qs'),('performance','Qp')]+([('functionality','Qf')] if metrics['Qf'] is not None else [])
    metrics['Q']=sum(w[k]*metrics[v] for k,v in valid)/sum(w[k] for k,v in valid)
    metrics['function_weight_available']=metrics['Qf'] is not None
    return metrics,records
