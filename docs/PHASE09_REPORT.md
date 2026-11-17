# Phase 09 实际运行报告

运行 `20261118T000031_p09_db4b0eb2`，命令：`.conda-env\python.exe -m uftr.cli run --phase 09`。

本轮按用户“直接一直继续完成”授权连续推进。原始数据与历史运行不覆盖；字段字典只支持SW单位m和北京时间，路面零点仍待核实。

本阶段数值适用小型真实路网（三个TAZ、9条正OD，含3条区内未上图项），不是南山全尺度优化。研究窗口外需求在scope字段记录。

参数见对应configs；独立审计与验收副本见docs/validation/phase09。

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
    "assignment_count": 7191,
    "max_gap": 0.0,
    "max_node_balance_error": 7.105427357601002e-15,
    "solve_seconds": 34.26009789950331
  },
  "strategies": [
    {
      "strategy": "none",
      "R": 0.9912682261200289,
      "selected": "",
      "selected_count": 0,
      "spent": 0.0,
      "budget": 3.0,
      "K": 3,
      "effect": 0.6,
      "seed": 42,
      "runtime_s": 1.0299991117790341e-05,
      "scenarios": "general,severe,extreme"
    },
    {
      "strategy": "random",
      "R": 0.9922231634870581,
      "selected": "road_02|road_04|road_01",
      "selected_count": 3,
      "spent": 3.0,
      "budget": 3.0,
      "K": 3,
      "effect": 0.6,
      "seed": 42,
      "runtime_s": 2.0348892000038177,
      "scenarios": "general,severe,extreme"
    },
    {
      "strategy": "depth",
      "R": 0.9926956308537506,
      "selected": "road_02|road_03|road_00",
      "selected_count": 3,
      "spent": 3.0,
      "budget": 3.0,
      "K": 3,
      "effect": 0.6,
      "seed": 42,
      "runtime_s": 1.9218317000049865,
      "scenarios": "general,severe,extreme"
    },
    {
      "strategy": "flow",
      "R": 0.9971560091494998,
      "selected": "road_05|road_04|road_03",
      "selected_count": 3,
      "spent": 3.0,
      "budget": 3.0,
      "K": 3,
      "effect": 0.6,
      "seed": 42,
      "runtime_s": 2.0125251000135904,
      "scenarios": "general,severe,extreme"
    },
    {
      "strategy": "centrality",
      "R": 0.9956974486746625,
      "selected": "road_02|road_05|road_01",
      "selected_count": 3,
      "spent": 3.0,
      "budget": 3.0,
      "K": 3,
      "effect": 0.6,
      "seed": 42,
      "runtime_s": 2.151522800006205,
      "scenarios": "general,severe,extreme"
    },
    {
      "strategy": "resilience_greedy",
      "R": 0.9971560091494998,
      "selected": "road_05|road_03|road_04",
      "selected_count": 3,
      "spent": 3.0,
      "budget": 3.0,
      "K": 3,
      "effect": 0.6,
      "seed": 42,
      "runtime_s": 17.429812500005937,
      "scenarios": "general,severe,extreme"
    }
  ],
  "exhaustive_R": 0.9971560091494998,
  "exhaustive_sets": 42,
  "greedy_absolute_gap": 0.0,
  "elapsed_s": 96.26386849999835
}
```
