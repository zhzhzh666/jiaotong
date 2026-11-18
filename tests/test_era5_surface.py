"""Numerical checks for the desktop/GIS routing kernel (no mobile UI)."""
import numpy as np
import pytest
from uftr.era5_surface import priority_drainage,route_step,simulate


def settings():
    return {'time':{'internal_seconds':180,'output_minutes':15},'initial_depth_m':0.,
            'loss':{'capacity_mm_h':0.},'thresholds_m':[.01,.15]}


CASE={'rain_multiplier':1.,'loss_multiplier':1.,'tau_multiplier':1.}


def test_bowl_keeps_depression_storage_and_acyclic_receiver():
    z=np.full((5,5),3.);z[1:4,1:4]=0
    d=priority_drainage(z,100)
    assert np.all(d['spill_depth_m'].reshape(z.shape)[1:4,1:4]==3)
    i=d['receiver']>=0
    assert np.all(d['rank'][d['receiver'][i]]<d['rank'][i])
    np.testing.assert_array_equal(z[1:4,1:4],0)


def test_single_pulse_transfers_without_creation():
    h=np.array([1.,0.]);r=np.array([1,-1]);s=np.zeros(2);tau=np.ones(2)*10
    after,loss,out=route_step(h,0,0,r,s,tau,10)
    np.testing.assert_allclose(after,[np.exp(-1),1-np.exp(-1)])
    assert loss==out==0
    for _ in range(30):
        before=after.sum();after,loss,out=route_step(after,0,0,r,s,tau,10)
        assert after.sum()+loss+out==pytest.approx(before)
    assert after.sum()<1e-10


def test_spill_threshold_is_retained_and_loss_is_available_water_limited():
    after,loss,out=route_step(np.array([.5]),0,0,np.array([-1]),np.array([1.]),np.array([1.]),10)
    assert after[0]==.5 and out==0
    after,loss,out=route_step(after,0,2,np.array([-1]),np.array([1.]),np.array([1.]),10)
    assert after[0]==0 and loss==.5 and out==0


def test_simulation_domain_budget_and_spatial_transfer():
    z=np.zeros((2,2));d=priority_drainage(z,10)
    # Force a chain: rain only in cell 0, all other cells are dry forcing.
    d['receiver']=np.array([1,3,3,-1]);d['rank']=np.array([3,2,1,0])
    rain=np.array([[100.,0.],[0.,0.]])
    result=simulate(z,d,np.full(4,900.),rain,np.array([0,1,1,1]),10,np.ones(4),np.arange(4),settings(),CASE)
    last=result['ledger'][-1]
    assert last['cumulative_rain_m3']==pytest.approx(10.)
    assert last['storage_m3']+last['cumulative_boundary_outflow_m3']==pytest.approx(10.)
    assert result['road_sample_depth_m'][:,1].max()>0
    assert abs(last['balance_residual_m3'])<1e-10


def test_zero_rain_control_and_no_loss_budget():
    z=np.array([[2.,1.],[1.,0.]]);d=priority_drainage(z,10)
    result=simulate(z,d,np.ones(4)*900,np.zeros((2,1)),np.zeros(4,int),10,np.ones(4),np.arange(4),settings(),CASE)
    assert not result['road_sample_depth_m'].any()
    assert all(row['storage_m3']==0 for row in result['ledger'])


@pytest.mark.parametrize('value',[np.nan,-1.,np.inf])
def test_bad_rain_rejected(value):
    z=np.zeros((2,2));d=priority_drainage(z,10)
    with pytest.raises(ValueError,match='rain'):
        simulate(z,d,np.ones(4)*900,np.array([[value]]),np.zeros(4,int),10,np.ones(4),np.arange(4),settings(),CASE)


def test_time_step_refinement_on_outlet_has_expected_convergence():
    z=np.zeros((2,2));d=priority_drainage(z,10);cfg=settings()
    args=(z,d,np.ones(4)*900,np.array([[40.],[0.]]),np.zeros(4,int),10,np.ones(4),np.arange(4),cfg,CASE)
    coarse=simulate(*args,dt_s=180)['road_sample_depth_m']
    fine=simulate(*args,dt_s=60)['road_sample_depth_m']
    finer=simulate(*args,dt_s=20)['road_sample_depth_m']
    assert abs(fine-finer).max()<abs(coarse-finer).max()


def test_cycle_rejected():
    z=np.zeros((2,2));d=priority_drainage(z,10);d['receiver'][:2]=[1,0]
    with pytest.raises(ValueError,match='cyclic'):
        simulate(z,d,np.ones(4)*900,np.zeros((1,1)),np.zeros(4,int),10,np.ones(4),np.arange(4),settings(),CASE)
