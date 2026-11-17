import numpy as np
import pandas as pd
import pytest
from uftr.flood import hydrograph,spatial_parameters,road_response


def test_finite_hydrograph_recovery():
    t=np.arange(0,86401,900);q=hydrograph(t,[32400,36000],[14400,18000],[21600,25200])
    assert np.all((q>=0)&(q<=1))
    assert np.all(q[0]==0) and np.all(q[-1]==0)
    assert q[36,0]==1 and np.all(np.diff(q[:37,0])>=0) and np.all(np.diff(q[36:,0])<=0)


def test_spatial_reproducibility_and_seed_change():
    s={'correlation_length_m':1000,'base_peak_m':.3,'log_depth_sd':.2,'delay_sd_hours':.3,'peak_hour':9,'rise_hours':4,'recession_hours':8}
    a=spatial_parameters([[0,0],[1,0],[3000,3000]],42,s)
    pd.testing.assert_frame_equal(a,spatial_parameters([[0,0],[1,0],[3000,3000]],42,s))
    assert not a.equals(spatial_parameters([[0,0],[1,0],[3000,3000]],43,s))
    assert abs(a.peak_m.iloc[0]-a.peak_m.iloc[1])<.01


@pytest.mark.parametrize('model',['pregnolato','linear'])
def test_response_normal_monotone_closed(model):
    h=np.linspace(0,.5,1001);s={'closure_depth_m':.3,'minimum_capacity_fraction':.2,'capacity_loss_at_closure':.8}
    for speed in [20,50,100]:
        q=road_response(h,speed,1800,s,model)
        assert q.iloc[0].speed_kph==speed and q.iloc[0].capacity_veh_h==1800
        assert np.all(np.diff(q.speed_kph)<=1e-9) and np.all(np.diff(q.capacity_veh_h)<=1e-9)
        assert (q.loc[h>=.3,['speed_kph','capacity_veh_h']]==0).all().all()
        assert q.loc[h>=.3,'closed'].all()
    with pytest.raises(ValueError):road_response([-1],50,1800,s)
