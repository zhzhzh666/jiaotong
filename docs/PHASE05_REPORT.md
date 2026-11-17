# Phase 05 实际运行报告

运行 `20261118T003411_p05_ed9ae37d`，命令：`.conda-env\python.exe -m uftr.cli run --phase 05`。

本轮按用户“直接一直继续完成”授权连续推进。原始数据与历史运行不覆盖；字段字典只支持SW单位m和北京时间，路面零点仍待核实。

参数见对应configs；独立审计与验收副本见docs/validation/phase05。

```json
{
  "rows": 20952,
  "closed_rows": 1618,
  "state_counts": {
    "normal": 12507,
    "light": 4734,
    "heavy": 2093,
    "closed": 1618
  },
  "output_directory": "data/synthetic/phase05/20261118T003411_p05_ed9ae37d",
  "closure_threshold_m": 0.3,
  "formula": "Pregnolato 2017 DOI 10.1016/j.trd.2017.06.020 PDF p7 Eq4; capacity is separate project assumption",
  "unaffected_edges": "all edges absent from state table remain at original normal attributes",
  "closure": "removed from traversable network; infinite time in export only"
}
```
