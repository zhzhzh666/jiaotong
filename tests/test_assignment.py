import numpy as np
import pandas as pd
import pytest
from uftr.assignment import TrafficNetwork,bpr


def fixture():
    return TrafficNetwork(pd.DataFrame({'edge_id':['a','b','c'],'u':[1,1,2],'v':[2,2,3],
        'free_flow_time_s':[1.,2.,1.],'capacity_veh_h':[1000.,1000.,10000.]}),[1,2,3,4])


def test_parallel_equilibrium_and_conservation():
    n=fixture();od=pd.DataFrame({'origin_node':[1,4,1],'destination_node':[3,3,1],'flow_veh_h':[2500.,20.,5.]})
    r=n.solve(od,tolerance=1e-9)
    assert r.converged and r.relative_gap<1e-9
    assert abs(r.flow[:2].sum()-2500)<1e-8 and (r.flow[:2]>0).all()
    assert abs(r.time[0]-r.time[1])<1e-6
    assert r.node_balance_max_error<1e-8
    assert r.served_veh_h+r.unserved_veh_h+r.intrazonal_veh_h==2525
    assert r.unserved_veh_h==20 and r.intrazonal_veh_h==5
    assert np.all(np.diff(r.trace.beckmann)<=1e-7)


def test_closure_disconnection_and_restore():
    n=fixture();od=pd.DataFrame({'origin_node':[1],'destination_node':[3],'flow_veh_h':[100.]})
    r=n.solve(od,capacity=[0,1000,10000],closed=[True,False,False])
    assert r.flow[0]==0 and r.flow[1]==100 and r.served_veh_h==100
    r=n.solve(od,capacity=[0,0,10000],closed=[True,True,False])
    assert r.unserved_veh_h==100 and np.all(r.flow==0)
    assert n.solve(od).served_veh_h==100
    with pytest.raises(ValueError):bpr([1],[1],[0])
