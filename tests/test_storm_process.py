import numpy as np
import pytest
from uftr.storm_process import simulate_ponding, threshold_metrics


def test_constant_input_and_event_water_balance():
    result = simulate_ponding(np.full((4, 2), 10.), .25, .8, [2., 3.], [0., 8.], 4.)
    h = result['depth_m'] * 1000
    assert np.allclose(h[-1]-h[0], result['inflow_mm'].sum(0)-result['drained_mm'].sum(0), atol=1e-12)
    assert np.max(np.abs(result['balance_residual_mm'])) < 1e-12
    # Independent recurrence for the no-constant-drainage first pond.
    assert h[4, 0] == pytest.approx(16 * sum((1-.25/4)**j for j in range(4)))


def test_dry_recession_matches_discrete_closed_form_and_clips_at_zero():
    result = simulate_ponding(np.zeros((20, 1)), .25, .8, 2, 8, 4, .1)
    expected = [max((100+8*4)*(1-.25/4)**k-8*4, 0)/1000 for k in range(21)]
    assert result['depth_m'][:, 0] == pytest.approx(expected)
    assert np.all(np.diff(result['depth_m'][:, 0]) <= 0)
    dry = simulate_ponding(np.zeros((2, 1)), .25, .8, 2, 1000, 4, .001)
    assert np.array_equal(dry['depth_m'][1:], np.zeros((2, 1)))


def test_threshold_interpolation_and_repeated_exceedance():
    m = threshold_metrics([0, 1, 2, 3, 4], [0, .2, 0, .2, 0], .1)
    assert m['duration_above_h'] == pytest.approx(2.)
    assert m['recovery_hour'] == pytest.approx(3.5)
    assert m['hours_after_peak'] == pytest.approx(2.5)
    assert m['status'] == 'recovered'


def test_censored_and_never_exceeded_are_distinct():
    dry = threshold_metrics([0, 1, 2], [0, .1, 0], .1)
    assert dry['duration_above_h'] == 0 and dry['status'] == 'not_exceeded'
    assert dry['recovery_hour'] is None
    wet = threshold_metrics([0, 1, 2], [0, .2, .15], .1)
    assert wet['status'] == 'right_censored' and wet['recovery_hour'] is None
    assert wet['duration_above_h'] == pytest.approx(1.5)


@pytest.mark.parametrize('kwargs', [{'dt_h':0}, {'recession_tau_h':.1}, {'drainage_mm_h':-1},
                                   {'runoff_coefficient':1.2}, {'initial_depth_m':float('nan')}])
def test_invalid_physical_parameters_rejected(kwargs):
    params=dict(dt_h=.25, runoff_coefficient=.8, concentration_ratio=2, drainage_mm_h=8, recession_tau_h=4)
    params.update(kwargs)
    with pytest.raises(ValueError):
        simulate_ponding(np.zeros((2, 1)), **params)
