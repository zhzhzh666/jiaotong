# Phase 06 实际运行报告

运行 `20261118T003023_p06_dd3a8f40`，命令：`.conda-env\python.exe -m uftr.cli run --phase 06`。

本轮按用户“直接一直继续完成”授权连续推进。原始数据与历史运行不覆盖；字段字典只支持SW单位m和北京时间，路面零点仍待核实。

参数见对应configs；独立审计与验收副本见docs/validation/phase06。

```json
{
  "sioux": {
    "served_veh_h": 360600.0,
    "unserved_veh_h": 0.0,
    "intrazonal_veh_h": 0.0,
    "total_veh_h": 360600.0,
    "relative_gap": 9.926453833972512e-05,
    "converged": true,
    "node_balance_max_error": 7.275957614183426e-11,
    "elapsed_s": 2.0094181000022218,
    "relative_flow_rmse": 0.0005735962651966626,
    "time_unit": "original TNTP time multiplied by 36 s, flow kept original benchmark unit"
  },
  "osm": {
    "small": {
      "served_veh_h": 43.65980286325988,
      "unserved_veh_h": 0.0,
      "intrazonal_veh_h": 20.672597307412012,
      "total_veh_h": 64.33240017067189,
      "relative_gap": 0.0,
      "converged": true,
      "node_balance_max_error": 3.552713678800501e-15,
      "elapsed_s": 0.0058963999908883125,
      "nodes": 1140,
      "edges": 2247,
      "od_rows": 9,
      "excluded_outside_small_scope_veh_h": 36910.41237698265
    },
    "nanshan": {
      "served_veh_h": 31971.51875405231,
      "unserved_veh_h": 3649.7494337037742,
      "intrazonal_veh_h": 1353.4765893972303,
      "total_veh_h": 36974.74477715332,
      "relative_gap": 1.7041520457153857e-05,
      "converged": true,
      "node_balance_max_error": 2.2737367544323206e-12,
      "elapsed_s": 3.530277300000307,
      "nodes": 20447,
      "edges": 40105,
      "od_rows": 58528,
      "excluded_outside_small_scope_veh_h": 0.0
    }
  }
}
```
