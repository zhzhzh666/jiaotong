# 暴雨内涝下城市交通网络韧性评估与优化

基于深圳真实路网的分阶段研究工程。Phase 00—01已验收：环境、论文方法、配置、图片查询及真实OSM有向路网。南山研究窗口20,447节点/40,105边，小区1,140节点/2,247边，Sioux Falls已接入。62项测试通过；内涝、分配、优化、SUMO 和 Streamlit 页面尚未实现。实际命令与限制见docs/PHASE01_REPORT.md。

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
& .\.conda-env\python.exe -m uftr.cli history --phase 01
& .\.conda-env\python.exe -m uftr.cli history --date 2026-11-17 --kind figure
& .\.conda-env\python.exe -m uftr.cli reindex
```

不在根目录执行时，命令增加 `--root C:\Users\zh\Desktop\git\jiaotong`（放在子命令前）。可用 `--config` 指定配置文件。当前接受 `--phase 00` 和 `--phase 01`；Phase 01可用 `--offline-source data/raw/phase01/20261117T192004_p01_d71ec83e` 校验已存原始快照后离线重放。公开下载需要网络。Phase 02以后尚无执行入口。

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

维护的可编辑汇报见 [PPT](docs/deliverables/开题与阶段进展汇报.pptx) 与 [Word](docs/deliverables/研究方案与阶段进展.docx)，当前同步到 Phase 01；已嵌入真实环境验收与两张路网图片，研究模型与后续实验明确标为待实施。原稿留在根目录。每阶段验收后同步更新两份文件，构建与检查方法见 [文档维护说明](docs/deliverables/README.md)。GitHub 尚未上传，待账号认证与远端配置。

PLAN.md 为完整 Phase 00—13 路线及验收；PROGRESS.md 为当前实际进度；DATA_SOURCES.md 说明数据状态；MODEL_ASSUMPTIONS.md 区分论文模型和工程假设；docs/LITERATURE_REVIEW.md 为全文核实记录；EXPERIMENT_LOG.md 保存命令和真实结果。

下一阶段Phase 02，在收到继续指令后获取积水、雨量、DEM、人口和应急POI。OSM下载采用官方map API回退，完整来源、研究窗口、转向限制与速度/容量估计边界见docs/PHASE01_REPORT.md。暂无深圳真实OD及交通韧性结果。
