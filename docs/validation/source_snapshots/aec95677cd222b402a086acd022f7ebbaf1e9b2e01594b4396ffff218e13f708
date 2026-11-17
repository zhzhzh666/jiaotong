"""Static user equilibrium with explicit parallel arcs and unreachable demand."""
from __future__ import annotations
from dataclasses import dataclass
import time
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.optimize import brentq


@dataclass
class AssignmentResult:
    flow: np.ndarray
    time: np.ndarray
    trace: pd.DataFrame
    served_veh_h: float
    unserved_veh_h: float
    intrazonal_veh_h: float
    total_veh_h: float
    relative_gap: float
    converged: bool
    node_balance_max_error: float
    elapsed_s: float
    od_cost_s: np.ndarray
    od_served: np.ndarray


def bpr(flow,t0,capacity,alpha=.15,beta=4):
    if np.any(np.asarray(capacity)<=0):raise ValueError('closed edges must be excluded before BPR')
    return np.asarray(t0)*(1+alpha*(np.asarray(flow)/capacity)**beta)


class TrafficNetwork:
    def __init__(self,edges,nodes=None):
        self.edges=edges.reset_index(drop=True).copy()
        if not self.edges.edge_id.is_unique:raise ValueError('unique directed edge_id required')
        self.nodes=np.array(sorted(set(edges.u)|set(edges.v)|set([] if nodes is None else nodes)))
        self.node_index={v:i for i,v in enumerate(self.nodes)}
        self.u=np.array([self.node_index[x] for x in edges.u]);self.v=np.array([self.node_index[x] for x in edges.v])
        self.pair=self.u*len(self.nodes)+self.v
        for name in ['free_flow_time_s','capacity_veh_h']:
            if not np.isfinite(edges[name]).all() or (edges[name]<=0).any():raise ValueError('positive finite '+name+' required')
        self.t0=edges.free_flow_time_s.to_numpy(float);self.capacity=edges.capacity_veh_h.to_numpy(float)

    def graph(self,cost,active):
        ids=np.flatnonzero(active)
        order=ids[np.lexsort((ids,cost[ids],self.pair[ids]))]
        # Exactly one current cheapest arc per ordered node pair in shortest paths.
        # Assignment flows remain independent for all original parallel arcs.
        unique=np.r_[True,np.diff(self.pair[order])!=0] if len(order) else np.array([],bool)
        chosen=order[unique]
        graph=csr_matrix((cost[chosen],(self.u[chosen],self.v[chosen])),shape=(len(self.nodes),len(self.nodes)))
        lookup={int(self.pair[i]):int(i) for i in chosen}
        return graph,lookup

    def prepare_od(self,od):
        q=od.flow_veh_h.to_numpy(float)
        if not np.isfinite(q).all() or (q<0).any():raise ValueError('invalid demand')
        orig=np.array([self.node_index.get(x,-1) for x in od.origin_node]);dest=np.array([self.node_index.get(x,-1) for x in od.destination_node])
        intra=od.route_status.eq('intrazonal_not_graph_loaded').to_numpy() if 'route_status' in od else (orig==dest)&(orig>=0)
        valid=(orig>=0)&(dest>=0)&~intra
        groups=[(o,np.flatnonzero(valid&(orig==o))) for o in np.unique(orig[valid])]
        return q,orig,dest,intra,valid,groups

    def aon(self,cost,active,prepared):
        q,orig,dest,intra,valid,groups=prepared
        flow=np.zeros(len(self.edges));od_time=np.full(len(q),np.inf);served=np.zeros(len(q),bool)
        graph,lookup=self.graph(cost,active);n=len(self.nodes)
        # Process one origin at a time: bounded memory even for the full real network.
        for o,ids in groups:
            dist,pred=dijkstra(graph,indices=int(o),directed=True,return_predecessors=True)
            reachable=ids[np.isfinite(dist[dest[ids]])];served[reachable]=True;od_time[reachable]=dist[dest[reachable]]
            load=np.bincount(dest[reachable],weights=q[reachable],minlength=n)
            # A shortest path tree is acyclic because costs are strictly positive.
            for v in np.argsort(dist)[::-1]:
                if load[v]>0 and pred[v]>=0:
                    u=int(pred[v]);flow[lookup[u*n+int(v)]]+=load[v];load[u]+=load[v]
        return flow,od_time,served

    def solve(self,od,t0=None,capacity=None,closed=None,tolerance=1e-4,max_iterations=500,alpha=.15,beta=4,warm_start=None):
        started=time.perf_counter();t0=self.t0.copy() if t0 is None else np.asarray(t0,float)
        cap=self.capacity.copy() if capacity is None else np.asarray(capacity,float)
        active=np.ones(len(self.edges),bool) if closed is None else ~np.asarray(closed,bool)
        if np.any(t0[active]<=0) or not np.isfinite(t0[active]).all() or np.any(cap[active]<=0) or not np.isfinite(cap[active]).all():
            raise ValueError('invalid open edge state')
        p=self.prepare_od(od);q,orig,dest,intra,valid,groups=p
        costs=np.full(len(cap),np.inf);costs[active]=t0[active]
        x,_,_=self.aon(costs,active,p) # feasible flow for current closures; never reuse infeasible old routes
        trace=[]
        for iteration in range(max_iterations+1):
            costs[active]=bpr(x[active],t0[active],cap[active],alpha,beta)
            y,od_time,served=self.aon(costs,active,p)
            total=float(np.dot(x[active],costs[active]));shortest=float(np.dot(y[active],costs[active]))
            gap=max(0.,(total-shortest)/total) if total>0 else 0.
            trace.append({'iteration':iteration,'relative_gap':gap,'system_travel_time_veh_s_h':total,
                'beckmann':float(np.sum(t0[active]*(x[active]+alpha*x[active]**(beta+1)/((beta+1)*cap[active]**beta))))})
            if gap<=tolerance or iteration==max_iterations:break
            direction=y-x
            def derivative(step):return float(np.dot(direction[active],bpr((x+step*direction)[active],t0[active],cap[active],alpha,beta)))
            step=1. if derivative(1.)<=0 else brentq(derivative,0.,1.,xtol=1e-12)
            trace[-1]['step_size']=step;x=x+step*direction
        net=np.bincount(self.u,weights=x,minlength=len(self.nodes))-np.bincount(self.v,weights=x,minlength=len(self.nodes))
        expected=np.bincount(orig[served],weights=q[served],minlength=len(self.nodes))-np.bincount(dest[served],weights=q[served],minlength=len(self.nodes))
        return AssignmentResult(x,costs,pd.DataFrame(trace),float(q[served].sum()),float(q[~served&~intra].sum()),float(q[intra].sum()),
            float(q.sum()),gap,gap<=tolerance,float(np.max(np.abs(net-expected),initial=0)),time.perf_counter()-started,od_time,served)


def load_osm(directory):
    import osmnx as ox
    graph=ox.load_graphml(directory/'road_network.graphml',edge_dtypes={x:float for x in ['free_flow_time_s','capacity_veh_h','length_m','free_flow_speed_kph']})
    rows=[{**d,'u':u,'v':v,'key':k} for u,v,k,d in graph.edges(keys=True,data=True)]
    return TrafficNetwork(pd.DataFrame(rows),list(graph.nodes)),graph


def result_summary(r):
    return {name:getattr(r,name) for name in ['served_veh_h','unserved_veh_h','intrazonal_veh_h','total_veh_h','relative_gap','converged','node_balance_max_error','elapsed_s']}
