# Phase 00 实施与验收报告

日期：2026-11-17，Asia/Shanghai。结论：Phase 00通过；Phase 01—13未开始。

## 已实现与文件清单

- 项目根目录独立Git仓库；Python 3.11.18独立Conda环境`.conda-env`。没有修改系统/base环境或用户原始论文/PPTX/DOCX。
- `pyproject.toml`、`environment.yml`、`requirements.in`、`conda-win-64.lock.txt`、`requirements-win-64.lock.txt`：安装入口与实际依赖锁。
- `src/uftr/`：配置和单位校验、97端点时间网格、实际环境采集、运行归档、图片来源/指纹、CSV/HTML索引、命令行运行与查询。
- `configs/phase00.yaml`、`tests/`：固定种子及参数，配置、归档、失败恢复、CLI、20项依赖和GIS/Parquet读写测试。
- `scripts/`：本地论文提取/关键页渲染、在线元数据核实、已保存运行完整性审计。
- 根目录七份管理文档已建立并更新；`docs/TASK_SPEC.md`保留任务原文；`docs/LITERATURE_REVIEW.md`记录5篇全文方法、公式、单位及与本项目的区别；`docs/references/`保存来源核实记录。
- `docs/validation/`保存实际测试日志/XML、pip检查、环境JSON、运行manifest和验收PNG/SVG副本；大型完整运行存于`results/runs/`。

## 实际执行的主要命令

工作目录：`C:\Users\zh\Desktop\git\jiaotong`。

```powershell
conda create --prefix .conda-env --override-channels -c conda-forge python=3.11 pip -y
uv pip install --python .conda-env\python.exe -r requirements.in
& .\.conda-env\python.exe -m pip install --no-index --disable-pip-version-check --no-build-isolation --no-deps -e .
& .\.conda-env\python.exe -X utf8 scripts/inspect_literature.py
& .\.conda-env\python.exe -X utf8 scripts/render_reference_pages.py
python -X utf8 scripts/verify_references.py
python -X utf8 scripts/verify_publisher.py
conda list --prefix .conda-env --explicit
& .\.conda-env\python.exe -m pip freeze --exclude-editable
& .\.conda-env\python.exe -m uftr.cli check-config
& .\.conda-env\python.exe -m pytest --junitxml=docs/validation/pytest-final.xml
& .\.conda-env\python.exe -m pip check
& .\.conda-env\python.exe -m uftr.cli run --phase 00
& .\.conda-env\python.exe -m uftr.cli history --phase 00 --run-id 20261117T173510_p00_a2d49eb6 --kind figure
& .\.conda-env\python.exe -m uftr.cli reindex
& .\.conda-env\python.exe -X utf8 scripts/audit_run.py --run-id 20261117T173510_p00_a2d49eb6
```

`conda list`和`pip freeze`输出已分别写入锁文件；pytest原始输出另存validation/pytest-final.txt。Git初始化和分阶段提交在本项目内执行；账号变化时Git命令使用仅对本目录生效的命令级safe.directory参数，未修改全局信任。

## 实际运行结果

| 检查 | 实际结果 |
| --- | --- |
| Python | 3.11.18，独立环境 |
| CPU/GPU | 24逻辑处理器；RTX4060 Laptop，8188 MiB显存 |
| Python依赖 | 20/20实际导入成功 |
| pytest | 37通过；0失败；1条rasterio/affine未来弃用警告；最终复核6.32秒 |
| pip check | No broken requirements found |
| 默认时间配置 | 24小时/15分钟，97端点、96区间 |
| 首次运行 | 20261117T172555_p00_0dcd60c4，5.2153秒，成功 |
| 最终复核运行 | 20261117T173510_p00_a2d49eb6，6.2704秒，成功 |
| 最终运行源码 | 0e0b56219e00b736621cc89b9bf33068d8473fd5，运行时git dirty=false |
| 最终运行图片 | 1张PNG、1张SVG，均来自实际环境JSON |
| 归档完整性 | 本次2个图片、6个输入指纹验证成功；两次运行共14个索引链接存在 |
| 历史保留 | 两次运行目录均保留，索引包含4条PNG/SVG记录，没有覆盖第一次结果 |

已通过的测试包括：无效单位/坐标/权重/时间步长拒绝；固定种子复现；同时间创建运行目录不冲突；失败时保留结果与traceback；图片防目录越界和防重复登记；HTML转义、中文文件名链接、CSV重建；自定义输出目录与CLI过滤；拒绝未实现Phase；米制投影、GeoJSON、Parquet、GeoTIFF实际读写。

## 图片查看与查询

- 本地查询入口：[运行图片索引](../results/index.html)。可按阶段、日期、区域、情景、策略输入关键词。
- 本次原始图片：[PNG](../results/runs/20261117T173510_p00_a2d49eb6/figures/environment_check.png)、[SVG](../results/runs/20261117T173510_p00_a2d49eb6/figures/environment_check.svg)。
- 版本化验收副本：[环境检查图](validation/environment_check.png)、[原始环境JSON](validation/environment.json)、[运行记录](validation/accepted-run-manifest.json)、[指纹审计](validation/run_audit.json)。

两次运行PNG均已实际查看，标题、坐标轴、图例和数值无裁切重叠。页面索引完成文件链接检查和CLI查询验收；Streamlit真实界面及其浏览器交互验收在Phase 12实施。

## 论文核查结论与当前问题

5篇PDF均已从本地读取，不需要再次下载。4篇英文Crossref书目信息核实成功；中文论文Crossref404、期刊页面HTTP500，但本地12页全文完整可读，已据首页及方法页核对。没有将网络失败当成论文不存在。

已记录不同论文15/30 cm中断阈值、不同速度模型、韧性损失与平均性能方向的区别。Land Eq.(18)常数+0.04与Table 5的-0.04不一致，已对照图像记录，不直接用于深圳模型。

SUMO、sumo-gui、netconvert尚未在PATH发现，sumolib/traci导入成功不能替代可执行程序安装。真实路网、积水、降雨、DEM、人口、POI和OD仍未获取；尚无任何交通韧性或治理实验结果。

## 下一阶段输入

下一步为Phase 01：公开OSM/Overpass访问、南山区边界与小测试区域配置、TransportationNetworks SiouxFalls标准文件。先确认小区域真实路网与方向/属性/连通性，再扩展南山区。不需要用户重新提供已有论文。

本次到此停止，不提前实现后续模型。
