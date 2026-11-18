# 道路交通性能退化模型

将南山四种降雨情景、五组排水消退参数的合成积水映射至54条有向道路，不修改40105条路网边及平行边标识。其余40051条边假设原状，不意味着实际无积水；5个未匹配点在上游保留。

速度：w=1000h（mm），v_limit=0.0009w²-0.5529w+86.9448（km/h），来源Pregnolato等2017 DOI 10.1016/j.trd.2017.06.020 PDF第7页Eq.4。h=0返回正常速度v0；0<h<0.30时v=min(v0,max(0,v_limit))。容量独立采用C=C0 max(0.20,1-0.80h/0.30)，单位veh/h。水深h>=0.30 m时速度与容量为0，行程时间导出为inf，弧从可通行集合移除。容量及中断阈值均为项目假设，不能归为原论文结论或官方安全标准。

通行时间t0=3.6L/v（秒），L为m；只表示灾害条件下自由流时间，尚未叠加拥堵。未求解新交通分配，因此不能把容量当作实际流量。

水深退至0.30 m以下即模型重开，没有额外安全检查时延或滞回，不能视为实际道路放行规则。封路事件按端点线性插值计算穿越时刻，临界相等按封路，窗口末仍关闭记右删失；未关闭边不填写恢复时刻。

raw/road_state_timeseries.parquet含5组×4情景×97端点×54边，字段包括u/v/key/edge_id、深度、正常属性、速度、容量、状态、通行性和自由流时间。raw/edge_depth_timeseries.parquet可对接已有水深接口；road_state_summary.csv汇总道路数量与关联边容量属性之和；该和值不等于网络吞吐量。closure_episodes.csv和road_peak_summary.csv记录封路持续时间与恢复。full_network_snapshots.parquet保存基准极端情景0/10.5/16/24小时全40105边快照，unlisted_assumed_dry明确标记缺省假设。routing_edge_checks.csv核对关闭弧从可通行集合中删除。native_chart_data.json保存原生PPT图表全部源值。

源码及配置快照在provenance；manifest与ZIP逐字节可核验，figures保留PNG/SVG。全过程为合成、未经道路积水/速度/容量实测标定的研究模型，未重跑均衡、韧性或治理。

当前结果目录：`data/synthetic/road_performance/20261118T153023_road_performance_ab224c4b`。

运行命令：`.conda-env/python.exe scripts/run_road_performance_process.py --config configs/road_performance_process.yaml`。
