# 操作说明

## 2026-11-18 龙岗合成OD计算

龙岗不含大鹏的483×483合成OD已生成：471个1 km区内分区、12个外部网关，WorldPop 2020面积分摊人口3,172,796.99人。平峰76,147.13、早峰152,294.26、晚峰137,064.83 veh/h；基准全天2,238,725.56车次，低/高为0.7/1.3倍。已输出96个15分钟完整方阵。

出行率0.05、机动车比例0.50、载客率1.25及双向各10%跨界量均为假设。人口同时代理产生与吸引，以重力核exp(−t/1200)和分块IPF配平；早晚峰不代表实测通勤方向。推定深圳图307,426节点/451,801有向弧，尚未认证拓扑。401个分区接入、70个未接入，平峰不可达3,492.31、区内1,946.93 veh/h均保留。外部—外部过境交通不在范围。

136项测试、13项运行检查及独立矩阵/96区间/SHA/ZIP审计通过；并非实测校准。当前包`data/synthetic/longgang_od/20261118T121117_longgang_od_2bf08c94`，方法见[LONGGANG_OD_MODEL.md](LONGGANG_OD_MODEL.md)，阶段报告见docs/PHASE_LONGGANG_OD_REPORT.md。Word/PPT共33页/张，变更1/31及新增32/33已逐页查看，历史2—30页/张逐像素一致；26/18张嵌图、14个原生图表45条序列核验通过。龙岗积水、分配和韧性尚未重算，历史南山结果保持原范围。

以下内容为此前阶段记录，当前需求状态以上述新包为准。

## 2026-11-18 龙岗研究范围剔除大鹏

当前范围为随包440307保留龙岗主面，排除大鹏面。已按用户最新要求筛选7,837条候选道路线及14站5,747条水位记录；其中13个龙岗标签站有5,353条记录，另1站行政区标签冲突。此数量是候选几何与观测子集，不是已建成有向路网或已验证积水。

本批没有官方OD、实测车流或新降雨/水深。路网缺节点拓扑、车道和限速存在缺失，缺少说明书所称motor_all_bbox；边界基准、测站位置与SW零点待核。人口/DSM范围覆盖可复用但尚未完成新裁剪。南山OD、60点积水和R/SUMO结果保留历史，不移名到龙岗；当前phase配置仍属历史南山，不能作为龙岗运行入口。

当前目标见configs/active_research.yaml；接收说明docs/LONGGANG_DATA_INTAKE.md，接收目录`data/processed/longgang_intake/20261118T195824_longgang_intake_079cc253`。10项复制/格式/筛选一致性检查通过，不能替代拓扑或实测标定。Word/PPT已同步为31页/张，变更的第1和31页/张已逐一查看，第2—30页/张与上一审核版逐像素一致；24/16张嵌图、14个原生图表的45条序列与42个图表/工作簿部件核验通过。本轮仅调整研究范围与文档，未重跑交通模型或131项历史模型测试。

以下保留此前含大鹏版本及南山的历史记录，最新范围以本节为准。

## 2026-11-18 龙岗研究区数据接收

研究目标已改为龙岗，采用用户确认的随包440307边界，包含大鹏范围。已接收五份OSM原件并逐份校验，完成9,624条候选道路线及15站6,125条水位记录筛选；其中14个龙岗标签站有5,731条记录，另1站行政区标签冲突。此数量是候选几何与观测子集，不是已建成有向路网或已验证积水。

本批没有官方OD、实测车流或新降雨/水深。路网缺节点拓扑、车道和限速存在缺失，缺少说明书所称motor_all_bbox；边界基准、测站位置与SW零点待核。人口/DSM范围覆盖可复用但尚未完成新裁剪。南山OD、60点积水和R/SUMO结果保留历史，不移名到龙岗；当前phase配置仍属历史南山，不能作为龙岗运行入口。

当前目标见configs/active_research.yaml；接收说明docs/LONGGANG_DATA_INTAKE.md，接收目录`data/processed/longgang_intake/20261118T193729_longgang_intake_fe318c5f`。七项复制/格式/筛选一致性检查通过，不能替代拓扑或实测标定。Word/PPT现为31页/张，封面注明龙岗目标，新增第31页/张；第2—30页/张像素保持一致，14个原生图表和工作簿保持原字节。24/16张嵌图及45条图表序列核验通过。南山原始运行证据不改写；本轮未重跑模型测试，历史131项记录保留。

以下保留南山历史验收记录。

## 2026-11-18 新合成情景交通评估

新合成积水、道路退化和完整OD已接入南山全路网时片用户均衡与韧性评估（基准排水消退组）：四情景×96个15分钟区间，384条指标记录，188次独立求解全部满足相对间隙1e-4，最大9.99e-05，节点守恒最大误差3.64e-12 veh/h。正常R=1，一般/严重/极端R=0.99995800 / 0.99976986 / 0.99958260。

R按96区间起点状态保持加权平均，正常基准逐区间使用同一OD；与旧97端点梯形积分不同。区内和不可达需求保留，全部568人口区保留在可达性分母；v/c使用退化容量。合成数据未经实测标定，独立时片不传递排队，本轮未进行全尺度治理优化或新SUMO仿真。各天气全天未服务量均与正常相同，医院消防覆盖也未变化；较高R仅描述当前54边暴露模型，不能证明真实暴雨影响很小。

131项测试、14项运行一致性检查与全部188个求解状态的独立BPR/间隙/节点守恒/需求记账审计通过；Word/PPT现为30页/张，原27页/张像素一致，新增28—30页/张逐张检查，23/15张源图SHA和14个原生图表45条序列核验通过。

当前结果`data/synthetic/traffic_evaluation/20261118T164429_traffic_process_39b516da`，说明TRAFFIC_PROCESS_MODEL.md，阶段报告PHASE_TRAFFIC_PROCESS_REPORT.md。

```powershell
.conda-env/python.exe scripts/run_traffic_process.py --config configs/traffic_process.yaml
.conda-env/python.exe scripts/audit_traffic_process.py --run data/synthetic/traffic_evaluation/20261118T164429_traffic_process_39b516da --output docs/validation/traffic_process/numerical_audit.json
```

中断可追加`--resume 原运行目录`，要求全部源码和输入SHA与检查点相同，成功运行禁止覆盖。raw/interval_metrics.csv关联state_id与同需求baseline_state_id，states/含边流量/时间/有效容量，od_service/含逐OD服务，accessibility/含全部人口区到设施时间，traces/含迭代过程。图集通过本机index.html查询，完整包不上传Git。

以下保留此前模块与历史验收记录。

## 2026-11-18 道路交通性能退化更新

道路交通性能退化模块已完成：水深驱动速度、独立容量函数与0.30 m中断规则，保留有向平行边。四情景×五参数组×97端点×54条关联边，共104760行道路状态；基准一般/严重/极端最多中断0/12/41条，严重/极端单边最长累计中断4.60/6.53小时。124项测试、14项状态核验、11输入/21输出SHA及ZIP内容核验通过。合成模型未经实测校准，未按新输入重跑交通分配、韧性或治理。

模型说明[ROAD_PERFORMANCE_MODEL.md](ROAD_PERFORMANCE_MODEL.md)，当前运行`data/synthetic/road_performance/20261118T153023_road_performance_ab224c4b`。执行命令：

```powershell
.conda-env/python.exe scripts/run_road_performance_process.py --config configs/road_performance_process.yaml
.conda-env/python.exe scripts/verify_synthetic_data_package.py --package data/synthetic/road_performance/20261118T153023_road_performance_ab224c4b --output docs/validation/road_performance/package_audit.json
```

打开该目录index.html查看速度/容量函数、全过程与10.5小时三情景地图，figures含PNG/SVG，同名ZIP可备份。raw含road_state_timeseries、closure_episodes、road_peak_summary、full_network_snapshots及routing_edge_checks；关闭道路在可通行边集中删除。src/uftr/road_performance.py的traversable_edges返回可对接分配器的成本及容量，仍需单独运行和验收交通分配。

维护Word/PPT当前27页/张；其余40051边假设原状，不据此断言真实无积水。完整输入和结果未随Git上传，新机器先恢复configs所指本机备份。

以下保留此前模块及历史实验记录。

全过程模块命令：`.conda-env/python.exe scripts/run_storm_flood_process.py --config configs/storm_flood_process.yaml`。新结果在`data/synthetic/storm_process/20261118T150315_storm_process_7b2a75f3`，打开index.html查看降雨/水深/超阈值点数及退水敏感性，读取raw/point_threshold_metrics.csv区分recovered、not_exceeded与right_censored。只读核验可运行`.conda-env/python.exe scripts/verify_synthetic_data_package.py --package data/synthetic/storm_process/20261118T150315_storm_process_7b2a75f3`。每次输出新目录；完整ZIP留本机。当前Word/PPT各24页/张。

## 南山合成数据包

本机打开`data/synthetic/scenario_packages/20261118T141443_nanshan_seed42/index.html`查看三张运行图；同名ZIP约50.5 MiB，包含降雨、水深、OD、GIS、字段字典和追溯信息。点深度CSV单位m，三个OD基准矩阵单位veh/h，NPZ的96个矩阵单位为每15分钟期望车次；分配小时率需除0.25，不能直接当路段流量。

在项目环境运行：

```powershell
.conda-env/python.exe scripts/verify_synthetic_data_package.py
.conda-env/python.exe scripts/generate_synthetic_data_package.py --config configs/synthetic_data_package.yaml
```

验证命令只读核验；生成命令创建新包并更新共用content.json，随后需要重新同步和审核Word/PPT。配置控制雨量、时段、空间扰动与假设排水参数。已有Phase04—13运行和界面结果没有使用这次新包，不能当作新情景的评估；正式接入需新配置、新run_id及验收。详见SYNTHETIC_DATA_PACKAGE.md。

工作目录C:/Users/zh/Desktop/git/jiaotong。南山已完成全图用户均衡、24小时/97端点韧性与固定2000辆计划的SUMO抽样；关键性、治理及十种子实验使用三个TAZ的小型真实区域。尚未实施南山全尺度优化，不能宣称全区治理收益或已校准历史灾害预测。

## 安装与运行


```powershell
.conda-env/python.exe -m pytest -q
.conda-env/python.exe -m pip check
.conda-env/python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
.conda-env/python.exe -m uftr.cli run --phase 06
.conda-env/python.exe -m uftr.cli run --phase 07 --config configs/phase07_nanshan.yaml
.conda-env/python.exe -m uftr.cli run --phase 11 --config configs/phase11_fresh.yaml
.conda-env/python.exe -m uftr.cli run --phase 13
.conda-env/python.exe -m uftr.cli reindex
.conda-env/python.exe -m uftr.cli history --phase 10
.conda-env/python.exe experiments/run_all.py --phases 04 05 06 07 08 09 10 11 --include-full-nanshan --dry-run
```

最后一条先检查命令，删除`--dry-run`才执行；包含南山07约22分钟，完整十种子需更久。Phase11默认恢复配置依赖本机失败运行的已完成训练检查点，`phase11_fresh.yaml`才是从零重算。12需要实际浏览器验收文件，13需要数据、历史运行和已验证交付文档，不是只克隆源码即可运行。新增运行保留新run_id，不覆盖历史。


## 界面

打开http://127.0.0.1:8501；按八页查看路网、积水、退化、韧性、可达性、关键道路、治理和实验。时间滑块按15分钟，从0到96；南山积水图和小网治理压力场是独立数据，界面有明确说明。预算/效果按已算方案筛选，K超过6会截断；未计算组合不运行后台新优化。Phase09曲线始终固定种子42/K3/效果0.6。

实验页下载136行完整CSV，界面按实验组筛选表格。来源折叠栏可下载manifest，本机完整图片索引results/index.html；下载的HTML需要与原results路径配套。勿把孤立HTML文件理解为已打包全部图片。

## 复现与备份

GitHub含源码、配置、依赖锁、Word/PPT和小型验收副本。请备份本机整个data与results/runs以及根目录原始资料；源码克隆不带大型输入。按configs路径恢复同名目录，输入指纹见manifest及final_data_inventory.json。测试与pip check通过后先运行06或07小网，南山07约22分钟。11_fresh从零算，11恢复本机失败运行的训练检查点；不要删除该检查点后再用恢复配置。

每次运行新建目录，旧成功或失败不会覆盖。结果和图保存于results/runs/<run_id>/raw、figures、screenshots，日志在logs；查询索引可reindex重建。模型配置变更后要重新生成对应实验，不直接修改历史CSV或图片。13审计依赖既有完整运行、界面验收与交付文件，不能替代新模型的重新验收。

## 报告维护

维护版docs/deliverables/研究方案与阶段进展.docx和开题与阶段进展汇报.pptx来自content.json。Python文档和artifact-tool PPT使用Codex捆绑运行时，见该目录README；图像均有源文件和run_id。原始根PPT/Word不改。24页/24张已完成渲染与旧版逐页像素比对检查，最终图片检查记录和交付指纹在docs/validation及delivery_manifest.json。

监测SW零点与测站地址代理位置未核实；OD、容量、积水、治理成本效果与情景概率未实测标定；人口与OSM年份不同，完整避难所缺失。南山时间效率为15起点抽样，介数32起点抽样。南山SUMO治理集合与风险无交集，灾害与治理结果相同；不据此证明全区治理有效。C/D/E只用种子42，B/F各十种子。GA为可选扩展未实现；G为实际分配效率表，不冒充南山优化耗时。
