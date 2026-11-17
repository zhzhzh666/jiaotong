# Phase 11 实际运行报告

运行 `20261118T001742_p11_2810fef9`，命令：`.conda-env\python.exe -m uftr.cli run --phase 11`。

本轮按用户“直接一直继续完成”授权连续推进。原始数据与历史运行不覆盖；字段字典只支持SW单位m和北京时间，路面零点仍待核实。

本阶段数值适用小型真实路网（三个TAZ、9条正OD，含3条区内未上图项），不是南山全尺度优化。研究窗口外需求在scope字段记录。

训练种子42—51，独立灾害种子1042—1051与OD种子5042—5051。C/D/E为种子42单因素/消融；G记录真实分配耗时。原运行十训练种子完成后绘图后端失败，恢复已有计算检查点并重跑独立测试，来源指纹见报告。

参数见对应configs；独立审计与验收副本见docs/validation/phase11。

```json
{
  "experiments": "A-G",
  "resumed_numerical_checkpoint": {
    "source_run": "20261118T000318_p11_f3be35ea",
    "numerical_results_sha256": "17ec9ef6fdfc1feb13f4859f869131c004b0975a7a8e58e98b95a2a0a455a000",
    "reason": "all ten training seeds finished; original run failed only during plot backend initialization; held-out cases rerun"
  },
  "training_seeds": [
    42,
    43,
    44,
    45,
    46,
    47,
    48,
    49,
    50,
    51
  ],
  "independent_test_seeds": [
    1042,
    1043,
    1044,
    1045,
    1046,
    1047,
    1048,
    1049,
    1050,
    1051
  ],
  "sensitivity_and_ablation_seeds": [
    42
  ],
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
    "solve_seconds": 7.316765100273187
  },
  "checks": [
    {
      "seed": 42,
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
      "assignment_count": 13755,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 74.06747080056812,
      "elapsed_s": 191.14926879999985
    },
    {
      "seed": 43,
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
      "assignment_count": 3309,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 24.283802099933382,
      "elapsed_s": 69.08085680000659
    },
    {
      "seed": 44,
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
      "assignment_count": 2919,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 22.914012300097966,
      "elapsed_s": 65.60874749999493
    },
    {
      "seed": 45,
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
      "assignment_count": 2757,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 13.040516000735806,
      "elapsed_s": 37.220665000000736
    },
    {
      "seed": 46,
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
      "assignment_count": 3138,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 15.205555899388855,
      "elapsed_s": 42.55055909999646
    },
    {
      "seed": 47,
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
      "assignment_count": 3195,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 14.738645899749827,
      "elapsed_s": 41.045061500000884
    },
    {
      "seed": 48,
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
      "assignment_count": 3195,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 19.169683800224448,
      "elapsed_s": 53.89283350000915
    },
    {
      "seed": 49,
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
      "assignment_count": 3195,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 18.978150399343576,
      "elapsed_s": 53.94799840000633
    },
    {
      "seed": 50,
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
      "assignment_count": 3081,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 14.266595400331425,
      "elapsed_s": 40.20486450000317
    },
    {
      "seed": 51,
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
      "assignment_count": 3138,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 14.404854000124033,
      "elapsed_s": 40.027489300002344
    },
    {
      "heldout_seed": 42,
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
      "assignment_count": 339,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 2.1745419000217225
    },
    {
      "heldout_seed": 43,
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
      "assignment_count": 339,
      "max_gap": 0.0,
      "max_node_balance_error": 1.4210854715202004e-14,
      "solve_seconds": 1.867697800087626
    },
    {
      "heldout_seed": 44,
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
      "assignment_count": 333,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 1.8158828001614893
    },
    {
      "heldout_seed": 45,
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
      "assignment_count": 339,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 1.7308067002013559
    },
    {
      "heldout_seed": 46,
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
      "assignment_count": 333,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 1.692319099776796
    },
    {
      "heldout_seed": 47,
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
      "assignment_count": 327,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 1.6956937001814367
    },
    {
      "heldout_seed": 48,
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
      "assignment_count": 333,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 1.6999848000705242
    },
    {
      "heldout_seed": 49,
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
      "assignment_count": 333,
      "max_gap": 0.0,
      "max_node_balance_error": 0.0,
      "solve_seconds": 1.694900000016787
    },
    {
      "heldout_seed": 50,
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
      "assignment_count": 339,
      "max_gap": 0.0,
      "max_node_balance_error": 7.105427357601002e-15,
      "solve_seconds": 1.745917500113137
    },
    {
      "heldout_seed": 51,
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
      "assignment_count": 345,
      "max_gap": 0.0,
      "max_node_balance_error": 1.4210854715202004e-14,
      "solve_seconds": 2.044075200057705
    }
  ],
  "statistics": [
    {
      "experiment": "B_strategies",
      "strategy": "centrality",
      "n": 10,
      "mean": 0.9943572271436778,
      "std": 0.0019037050040209703,
      "ci95_low": 0.9929953986221205,
      "ci95_high": 0.9957190556652351
    },
    {
      "experiment": "B_strategies",
      "strategy": "depth",
      "n": 10,
      "mean": 0.992792838655007,
      "std": 0.0024678105675191055,
      "ci95_low": 0.9910274733229049,
      "ci95_high": 0.9945582039871091
    },
    {
      "experiment": "B_strategies",
      "strategy": "flow",
      "n": 10,
      "mean": 0.9963640106324518,
      "std": 0.0016887241280495377,
      "ci95_low": 0.9951559701651723,
      "ci95_high": 0.9975720510997313
    },
    {
      "experiment": "B_strategies",
      "strategy": "none",
      "n": 10,
      "mean": 0.9895395263177591,
      "std": 0.0026267884825933578,
      "ci95_low": 0.9876604350362117,
      "ci95_high": 0.9914186175993065
    },
    {
      "experiment": "B_strategies",
      "strategy": "random",
      "n": 10,
      "mean": 0.9932494410158272,
      "std": 0.0026035580100775965,
      "ci95_low": 0.991386967813223,
      "ci95_high": 0.9951119142184315
    },
    {
      "experiment": "B_strategies",
      "strategy": "resilience_greedy",
      "n": 10,
      "mean": 0.9963640106324518,
      "std": 0.0016887241280495377,
      "ci95_low": 0.9951559701651723,
      "ci95_high": 0.9975720510997313
    },
    {
      "experiment": "F_heldout",
      "strategy": "none",
      "n": 10,
      "mean": 0.9885456083086783,
      "std": 0.0021526357400527096,
      "ci95_low": 0.9870057054659923,
      "ci95_high": 0.9900855111513643
    },
    {
      "experiment": "F_heldout",
      "strategy": "trained_greedy",
      "n": 10,
      "mean": 0.9961109247347739,
      "std": 0.0016740213455254745,
      "ci95_low": 0.99491340200451,
      "ci95_high": 0.9973084474650379
    }
  ],
  "heldout_paired_gain_ci95": {
    "n": 10,
    "mean": 0.007565316426095559,
    "std": 0.0008253473624356873,
    "ci95_low": 0.006974898490552517,
    "ci95_high": 0.0081557343616386
  },
  "observed_process_peak_memory_bytes": 433287168,
  "G_assignment_benchmark_source": "results\\runs\\20261117T235309_p06_1ba551f8\\raw\\assignment_report.json",
  "limitations": [
    "Optimization/10-seed suite is on the explicitly scoped small real network, not full Nanshan optimization",
    "Small OD contains three connected TAZ and nine positive pairs, including three intrazonal entries",
    "No calibrated OD, rainfall probability, sensor zero datum or SUMO capacity calibration",
    "CI describes stochastic model realizations; it is not a confidence interval for real Shenzhen resilience"
  ]
}
```
