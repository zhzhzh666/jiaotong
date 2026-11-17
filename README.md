# 暴雨内涝下城市交通网络韧性评估与优化

基于深圳真实路网的分阶段研究工程。Phase 00—03已验收，98项测试通过。已完成真实有向OSM路网、空间数据、568个TAZ及三时段重力/IPF合成OD，并接入45站18123条用户提供水位。需求均未标定，水位零点及地址位置待核实；尚无内涝、分配、韧性或治理结果。见[Phase 03报告](docs/PHASE03_REPORT.md)。

## 安装（Windows PowerShell）

在 `C:\Users\zh\Desktop\git\jiaotong` 执行：

```powershell
conda create --prefix .conda-env --override-channels -c conda-forge python=3.11 pip -y
& .\.conda-env\python.exe -m pip install -r requirements.in
& .\.conda-env\python.exe -m pip install --no-index --disable-pip-version-check --no-build-isolation --no-deps -e .
```

精确复现已验收环境时，用下面的锁文件安装方式替代上面的宽范围依赖安装：

```powershell
conda create --prefix .conda-env --file conda-win-64.lock.txt -y
& .\.conda-env\python.exe -m pip install -r requirements-win-64.lock.txt
& .\.conda-env\python.exe -m pip install --no-index --disable-pip-version-check --no-build-isolation --no-deps -e .
```

锁文件针对Windows x64；其他平台需要重新求解和验收。SUMO 的 Python 接口与 SUMO/netconvert 可执行程序是独立依赖；可执行程序在 Phase 10 检查，本阶段不以接口导入冒充微观仿真可运行。

## 运行和测试

```powershell
& .\.conda-env\python.exe -m uftr.cli check-config
& .\.conda-env\python.exe -m pytest
& .\.conda-env\python.exe -m pip check
& .\.conda-env\python.exe -m uftr.cli run --phase 00
& .\.conda-env\python.exe -m uftr.cli run --phase 01
& .\.conda-env\python.exe -m uftr.cli run --phase 02 --offline-source data/raw/phase02/20261117_source_acquisition
& .\.conda-env\python.exe -m uftr.cli history --phase 02
& .\.conda-env\python.exe -m uftr.cli history --date 2026-11-17 --kind figure
& .\.conda-env\python.exe -m uftr.cli reindex
```

不在根目录执行时，命令增加 `--root C:\Users\zh\Desktop\git\jiaotong`（放在子命令前）。可用 `--config` 指定配置文件。当前接受 `--phase 00`、`--phase 01` 和 `--phase 02`；Phase 01可用 `--offline-source data/raw/phase01/20261117T192004_p01_d71ec83e` 校验已存原始快照后离线重放。公开下载需要网络。Phase 02默认在线下载，或使用上方已封存快照离线重放；需保留配置所指Phase 01原始OSM和处理路网，克隆仓库本身不包含大型数据。Phase 03以后尚无执行入口。

## 图片与结果查询

打开 `results/index.html`，用阶段、日期、区域、情景、策略关键词筛选缩略图；命令行可组合 `--phase --region --scenario --strategy --kind --run-id --date` 精确查询。

每次运行保存：

```text
results/runs/<run_id>/
  config.json            # 实际配置快照
  manifest.json          # 代码版本、输入/图片指纹、时间、状态、来源
  raw/environment.json   # 实际环境和依赖导入结果
  figures/               # PNG及SVG
  screenshots/           # 后续真实界面截图
  logs/                  # 运行及失败记录
```

CSV/HTML索引可重建；历史运行不覆盖、不自动删除。results大文件未纳入Git，需要另行备份整个运行目录才能保留所有结果。原始论文也保留在本机根目录，源码仓库保存其指纹。

## 文档和后续步骤

维护的可编辑汇报见 [PPT](docs/deliverables/开题与阶段进展汇报.pptx) 与 [Word](docs/deliverables/研究方案与阶段进展.docx)，当前同步到 Phase 03；19页Word、24张PPT，嵌入环境、路网、空间数据、合成OD及水位共12张运行图片，研究模型与后续实验明确标为待实施。原稿留在根目录。每阶段验收后同步更新两份文件，构建与检查方法见 [文档维护说明](docs/deliverables/README.md)。项目已上传至 [GitHub](https://github.com/zhzhzh666/jiaotong)，main保留全部本地阶段提交及远端初始化历史；原始论文、环境与大型数据仍在本机。

PLAN.md 为完整 Phase 00—13 路线及验收；PROGRESS.md 为当前实际进度；DATA_SOURCES.md 说明数据状态；MODEL_ASSUMPTIONS.md 区分论文模型和工程假设；docs/LITERATURE_REVIEW.md 为全文核实记录；EXPERIMENT_LOG.md 保存命令和真实结果。

下一阶段Phase 04，在收到继续指令后实施24 h/15 min参数化内涝时序。实测深圳OD、完整避难所与本地细时序雨量仍缺，SW疑似积水深度但零点未核实；不宣称历史灾害重建。

## Phase 03 已验收 2026-11-17

最终运行20261117T215510_p03_ab17de87，实现提交410a526224966d7ac30203049978823185876038、dirty=false，36.3785秒。98项测试通过、44条rasterio/affine未来弃用警告，pip check无冲突。568个1000 m裁剪TAZ，236个正产生/吸引TAZ；193个区内道路接入、43个未接入，未删需求；6个真实跨界外部节点。保留233个WorldPop原生像元的1540614.3657147214估计人数。平/早/晚峰总量36974.744777/73949.489554/66554.540599 veh/h，全部为未标定合成小时率原型；每时段58528非零OD对。IPF最大相对边际误差9.64608e-10，最大绝对误差6.891502e-7 veh/h。区内未上图与正常不可达需求单列，原MultiDiGraph不改动。

水位来源由用户确认：深圳市政府数据开放平台抓取，高水位日期筛选，平台地址经高德地理编码。45站、18123条记录；6站/2393条在研究边界，1条东莞POI匹配方式可疑。用户确认0.15/0.30/0.40 m蓝黄橙红分级；SW路面零点仅为“平时近零”的推测，平台未明确，保留raw值，不直接作为道路积水深度。六个原始CSV/ZIP在根目录和sealed snapshot保持字节不变，未纳入Git。

独立审计、5图/55输入/114索引链接校验通过，11项关键输出与首轮成功运行逐字节一致。5张实际PNG逐张查看并保存到docs/validation/phase03；Word19页、PPT24张全部渲染检查，12张嵌入源图字节核验，原稿指纹不变。报告和命令见docs/PHASE03_REPORT.md。下一阶段为Phase 04，本阶段结束停止，收到继续指令再实施。

复现Phase 03：`.conda-env/python.exe -m uftr.cli run --phase 03 --user-source data/raw/user_sources/20261117T215014_p03_2b8fe770`。首次接入时六个用户文件须放项目根目录，可省略--user-source。大型输入未在Git中，须使用本地封存目录；下载代码不会自动取得这些数据。
