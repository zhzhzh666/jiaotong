import numpy as np
import pandas as pd
import pytest
from uftr.assignment import TrafficNetwork
from uftr.road_performance import network_snapshot
from uftr.traffic_process import validate_profile,interval_od,state_arrays,integrate_intervals,congestion_fraction


def profile():
    return pd.DataFrame({'interval_index':np.arange(96),'start_hour':np.arange(96)/4,
        'end_hour':(np.arange(96)+1)/4,'duration_hours':.25,'base_period':'offpeak','rate_multiplier':1.})


def test_daily_departures_are_96_intervals_and_rates_are_not_trips():
    p=profile();validate_profile(p)
    od=pd.DataFrame({'flow_veh_h':[100.,20.,5.],'route_status':['loaded','unreachable','intrazonal_not_graph_loaded']})
    q=interval_od(od,.4)
    assert q.flow_veh_h.tolist()==[40.,8.,2.] and q.route_status.tolist()==od.route_status.tolist()
    assert q.flow_veh_h.sum()*.25==12.5
    assert integrate_intervals(p,np.ones(96))==1
    values=np.r_[np.zeros(48),np.ones(48)]
    assert integrate_intervals(p,values)==.5


@pytest.mark.parametrize('bad',['duplicate','gap','97th','negative'])
def test_invalid_departure_profiles_rejected(bad):
    p=profile()
    if bad=='duplicate':p.loc[1,'interval_index']=0
    if bad=='gap':p.loc[1,'start_hour']+=.1
    if bad=='97th':p=pd.concat([p,p.tail(1)],ignore_index=True)
    if bad=='negative':p.loc[0,'rate_multiplier']=-1
    with pytest.raises(ValueError):validate_profile(p)


def test_sparse_frozen_states_preserve_reverse_parallel_arcs_and_penalized_demand():
    e=pd.DataFrame({'edge_id':['a','parallel','reverse'],'u':[1,1,2],'v':[2,2,1],'key':[0,1,0],
        'length_m':[100.,120.,100.],'free_flow_speed_kph':[50.,30.,50.],
        'free_flow_time_s':[7.2,14.4,7.2],'capacity_veh_h':[1800.,900.,1800.]})
    n=TrafficNetwork(e,[1,2,3]);s=network_snapshot(e,pd.DataFrame({'edge_id':['a'],'depth_m':[.3]}),
        {'closure_depth_m':.3,'minimum_capacity_fraction':.2,'capacity_loss_at_closure':.8})
    t,c,closed=state_arrays(n,s.iloc[[0]])
    assert closed.tolist()==[True,False,False] and c[0]==0 and np.isinf(t[0])
    od=pd.DataFrame({'origin_node':[1,3,1],'destination_node':[2,2,1],'flow_veh_h':[100.,20.,5.]})
    r=n.solve(od,t0=t,capacity=c,closed=closed)
    assert r.flow[0]==0 and r.flow[1]==pytest.approx(100)
    assert r.served_veh_h+r.unserved_veh_h+r.intrazonal_veh_h==125
    assert r.unserved_veh_h==20 and r.intrazonal_veh_h==5
    bad=s.iloc[[0]].copy();bad['key']=8
    with pytest.raises(ValueError):state_arrays(n,bad)


def test_congestion_uses_degraded_capacity_and_ignores_closed_edges():
    assert congestion_fraction([50,0],[40,0],[False,True])==1
    assert congestion_fraction([50,0],[100,0],[False,True])==0
    assert congestion_fraction([0],[0],[True])==0
