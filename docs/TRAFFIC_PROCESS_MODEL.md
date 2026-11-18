# 南山合成积水与OD交通评估

96 left-endpoint hold intervals, duration-weighted mean of Q over 24 h; same-interval dry-road baseline。

四情景使用完整574×574矩阵的非零OD长表（每时段58528对）；零需求分区在原矩阵/zone_index保留。96个矩阵逐个重放，区间车次除以0.25才是veh/h，未删区内或不可达需求。568个人口区全部保留，可达性分母不删除未接入人口。

每个区间使用已冻结道路状态，正常基准使用完全相同OD。BPR与Frank–Wolfe重新分配，关闭弧不加入最短路图且流量为0。有向平行边独立保留。相同OD和全部道路状态的字节哈希相同时才复用结果，不近似相邻时片。

R=ΣQ[k]Δt/24，采用区间起点保持，与历史97端点梯形积分定义不同。时片间不传递队列，不是完整动态分配。Qs/Qp/Qf沿用项目定义和权重，未服务惩罚14400秒、区内300秒，缺失避难所不补造。v/c使用本时片退化后的容量。

raw/interval_metrics.csv为384区间指标，scenario_summary.csv为R及全天需求去向，assignment_summary.csv为独立求解检查；states保留每次独立求解的边流量/时间/容量/封闭状态，od_service保留逐OD服务与最短路时间，accessibility保留人口区可达性，traces保留迭代过程。state_id与baseline_state_id可追溯同需求正常基准。

中断后可用原配置和--resume 当前目录继续，严格要求全部原输入/源码SHA一致；完整成功运行禁止覆盖。源码、配置、manifest、ZIP和PNG/SVG均保留。

- Synthetic uncalibrated OD and inundation; 54 exposed directed edges, 40051 assumed original
- Static UE per departure interval; no queue carryover, no full dynamic traffic assignment
- Time efficiency uses fixed sampled origins; missing shelters not invented
- New 96-interval integral differs from historical 97-endpoint trapezoid; old results not directly substituted
- No full Nanshan mitigation optimization or new SUMO run in this evaluation

当前运行：`data/synthetic/traffic_evaluation/20261118T164429_traffic_process_39b516da`。

命令：`.conda-env/python.exe scripts/run_traffic_process.py --config configs/traffic_process.yaml`。
