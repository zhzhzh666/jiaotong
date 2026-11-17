# Phase 04 实际运行报告

运行 `20261118T003010_p04_b90874cf`，命令：`.conda-env\python.exe -m uftr.cli run --phase 04`。

本轮按用户“直接一直继续完成”授权连续推进。原始数据与历史运行不覆盖；字段字典只支持SW单位m和北京时间，路面零点仍待核实。

参数见对应configs；独立审计与验收副本见docs/validation/phase04。

```json
{
  "endpoints": 97,
  "intervals": 96,
  "affected_directed_edges": 54,
  "rows": 20952,
  "source_kind": "synthetic_parameterized",
  "not_historical_reconstruction": true,
  "unit_m_and_timezone_supported_by_user_dictionary": true,
  "observed_zero_datum_verified": false,
  "scenario_peak_m": {
    "extreme": 0.7957634374610573,
    "general": 0.2586231171748436,
    "normal": 0.0,
    "severe": 0.4973521484131608
  },
  "output_directory": "data/synthetic/phase04/20261118T003010_p04_b90874cf"
}
```
