# 暴雨内涝下城市交通网络韧性评估与优化

基于深圳真实路网的分阶段研究工程。Phase 00已验收：环境、论文方法、配置、运行归档和图片查询；道路、内涝、分配、优化、SUMO 和 Streamlit 页面尚未实现。37项测试通过，20项依赖导入成功，实际结果与命令见docs/PHASE00_REPORT.md。

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
& .\.conda-env\python.exe -m uftr.cli history --phase 00
& .\.conda-env\python.exe -m uftr.cli history --date 2026-11-17 --kind figure
& .\.conda-env\python.exe -m uftr.cli reindex
```

不在根目录执行时，命令增加 `--root C:\Users\zh\Desktop\git\jiaotong`（放在子命令前）。可用 `--config` 指定配置文件。当前只接受 `--phase 00`，后续阶段尚无执行入口。

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

PLAN.md 为完整 Phase 00—13 路线及验收；PROGRESS.md 为当前实际进度；DATA_SOURCES.md 说明数据状态；MODEL_ASSUMPTIONS.md 区分论文模型和工程假设；docs/LITERATURE_REVIEW.md 为全文核实记录；EXPERIMENT_LOG.md 保存命令和真实结果。

下一步仅在 Phase 00 验收且收到继续指令后实施 Phase 01。后续需要 OSM/Overpass 和 TransportationNetworks 公开下载；暂无真实积水、人口和OD输入，缺失时按任务书明确标记替代方案。
