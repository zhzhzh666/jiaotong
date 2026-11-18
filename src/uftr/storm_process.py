"""Synthetic rainfall storage and recession, with explicit units and censoring.

Independent pond proxies; this is not a hydraulic or calibrated drainage model.
"""
from __future__ import annotations

import numpy as np


def simulate_ponding(rain_mm, dt_h, runoff_coefficient, concentration_ratio,
                     drainage_mm_h, recession_tau_h, initial_depth_m=0.0):
    """rain_mm is (interval, point); output depth has one extra endpoint.

    H and drainage are computed in mm over each interval. Linear recession is
    explicit Euler, so require dt <= tau to preserve a nonnegative recession
    factor before the availability cap. The cap includes new interval inflow.
    """
    rain = np.asarray(rain_mm, dtype=float)
    if rain.ndim != 2 or not rain.size or not np.isfinite(rain).all() or (rain < 0).any():
        raise ValueError('rain_mm must be a finite nonnegative interval-by-point array')
    if not np.isfinite(dt_h) or dt_h <= 0:
        raise ValueError('dt_h must be positive')
    count = rain.shape[1]
    def vector(value, name):
        try:
            value = np.broadcast_to(np.asarray(value, dtype=float), (count,))
        except ValueError as exc:
            raise ValueError(name + ' must be scalar or point-sized') from exc
        if not np.isfinite(value).all() or (value < 0).any():
            raise ValueError(name + ' must be finite and nonnegative')
        return value
    runoff = vector(runoff_coefficient, 'runoff_coefficient')
    if (runoff > 1).any():
        raise ValueError('runoff_coefficient must not exceed 1')
    area = vector(concentration_ratio, 'concentration_ratio')
    drain = vector(drainage_mm_h, 'drainage_mm_h')
    tau = vector(recession_tau_h, 'recession_tau_h')
    if (tau < dt_h).any():
        raise ValueError('recession_tau_h must be at least dt_h')
    h = np.zeros((rain.shape[0] + 1, count), dtype=float)
    h[0] = vector(initial_depth_m, 'initial_depth_m') * 1000
    inflow = rain * runoff * area
    drained = np.zeros_like(rain)
    for k in range(len(rain)):
        available = h[k] + inflow[k]
        drained[k] = np.minimum(available, drain * dt_h + h[k] * dt_h / tau)
        h[k + 1] = available - drained[k]
    return {'depth_m': h / 1000, 'inflow_mm': inflow, 'drained_mm': drained,
            'balance_residual_mm': h[1:] - h[:-1] - inflow + drained}


def threshold_metrics(time_h, depth_m, threshold_m):
    """Integrate h > threshold using linear interpolation between endpoints.

    Recovery means the final downward crossing following the event maximum,
    with no later exceedance within the observation window. Never-exceeded and
    right-censored events have no fabricated recovery time. This is an observed
    model-window metric, not a promise that another storm cannot occur later.
    """
    t, h = np.asarray(time_h, float), np.asarray(depth_m, float)
    if t.ndim != 1 or h.shape != t.shape or len(t) < 2 or not np.isfinite(t).all() or not np.isfinite(h).all():
        raise ValueError('time/depth must be equal finite one-dimensional arrays')
    if (np.diff(t) <= 0).any() or (h < 0).any() or not np.isfinite(threshold_m) or threshold_m < 0:
        raise ValueError('strictly increasing time and nonnegative depths/threshold required')
    above = h > threshold_m
    fraction = np.zeros(len(h) - 1)
    fraction[above[:-1] & above[1:]] = 1
    rise = ~above[:-1] & above[1:]
    fall = above[:-1] & ~above[1:]
    fraction[rise] = (h[1:][rise] - threshold_m) / (h[1:][rise] - h[:-1][rise])
    fraction[fall] = (h[:-1][fall] - threshold_m) / (h[:-1][fall] - h[1:][fall])
    result = {'threshold_m': float(threshold_m), 'duration_above_h': float(np.dot(np.diff(t), fraction)),
              'recovery_hour': None, 'hours_after_peak': None, 'status': 'not_exceeded'}
    if above.any():
        if above[-1]:
            result['status'] = 'right_censored'
        else:
            last = int(np.flatnonzero(above)[-1])
            crossing = float(t[last] + (threshold_m - h[last]) * (t[last+1] - t[last]) / (h[last+1] - h[last]))
            peak = int(h.argmax())
            result.update(recovery_hour=crossing, hours_after_peak=float(crossing-t[peak]), status='recovered')
    return result
