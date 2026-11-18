# 操作说明

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
