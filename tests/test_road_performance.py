import numpy as np
import pandas as pd
import pytest
from uftr.road_performance import evaluate_depth_rows,network_snapshot,traversable_edges,closure_episodes,graphml_edge_identities

SETTINGS={'closure_depth_m':.3,'minimum_capacity_fraction':.2,'capacity_loss_at_closure':.8}


def edges():
    return pd.DataFrame({'edge_id':['a','parallel','reverse'],'u':[1,1,2],'v':[2,2,1],'key':[0,1,0],
        'length_m':[100.,120.,100.],'free_flow_speed_kph':[50.,30.,50.],'capacity_veh_h':[1800.,900.,1800.]})


def test_graphml_identities_restored_without_parsing_hashed_edge_id(tmp_path):
    path=tmp_path/'edges.graphml'
    path.write_text('<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><key id="d1" for="edge" attr.name="edge_id"/>'
        '<graph edgedefault="directed"><edge source="10" target="20" id="1"><data key="d1">hashed_edge</data></edge></graph></graphml>')
    assert graphml_edge_identities(path).to_dict('records')==[{'edge_id':'hashed_edge','u':10,'v':20,'key':1}]


def test_parallel_and_direction_retained_and_closed_removed_from_routing():
    s=network_snapshot(edges(),pd.DataFrame({'edge_id':['a'],'depth_m':[.3]}),SETTINGS)
    assert s.edge_id.tolist()==['a','parallel','reverse']
    assert s.unlisted_assumed_dry.tolist()==[False,True,True]
    assert np.isinf(s.iloc[0].travel_time_s) and s.iloc[0].capacity_veh_h==0
    active=traversable_edges(s)
    assert active.edge_id.tolist()==['parallel','reverse']
    assert active.iloc[0].free_flow_time_s==pytest.approx(120*3.6/30)


def test_literature_units_capacity_is_independent_and_boundary_exact():
    data=pd.DataFrame({'time_s':[0,1,2,3],'edge_id':['a']*4,'depth_m':[0,.1,.15,.3]})
    s=evaluate_depth_rows(edges(),data,SETTINGS)
    assert s.speed_kph.tolist()==pytest.approx([50,40.6548,24.2598,0])
    assert s.capacity_ratio.tolist()==pytest.approx([1,1-.8/3,.6,0])
    assert s.state.tolist()==['normal','light','heavy','closed']
    assert s.closed.tolist()==[False,False,False,True]


def test_low_free_flow_speed_is_not_increased_by_polynomial():
    s=evaluate_depth_rows(edges(),pd.DataFrame({'edge_id':['parallel'],'depth_m':[.001]}),SETTINGS)
    assert s.iloc[0].speed_kph==30 and s.iloc[0].capacity_veh_h<900


def test_repeat_closure_exact_crossings_and_censoring():
    episodes=closure_episodes([0,1,2,3,4],[0,.4,0,.4,.4],.3)
    assert len(episodes)==2
    assert episodes[0]['closed_from_hour']==pytest.approx(.75)
    assert episodes[0]['reopen_hour']==pytest.approx(1.25)
    assert episodes[0]['duration_h']==pytest.approx(.5)
    assert episodes[1]['right_censored'] and episodes[1]['reopen_hour'] is None
    tangent=closure_episodes([0,1,2],[0,.3,0],.3)
    assert len(tangent)==1 and tangent[0]['duration_h']==0


@pytest.mark.parametrize('bad', ['unknown','duplicate','missing','bad_floor'])
def test_invalid_inputs_are_rejected(bad):
    data=pd.DataFrame({'edge_id':['a'],'depth_m':[.1]});settings=SETTINGS.copy()
    if bad=='unknown':data.edge_id='absent'
    if bad=='duplicate':data=pd.concat([data,data],ignore_index=True)
    if bad=='missing':data.depth_m=np.nan
    if bad=='bad_floor':settings['minimum_capacity_fraction']=1.1
    with pytest.raises(ValueError):network_snapshot(edges(),data,settings)
