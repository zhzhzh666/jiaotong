# Phase 01 真实路网获取与建模验收

2026-11-17，工作目录 `C:\Users\zh\Desktop\git\jiaotong`。Phase 00—01 已验收；Phase 02—13 未开始。本阶段完成小区域、南山研究窗口真实 OSM 有向路网及 Sioux Falls 数据接入，没有运行交通分配、内涝、韧性或治理优化。

## 数据与范围

南山边界经 Nominatim 查询并核实 OSM relation 5664195。原生 OSMnx/Overpass 下载遇主端点502、其他端点超时或504，因此改用官方只读 OSM map API 分块取得 XML，再由 OSMnx 公开 XML 接口建图。下载配置为0.04°分块、每请求至少间隔1秒、超时60秒、最多240请求，遇节点上限自适应细分。南山实际68次请求含3次节点超限，小区域另1次请求。保存原始响应、来源、访问时间与 SHA256；不把该流程表述为原生 Overpass 下载成功。

- Nominatim：<https://nominatim.openstreetmap.org/search>
- OSM：<https://api.openstreetmap.org/api/0.6/map>，© OpenStreetMap contributors，ODbL 1.0，<https://www.openstreetmap.org/copyright>。
- 原始快照：`data/raw/phase01/20261117T192004_p01_d71ec83e/`，约146 MB；其中 `source_inventory.json` 是重放输入合同。
- 完整行政多边形含大片海域，直接截取包含17条港珠澳大桥相关有向边。主实验采用原边界与 `[113.69,22.35,114.03,22.66]` 的交集，保留内伶仃等所有窗口内分量。此为显式研究窗口，不是官方陆地边界；跨边界相邻道路按配置保留。完整行政范围图仍在处理目录，排除边ID、OSM ID、名称见 `full_osm_administrative_scope/scope_exclusions.json`。
- 小区域 bbox：`[113.925,22.528,113.945,22.545]`，深大附近。下载带500 m缓冲后截取，减少边界拓扑缺失。

## 实际输出

| 指标 | 小区域 | 南山研究窗口 |
| --- | ---: | ---: |
| 节点 | 1,140 | 20,447 |
| 有向边 | 2,247 | 40,105 |
| 弱连通分量 | 3 | 33 |
| 强连通分量 | 62 | 419 |
| 最大弱连通分量节点 | 1,114 | 19,279 |
| 最大强连通分量节点 | 1,019 | 18,811 |
| 平行有向节点对 | 0 | 6 |
| 单向边 | 369 | 7,429 |
| OSM限速字段可用边 | 16 | 1,024 |
| 按道路类型估计速度边 | 2,231 | 39,081 |
| 容量估计边 | 2,247 | 40,105 |
| 20起点可达对核查 | 19,530 | 362,300 |

完整行政范围为20,468节点、40,122边；研究窗口排除17边、21节点，未按最大连通分量删图，未补造道路。每区保存 GraphML、节点/边 GeoJSON、道路属性 CSV、统计、研究边界及 PNG；运行目录另有 SVG。CSV保留 `(u,v,key)`、稳定 `edge_id`、道路级别、OSM标签与各字段来源。

WGS84保存位置，EPSG:32650计算米制几何长度。原始方向、反向单行、方向性车道及限速已核查；MultiDiGraph保留平行边、自环和断连分量。示例红线为按估计自由流时间得到的实际可达最短路，保留选用的边key；它不是交通分配或导航合规性证明。OSM转向限制关系、条件通行与信号延误尚未建模。

自由流速度采用可解析 OSM maxspeed 或配置的道路类型默认值，属于自由流代理；容量均为方向车道数乘配置单车道容量的估计，未实测或标定。双向总车道拆分和缺失车道默认均逐字段标记；不可将这些值称为观测交通数据。双向边长度相加也不等于不重复的物理道路总长。

## Sioux Falls

上游 `bstabler/TransportationNetworks` 固定提交 `d1639b4ef218c17928ba573e806ddf8ba5e7ae6d`。取得 net、trips、node、flow、两个 README 及来源记录，解析24节点、76有向弧、576个OD条目，其中528非零，总需求360600（保留原始单位）；强连通且全对可达。24个坐标、76条外部参考流量已验证。

上游说明自由流时间单位为0.01小时；length人为等于自由流时间，并非米；需求为原始日流量的0.1，上游称近似小时流量；坐标为人工示意。参考流量为下载的外部最佳已知解，项目尚未运行求解器。上游捐赠数据限学术研究，不能称MIT或公有领域数据；原始文件留本地，公开前遵守上游条款。基准来源：<https://github.com/bstabler/TransportationNetworks/tree/d1639b4ef218c17928ba573e806ddf8ba5e7ae6d/SiouxFalls>。

## 执行与验收

```powershell
& .\.conda-env\python.exe -u -X utf8 -m uftr.cli run --phase 01
& .\.conda-env\python.exe -u -X utf8 -m uftr.cli run --phase 01 --offline-source data/raw/phase01/20261117T192004_p01_d71ec83e
& .\.conda-env\python.exe -X utf8 -m pytest --junitxml=docs/validation/phase01/pytest-accepted.xml
& .\.conda-env\python.exe -m pip check
& .\.conda-env\python.exe -X utf8 scripts/audit_run.py --run-id 20261117T193651_p01_2e554d34 --output docs/validation/phase01/run_audit.json
& .\.conda-env\python.exe -X utf8 scripts/audit_network.py --run-id 20261117T193651_p01_2e554d34 --compare-run 20261117T192004_p01_d71ec83e --output docs/validation/phase01/network_audit.json
```

最终验收运行 `20261117T193651_p01_2e554d34`，离线校验原始输入后重放，success，99.9249秒；源实现 `e8115197f63b0f926165406f4ec4c308d77d9bc0`，运行时dirty=false。处理目录 `data/processed/phase01/20261117T193651_p01_2e554d34/`。

62项测试通过，0失败，1条已有rasterio/affine未来弃用警告；pip check无冲突。独立审计核对所有42,352条道路几何端点及投影长度、7,747条可比原始单行顺序、34,554条双向对应边，GraphML/CSV/GeoJSON一致，稳定ID和共同边属性与初次下载一致。审计21项输出，归档校验4个图像格式文件、171个输入与42个历史索引链接。两个PNG最终版本已逐张查看，无裁切或文字重叠。

修复过程：反向单行 `oneway=-1` 在OSMnx内部先翻转节点，已据原始标签纠正方向属性；保留孤立环岛；审查行政海域范围并记录排除清单。离线重放 `20261117T193355_p01_d6c1cd1a` 因Windows XML换行差异失败，已修正为换行归一化比较，保留原始字节并增加回归测试；失败目录不删除。旧61项日志为换行回归测试加入前记录，最终以 `pytest-accepted.*` 为准。

## 图片与后续

最终PNG、manifest、统计、报告和来源清单的版本化副本见 `docs/validation/phase01/`，哈希见 `acceptance_inventory.json`。大体量原始数据、GraphML/GeoJSON和SVG继续保存在本机，备份时须一起保存 `data/` 与 `results/runs/`。浏览 `results/index.html` 或执行 `history --phase 01 --kind figure` 可查询。PPT 13张、Word 9页同步到本阶段，全部逐页查看，三个嵌入PNG与源图哈希一致；根目录原稿和论文指纹不变。

下一阶段为 Phase 02：获取并审计真实积水、雨量、DEM、人口和应急设施POI，记录缺失、许可、时间与关联置信度。暂无深圳真实OD、交通韧性或优化结论。GitHub尚缺认证与远端，未上传；本阶段保存本地Git提交后停止，等待继续指令。
