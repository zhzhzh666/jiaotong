# Phase 08 实际运行报告

运行 `20261118T000018_p08_d5053648`，命令：`.conda-env\python.exe -m uftr.cli run --phase 08`。

本轮按用户“直接一直继续完成”授权连续推进。原始数据与历史运行不覆盖；字段字典只支持SW单位m和北京时间，路面零点仍待核实。

本阶段数值适用小型真实路网（三个TAZ、9条正OD，含3条区内未上图项），不是南山全尺度优化。研究窗口外需求在scope字段记录。

参数见对应configs；独立审计与验收副本见docs/validation/phase08。

```json
{
  "scope": {
    "region": "small",
    "nodes": 1140,
    "directed_edges": 2247,
    "od_rows_by_period": {
      "evening_peak": 9,
      "morning_peak": 9,
      "offpeak": 9
    },
    "excluded_outside_small_scope_veh_h": {
      "evening_peak": 66439.11835826385,
      "morning_peak": 73820.82562673351,
      "offpeak": 36910.41237698265
    },
    "represented_population": 64440.75464999674,
    "facility_counts": {
      "hospital": 4,
      "fire_station": 2
    },
    "unavailable_shelter_inventory": true,
    "candidate_physical_roads": 6,
    "candidate_risk_design": "independent synthetic surface-road stress test; sampled from normally used physical groups",
    "efficiency": "time-weighted 1/s, unreachable=0; sampled origin nodes to all graph nodes",
    "efficiency_origins": 3,
    "assignment_count": 1206,
    "max_gap": 0.0,
    "max_node_balance_error": 7.105427357601002e-15,
    "solve_seconds": 4.841108599634026
  },
  "ranking_rows": 6,
  "base_R": 0.9912682261200289,
  "elapsed_s": 14.743398399994476
}
```
