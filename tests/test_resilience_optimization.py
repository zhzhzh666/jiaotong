import numpy as np
import pandas as pd
import pytest
from uftr.assignment import TrafficNetwork
from uftr.resilience import integrate,evaluate_metrics
from uftr.optimization import greedy,exhaustive


def test_normal_and_total_disruption_with_missing_shelters():
    n=TrafficNetwork(pd.DataFrame({'edge_id':['a','b'],'u':[1,2],'v':[2,1],'free_flow_time_s':[10.,10.],'capacity_veh_h':[1000.,1000.]}))
    od=pd.DataFrame({'origin_node':[1],'destination_node':[2],'flow_veh_h':[100.]})
    origins=pd.DataFrame({'zone_id':['z'],'node_id':[1],'population_estimate':[1000.],'access_time_s':[0.]})
    fac=pd.DataFrame({'category':['hospital'],'node_id':[2],'access_time_s':[0.]})
    r=n.solve(od);base,a=evaluate_metrics(n,r,np.array([False,False]),origins,fac,[1])
    assert base['Q']==1 and base['shelter_15min_coverage'] is None
    r=n.solve(od,closed=[True,True]);m,a=evaluate_metrics(n,r,np.array([True,True]),origins,fac,[1],base)
    assert m['Qf']==0 and m['Qp']<.01 and m['Q']<.2 and m['unserved_veh_h']==100
    assert np.isfinite(m['Q'])
    assert integrate([0,1,2],[1,0,1])==.5
    with pytest.raises(ValueError):integrate([0,0],[1,1])


def test_budget_greedy_recomputes_and_matches_small_exhaustive():
    calls=[]
    def score(s):
        calls.append(frozenset(s));return sum({'a':4,'b':3,'c':1}[v] for v in s)-(2 if {'a','b'}<=set(s) else 0)
    costs={'a':2,'b':1,'c':1};chosen,trace=greedy(list(costs),costs,3,2,score)
    best,value,count=exhaustive(list(costs),costs,3,2,score)
    assert sum(costs[e] for e in chosen)<=3 and len(chosen)<=2
    # Greedy has no universal optimality guarantee; this fixture exposes a gap.
    assert score(chosen)==4 and value==5
    assert frozenset(['a','b']) in calls and len(trace)==2
