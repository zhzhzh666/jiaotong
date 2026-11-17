# Phase 10 实际运行报告

运行 `20261118T001529_p10_09f176d5`，命令：`.conda-env\python.exe -m uftr.cli run --phase 10`。

本轮按用户“直接一直继续完成”授权连续推进。原始数据与历史运行不覆盖；字段字典只支持SW单位m和北京时间，路面零点仍待核实。

南山2000辆计划为固定资源抽样，约占原小时率积分的0.184%；不是全天全量交通。小网治理方案与南山风险集无交集，因此南山disaster/optimized相同，不作为全区治理收益证据。两个原有OSM自环只在SUMO中沿原曲线中点拆分，保留一对多映射，原交通图不变。

参数见对应configs；独立审计与验收副本见docs/validation/phase10。

```json
{
  "results": [
    {
      "scenario": "normal",
      "departed": 1267,
      "arrived": 1263,
      "running_at_end": 4,
      "waiting_to_depart_at_end": 0,
      "external_pending_at_end": 0,
      "external_queue_delay_s": 0.3668503150320248,
      "teleport_events": 0,
      "reroute_errors_retained": 0,
      "completed_mean_travel_time_s": 231.00158353127475,
      "total_waiting_time_s": 16.0,
      "elapsed_s": 8.11744109999563,
      "vehicle_balance_departed_minus_arrived_running": 0,
      "region": "small",
      "hourly_rate_integral_expected_vehicles": 1890.241707627824,
      "sampled_total_planned": 1890,
      "resource_limit": 2000,
      "sampling_fraction": 0.9998721287193861,
      "plan_status_counts": {
        "routed": 1267,
        "intrazonal_not_graph_loaded": 623
      },
      "outside_region_demand_excluded_veh_h": {
        "evening_peak": 66439.11835826385,
        "morning_peak": 73820.82562673351,
        "offpeak": 36910.41237698265
      },
      "shared_departure_plan_sha256": "d1337ab176df63486cfad6b58da80afa415318439e9ed94a21f653bd25b0bef7",
      "unrouted_planned": 623,
      "selected_road_groups": [
        "road_05",
        "road_03",
        "road_04"
      ],
      "routed_plan_balance": 0
    },
    {
      "scenario": "disaster",
      "departed": 1267,
      "arrived": 1263,
      "running_at_end": 4,
      "waiting_to_depart_at_end": 0,
      "external_pending_at_end": 0,
      "external_queue_delay_s": 0.3668503150320248,
      "teleport_events": 0,
      "reroute_errors_retained": 0,
      "completed_mean_travel_time_s": 245.93586698337293,
      "total_waiting_time_s": 39.0,
      "elapsed_s": 7.867420399998082,
      "vehicle_balance_departed_minus_arrived_running": 0,
      "region": "small",
      "hourly_rate_integral_expected_vehicles": 1890.241707627824,
      "sampled_total_planned": 1890,
      "resource_limit": 2000,
      "sampling_fraction": 0.9998721287193861,
      "plan_status_counts": {
        "routed": 1267,
        "intrazonal_not_graph_loaded": 623
      },
      "outside_region_demand_excluded_veh_h": {
        "evening_peak": 66439.11835826385,
        "morning_peak": 73820.82562673351,
        "offpeak": 36910.41237698265
      },
      "shared_departure_plan_sha256": "d1337ab176df63486cfad6b58da80afa415318439e9ed94a21f653bd25b0bef7",
      "unrouted_planned": 623,
      "selected_road_groups": [
        "road_05",
        "road_03",
        "road_04"
      ],
      "routed_plan_balance": 0
    },
    {
      "scenario": "optimized",
      "departed": 1267,
      "arrived": 1263,
      "running_at_end": 4,
      "waiting_to_depart_at_end": 0,
      "external_pending_at_end": 0,
      "external_queue_delay_s": 0.3668503150320248,
      "teleport_events": 0,
      "reroute_errors_retained": 0,
      "completed_mean_travel_time_s": 234.77197149643706,
      "total_waiting_time_s": 19.0,
      "elapsed_s": 7.627339899991057,
      "vehicle_balance_departed_minus_arrived_running": 0,
      "region": "small",
      "hourly_rate_integral_expected_vehicles": 1890.241707627824,
      "sampled_total_planned": 1890,
      "resource_limit": 2000,
      "sampling_fraction": 0.9998721287193861,
      "plan_status_counts": {
        "routed": 1267,
        "intrazonal_not_graph_loaded": 623
      },
      "outside_region_demand_excluded_veh_h": {
        "evening_peak": 66439.11835826385,
        "morning_peak": 73820.82562673351,
        "offpeak": 36910.41237698265
      },
      "shared_departure_plan_sha256": "d1337ab176df63486cfad6b58da80afa415318439e9ed94a21f653bd25b0bef7",
      "unrouted_planned": 623,
      "selected_road_groups": [
        "road_05",
        "road_03",
        "road_04"
      ],
      "routed_plan_balance": 0
    },
    {
      "scenario": "normal",
      "departed": 1723,
      "arrived": 1708,
      "running_at_end": 15,
      "waiting_to_depart_at_end": 0,
      "external_pending_at_end": 0,
      "external_queue_delay_s": 0.6377144907928596,
      "teleport_events": 0,
      "reroute_errors_retained": 0,
      "completed_mean_travel_time_s": 629.5058548009367,
      "total_waiting_time_s": 24.0,
      "elapsed_s": 49.192062599991914,
      "vehicle_balance_departed_minus_arrived_running": 0,
      "region": "nanshan",
      "hourly_rate_integral_expected_vehicles": 1087057.4964483078,
      "sampled_total_planned": 2000,
      "resource_limit": 2000,
      "sampling_fraction": 0.001839829085889667,
      "plan_status_counts": {
        "routed": 1723,
        "no_lane_connected_normal_route": 184,
        "intrazonal_not_graph_loaded": 85,
        "missing_connector": 8
      },
      "outside_region_demand_excluded_veh_h": {},
      "shared_departure_plan_sha256": "6b1c6fdfeb5af27c405c9b58f8afd71148cb19def100b0531052ef73f5978332",
      "unrouted_planned": 277,
      "selected_road_groups": [],
      "routed_plan_balance": 0
    },
    {
      "scenario": "disaster",
      "departed": 1723,
      "arrived": 1708,
      "running_at_end": 15,
      "waiting_to_depart_at_end": 0,
      "external_pending_at_end": 0,
      "external_queue_delay_s": 13321.393967409665,
      "teleport_events": 0,
      "reroute_errors_retained": 0,
      "completed_mean_travel_time_s": 633.4830210772834,
      "total_waiting_time_s": 13.0,
      "elapsed_s": 57.192412400007015,
      "vehicle_balance_departed_minus_arrived_running": 0,
      "region": "nanshan",
      "hourly_rate_integral_expected_vehicles": 1087057.4964483078,
      "sampled_total_planned": 2000,
      "resource_limit": 2000,
      "sampling_fraction": 0.001839829085889667,
      "plan_status_counts": {
        "routed": 1723,
        "no_lane_connected_normal_route": 184,
        "intrazonal_not_graph_loaded": 85,
        "missing_connector": 8
      },
      "outside_region_demand_excluded_veh_h": {},
      "shared_departure_plan_sha256": "6b1c6fdfeb5af27c405c9b58f8afd71148cb19def100b0531052ef73f5978332",
      "unrouted_planned": 277,
      "selected_road_groups": [],
      "routed_plan_balance": 0
    },
    {
      "scenario": "optimized",
      "departed": 1723,
      "arrived": 1708,
      "running_at_end": 15,
      "waiting_to_depart_at_end": 0,
      "external_pending_at_end": 0,
      "external_queue_delay_s": 13321.393967409665,
      "teleport_events": 0,
      "reroute_errors_retained": 0,
      "completed_mean_travel_time_s": 633.4830210772834,
      "total_waiting_time_s": 13.0,
      "elapsed_s": 56.547317700009444,
      "vehicle_balance_departed_minus_arrived_running": 0,
      "region": "nanshan",
      "hourly_rate_integral_expected_vehicles": 1087057.4964483078,
      "sampled_total_planned": 2000,
      "resource_limit": 2000,
      "sampling_fraction": 0.001839829085889667,
      "plan_status_counts": {
        "routed": 1723,
        "no_lane_connected_normal_route": 184,
        "intrazonal_not_graph_loaded": 85,
        "missing_connector": 8
      },
      "outside_region_demand_excluded_veh_h": {},
      "shared_departure_plan_sha256": "6b1c6fdfeb5af27c405c9b58f8afd71148cb19def100b0531052ef73f5978332",
      "unrouted_planned": 277,
      "selected_road_groups": [],
      "routed_plan_balance": 0
    }
  ],
  "sumo_version": "Eclipse SUMO sumo 1.28.0",
  "mapping": "plain XML from actual OSM-derived directed MultiDiGraph, exact edge IDs, projected geometry; SUMO generates junction/lane connections",
  "limitations": [
    "No measured signal plans, turn restrictions, lane-level geometry or calibrated car following",
    "BPR capacity was not assigned as SUMO capacity",
    "Full Nanshan SUMO is a resource-limited fixed OD sample; unrouted/intrazonal plans are retained in counts",
    "Nanshan optimized scenario uses only overlap of the small optimized physical roads with full-risk arcs; it is not a Nanshan optimization result"
  ]
}
```
