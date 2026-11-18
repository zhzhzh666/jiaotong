# 实验记录：当前验收与完整历史

## 2026-11-18 Word与PPT同步至龙岗蓄水情景

专门文档聊天已将已核实龙岗独立蓄水桶结果及真实管网资料条件同步至维护版Word37页、PPT37张。新增第34—36节说明降雨蓄水步骤、4,139个代理单元与道路关联、恢复和参数敏感性，第37节说明C方案所需资料与尚未实施的状态。来源运行及141项测试、17项检查、20组独立审计均可追溯，数值仍是未标定合成压力情景，未重算龙岗交通影响。

37页/张均已渲染，改动1/33及新增34—37已逐一查看，其余2—32与上一已审版本逐像素一致；29/21张源图和14个原生图表45条序列核验通过，42个历史图表/工作簿部件保留原字节。原稿未改写。本轮文档维护没有重跑模型测试或仿真，141项为所引用模型运行的既有验收记录。后续ERA5/Open-Meteo逐时雨量与B地表汇流工作仍在推进，待独立核对新成果后另行同步。


## 2026-11-18 B方案历史降雨数据核查

已实际取得龙岗附近单个ERA5网格2023-09-07至09-09的72条逐小时再分析降水记录，0缺值；该样例不是站点实测或全区平均。已确认深圳气象局自动站查询与NASA半小时IMERG入口，尚未取得其历史站点/卫星文件。来源、样例、许可与接入步骤见[降雨数据核查](docs/LONGGANG_RAINFALL_DATA_AVAILABILITY.md)。仅保存可获取性样例和核验记录，B/C模型均未运行，旧合成输入及结果保持不变。


## 2026-11-18 C方案真实排水管网公开渠道核查

本轮未核实到可直接下载、覆盖龙岗（不含大鹏）且字段完整的真实雨水管网；这不等于数据不存在。已核实官方管渠统计、数据质检工具入口及依申请公开指南，开放平台详情/搜索未正常显示内容。核查来源、字段清单、未提交的申请草案与C方案实施步骤见[管网数据核查](docs/LONGGANG_DRAINAGE_DATA_AVAILABILITY.md)。未取得真实管井数据，未运行SWMM/二维模型，现有合成蓄水桶结果保持原方法和适用范围。本轮仅文档更新，Word/PPT由专门文档聊天维护。


## 2026-11-18 龙岗暴雨内涝情景

已完成龙岗不含大鹏的合成降雨—蓄水—退水情景：4,139个250 m道路网格代理，6,848个地面源线要素建模，952个桥隧或非零layer保持未知NaN。四档参考雨量0/100/200/300 mm，五组参数，96区间/97端点；基准最大水深0.2613/0.5439/0.8266 m。与OD推定图86,807条弧的保存ID精确对应，426条跨界弧标记。

方法是合成道路低点＋动态蓄水桶，更接近A的参数化扩展，未使用已核实历史积水点，未实现B地表汇流或C管网二维耦合。所有参数未经实测标定。141项测试、17项运行核验与20组独立水量/道路聚合/SHA/ZIP审计通过，5分钟复核最大端点差异1.23 cm。仅完成情景输入，未重算道路速度/容量、交通分配、韧性或SUMO。

当前包`data/synthetic/longgang_storm/20261118T124853_longgang_storm_7e7668c1`。方法步骤见`docs/LONGGANG_STORM_MODEL.md`，阶段报告见`docs/PHASE_LONGGANG_STORM_REPORT.md`。大型数据保留本机，代码、配置、说明与核验记录上传GitHub；Word/PPT由专门文档聊天负责，本轮不改写。以下保留此前阶段记录。

## 2026-11-18 龙岗合成OD计算

龙岗不含大鹏的483×483合成OD已生成：471个1 km区内分区、12个外部网关，WorldPop 2020面积分摊人口3,172,796.99人。平峰76,147.13、早峰152,294.26、晚峰137,064.83 veh/h；基准全天2,238,725.56车次，低/高为0.7/1.3倍。已输出96个15分钟完整方阵。

出行率0.05、机动车比例0.50、载客率1.25及双向各10%跨界量均为假设。人口同时代理产生与吸引，以重力核exp(−t/1200)和分块IPF配平；早晚峰不代表实测通勤方向。推定深圳图307,426节点/451,801有向弧，尚未认证拓扑。401个分区接入、70个未接入，平峰不可达3,492.31、区内1,946.93 veh/h均保留。外部—外部过境交通不在范围。

136项测试、13项运行检查及独立矩阵/96区间/SHA/ZIP审计通过；并非实测校准。当前包`data/synthetic/longgang_od/20261118T121117_longgang_od_2bf08c94`，方法见[LONGGANG_OD_MODEL.md](docs/LONGGANG_OD_MODEL.md)，阶段报告见docs/PHASE_LONGGANG_OD_REPORT.md。Word/PPT共33页/张，变更1/31及新增32/33已逐页查看，历史2—30页/张逐像素一致；26/18张嵌图、14个原生图表45条序列核验通过。龙岗积水、分配和韧性尚未重算，历史南山结果保持原范围。

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

当前结果`data/synthetic/traffic_evaluation/20261118T164429_traffic_process_39b516da`，说明docs/TRAFFIC_PROCESS_MODEL.md，阶段报告docs/PHASE_TRAFFIC_PROCESS_REPORT.md。

命令`.conda-env/python.exe scripts/run_traffic_process.py --config configs/traffic_process.yaml`。初测发现Series不支持get_indexer，改从权威edge_id索引定位，失败JUnit保留，修复后131项全套通过。原assignment.py/resilience.py算法未改；新接口纠正本轮v/c统计的容量口径。独立审计从存储OD最短路费用重放相对间隙，从弧流与已服务OD重放节点守恒，避免仅复述求解器标志。

文档继续采用后台Word只读COM导PDF、pypdfium2渲染，PPT使用Artifact Tool导入追加原生图表，原10个图表与XLSX逐字节保留。未声称原生PowerPoint播放验收。

以下保留此前模块与历史验收记录。

## 2026-11-18 道路交通性能退化更新

执行`.conda-env/python.exe scripts/run_road_performance_process.py --config configs/road_performance_process.yaml`，最终运行`20261118T153023_road_performance_ab224c4b`。道路交通性能退化模块已完成：水深驱动速度、独立容量函数与0.30 m中断规则，保留有向平行边。四情景×五参数组×97端点×54条关联边，共104760行道路状态；基准一般/严重/极端最多中断0/12/41条，严重/极端单边最长累计中断4.60/6.53小时。124项测试、14项状态核验、11输入/21输出SHA及ZIP内容核验通过。合成模型未经实测校准，未按新输入重跑交通分配、韧性或治理。

首轮发现GeoJSON未保留u/v/key，失败输出保留，改从权威GraphML关联恢复并加入对应测试，不从几何猜测方向。成功初版保留；最终版改善地图图幅，快照明确标注synthetic。既有flood.py函数和历史manifest均未修改。

PPT首版因x数值含超过15位有效精度未通过工作簿校验，改为图表x/y均取12位有效数字，仅用于显示缓存，全部29条序列按1e-10容差与原源值核对。v1失败稿保留，v2通过。六个既有图表XML与XLSX逐字节保留，四个新增图表具可编辑工作簿。

维护Word/PPT现为27页/张，新增三节，原24页/张像素一致；20/14张源图SHA匹配，10个原生图表29条序列与源值逐值核验。当前说明见docs/ROAD_PERFORMANCE_MODEL.md，阶段报告见docs/PHASE_ROAD_PERFORMANCE_REPORT.md。后台Word只读COM导PDF，捆绑pypdfium2逐页渲染；PPT最终文件Artifact Tool重新导入渲染。新增25—27页/张逐一打开检查，前24页/张像素一致。没有声称原生PowerPoint播放验收。

以下保留此前模块及历史实验记录。

全过程补充运行`20261118T150315_storm_process_7b2a75f3`，命令`.conda-env/python.exe scripts/run_storm_flood_process.py --config configs/storm_flood_process.yaml`。基准重放最大误差3.886e-16 m，区间/事件平衡误差1.101e-13/9.095e-13 mm；115测试通过、pip check无冲突。四雨量情景五参数组，阈值0/0.01/0.15/0.30/0.40 m逐点统计，未超过和右删失留空恢复时刻。此前探索输出保留；修正了汇总JSON空值和相对配置路径。PPT导入曾丢失旧图表XLSX，后按源文件逐字节保留原图表及工作簿，并修正包命名空间；失败v1/v2保留。最终v4通过全部结构/图表/字体/重导入核验；24页/张中原22页/张像素相同，新增23/24逐张检查。尚未验收原生PowerPoint播放，也未重跑交通评估。

## 2026-11-18 南山合成输入补充

用户无法下载相关数据，授权模拟积水点、降雨和OD。执行`.conda-env/python.exe scripts/generate_synthetic_data_package.py --config configs/synthetic_data_package.yaml`，最终包`20261118T141443_nanshan_seed42`（较早141243版本保留）。60点、四情景、24h/15min、574×574完整OD、96区间、全天793108.2755期望车次；16项一致性检查通过，最大事件水量残差9.095e-13 mm。完整包和53,003,982字节ZIP保留本机，10输入/38输出SHA与ZIP成员一致性独立核验通过。

三张PNG/SVG已查看；Word22页/PPT22张完成渲染核验。原19页Word和17张旧幻灯片PNG与上一验收版字节一致，变化的第2/3张及新增20—22页/张逐张查看。长来源路径和孤字换行已修复。Word15张/PPT13张源图字节一致，PPT三图的7条序列与CSV逐值一致，原稿SHA不变。PPT曾因类别标签、验证回执与输出同目录失败，修复后v3通过，失败稿保留在.cache；未声称原生PowerPoint播放已验收。核心模型未改，本轮未重跑此前106项核心测试或Phase04—13仿真；合成包不代表实测标定。

2026-11-18：Phase 00—13按上述实际范围完成研究原型与最终审计；106项测试通过、44条既有弃用警告，pip check无冲突。南山已完成全图用户均衡、24小时/97端点韧性与固定2000辆计划的SUMO抽样；关键性、治理及十种子实验使用三个TAZ的小型真实区域。尚未实施南山全尺度优化，不能宣称全区治理收益或已校准历史灾害预测。

| 阶段 | run_id |
| --- | --- |
| 04 | `20261118T003010_p04_b90874cf` |
| 05 | `20261118T003411_p05_ed9ae37d` |
| 06 | `20261118T003023_p06_dd3a8f40` |
| 08 | `20261118T000018_p08_d5053648` |
| 09 | `20261118T000031_p09_db4b0eb2` |
| 10 | `20261118T001529_p10_09f176d5` |
| 11 | `20261118T001742_p11_2810fef9` |
| 12 | `20261118T004847_p12_a74097b5` |
| 07_small | `20261117T235936_p07_e0ae2117` |
| 07_nanshan | `20261117T235946_p07_4ed639cd` |
| 13 | `20261118T005701_p13_457497bb` |

Sioux Falls相对间隙9.92645e-5，参考流量相对RMSE0.05736%；南山平峰间隙1.70415e-5，未服务3649.7494 veh/h与区内1353.4766 veh/h均保留。南山正常/一般/严重/极端R为1 / 0.999913959 / 0.999664636 / 0.999460725，全部180次分配收敛，约21.6分钟。小网六路组、成本1、K=3、预算3、效果0.6，贪心选择road_05/road_03/road_04：R由0.991268226提高至0.997156009，与流量优先并列；42集合穷举差距0。独立十种子配对增益0.007565316，95% t区间[0.006974898,0.008155734]，只描述随机模型差异。

## 本轮失败、修复与恢复

所有失败run和日志均保留。GraphML字符串u/v属性覆盖节点标识，读取时改为图实际端点；NumPy已移除trapz，改用受支持积分接口；旧测试只接受早期CLI阶段和当前源码指纹，随新增功能更新。SUMO动态封路影响待发路线，改为保留外部队列、核查可发路线再入网；原有自环在SUMO沿同曲线拆为两段并保留映射，未新增连接。十种子训练完成后Tk绘图后端失败，切换Agg；从20261118T000318_p11_f3be35ea恢复已完成训练，保存源结果SHA，独立测试重跑。phase11_fresh.yaml可完全重算，phase11.yaml依赖该本机检查点。

早期dirty运行缺少不可变源码副本，最终审计以原Git blob和SHA完全一致的恢复文件核验，恢复文件保存在docs/validation/source_snapshots；未改历史git状态或hash。后续归档增加源码/配置快照与输出清单。历史数据按真实本地字节核查。

文档生成发现PPT空项目符号，删空行后修复；finalizer禁止覆盖旧输出，改新输出路径；子进程缺少RUNTIME_NODE_MODULES，显式配置捆绑路径后通过。Word沿已诊断的LibreOffice缺失使用Microsoft Word只读COM导PDF，再pypdfium2渲染；19页和19张逐一查看，12张源图字节核验，PPT结构/字体/再次导入检查通过。未声称原生PowerPoint播放测试。

最终审计20261118T005701_p13_457497bb：基础和后续输入/图件、守恒、收敛、公平预算、独立种子、六次SUMO全车辆去向、界面与交付指纹通过；小网fresh重算R绝对误差0，54个数据文件冻结。最终106项测试/44警告、pip check通过，原始stdout见docs/validation/current-tests.txt与current-pip-check.txt。


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


监测SW零点与测站地址代理位置未核实；OD、容量、积水、治理成本效果与情景概率未实测标定；人口与OSM年份不同，完整避难所缺失。南山时间效率为15起点抽样，介数32起点抽样。南山SUMO治理集合与风险无交集，灾害与治理结果相同；不据此证明全区治理有效。C/D/E只用种子42，B/F各十种子。GA为可选扩展未实现；G为实际分配效率表，不冒充南山优化耗时。

## 历史Phase00—03（当时状态，保留原文）

# 实验配置与结果

## 2026-11-17 Phase 00 实施过程记录

目的：验证开发环境、配置、运行归档和图片可追溯；没有道路/内涝/交通实验结果。

初查：默认 Python 3.8.3（D:/anaconda/python.exe）；24逻辑CPU；总内存15.8 GiB，检查时可用约3.2 GiB；RTX4060 Laptop约8 GiB显存；C/D剩余约30.4/63.7 GiB。不同时间可用资源会变化，以每次运行原始JSON为准。

已执行主要命令（工作目录均为本项目）：

```powershell
conda create --prefix .conda-env --override-channels -c conda-forge python=3.11 pip -y
uv pip install --python .conda-env\python.exe -r requirements.in
python -X utf8 scripts/verify_references.py
```

使用Codex自带Python运行 `scripts/inspect_literature.py` 提取论文全文。临时文本位于 .cache/literature，不作为原文替代。

问题记录：

1. Get-CimInstance 无法访问 CIM 资源，改用 platform/psutil/nvidia-smi 获取实际信息。
2. uv 默认缓存访问被拒绝，经过执行权限审核后继续安装；没有修改base环境。
3. 默认Python在受限执行时HTTPS不可用，外网核实经权限审核执行；4篇英文Crossref成功，中文DOI为404，须另核期刊。
4. 原始PDF提取存在字体警告和数学符号失真；关键公式页已渲染核对。Land Eq.(18)与Table 5常数符号冲突已登记。

上述为实施过程记录，最终结果如下。

## Phase 00 验收结果

- Python 3.11.18，Conda环境位于`.conda-env`；uv实际安装63项依赖；Conda底层和pip层分别锁定在conda-win-64.lock.txt、requirements-win-64.lock.txt。
- 本地项目安装命令增加`--no-index --disable-pip-version-check`避免无必要的联网检查；初次普通editable安装长时间无输出后中止，离线安装成功。
- 首轮35项pytest通过；增加投影/GeoJSON/Parquet/GeoTIFF实际读写兼容检查后37项通过；最终兼容修正后复核仍为37通过、1条rasterio/affine未来弃用警告，无测试失败。原始输出见docs/validation/pytest-final.txt与XML。
- `python -m pip check`：No broken requirements found。
- `python -m uftr.cli check-config`：valid=true，97端点。
- 第一次真实运行：20261117T172555_p00_0dcd60c4；20/20导入，5.2153秒，正常结束；源实现提交772b8f6，git dirty=false。
- 生成environment_check.png和.svg，PNG已实际查看，无裁切重叠；源JSON、输入、图片SHA256校验通过；索引7个本地链接均存在。
- `python -m uftr.cli history --phase 00 --date 2026-11-17 --kind figure`返回PNG/SVG两条记录；`reindex`成功。
- 执行账号变化导致Git所有权保护报错，改为只在本项目单次命令中传safe.directory；未修改全局Git配置。CLI输出统一UTF-8。
- 5篇本地全文和10张关键页用于方法核查；4篇Crossref成功，中文Crossref404、期刊HTTP500，保留失败记录，未重复下载论文。

最终复核运行和交付文件清单见docs/PHASE00_REPORT.md；没有运行后续阶段交通实验。

最终复核：20261117T173510_p00_a2d49eb6，20/20导入、6.2704秒、success，源码0e0b562且dirty=false。保留此前运行，现有4条图像格式记录和14个索引链接；本次2图片/6输入指纹校验通过。验收PNG/SVG及原始JSON/manifest另存docs/validation以纳入Git。最终PNG已查看，中文CLI查询正确显示。

## PPT 与 Word 同步维护历史 2026-11-17

## Phase 01 实施过程

用户继续后读取阶段文档，实施真实路网获取。沙箱内 GitHub 请求超时；授权联网后 Sioux Falls 和 Nominatim 可读。Overpass 主端点502繁忙，kumi/private.coffee超时，其他公开镜像亦失败。官方 api.openstreetmap.org 只读地图API成功，改为限定请求预算、1秒间隔、按需细分分块下载原始OSM XML，再以OSMnx公开XML接口建图；这一变化需在最终数据来源中说明。

首次网络单元检查26项通过、1项失败：oneway=-1的方向限速误用。查阅已安装OSMnx _add_paths 确认节点先翻转后reversed=False，已按原始oneway标签修正，复核27项通过。CSV导出改为普通DataFrame避免几何列被WKT替换的无害警告。真实数据运行和最终验收结果在后文记录。

根据用户要求，保留根目录原始论文、PPT、Word，在 docs/deliverables 建立可编辑维护版：PPT 9页、Word 6页。整理研究范围、模型规划、5篇本地论文与采用边界、Phase 00 验收、真实环境图、图片查询与下一步。两文件的日期、验收指标、运行ID、图像与书目共用 content.json；保存 scripts/build_word.py 与 scripts/build_presentation.mjs。

使用 Codex 捆绑 Python/python-docx 和 Node/@oai/artifact-tool 构建。PPT finalizer 通过9页包结构、布局、原稿字体和再次导入检查，9张 PNG 已逐张查看。首次 finalizer 缺少 RUNTIME_NODE_MODULES 环境变量，设置捆绑模块路径后通过。未安装新软件。

规定的 render_docx.py 实际运行后因本机缺少 LibreOffice soffice.exe 失败；读取报错后改用已安装 Microsoft Word 只读打开并 ExportAsFixedFormat 导出 PDF，再由捆绑 pypdfium2 渲染 PNG。初版有空白页和末节跨页，已修正分页、行距与标题边框，最终6页均检查。预览PDF/PNG仅作本地QA，存 .cache/doc-sync，不作为交付文件。此次不改科学模型，不重跑已验收交通基础测试，不声称完成后续仿真。GitHub 上传仍待认证与远端设置。

## Phase 01 最终验收

初次完整下载20261117T192004_p01_d71ec83e成功。核查发现南山行政海域含港珠澳大桥相关17边，保留完整图并配置研究窗口；方向oneway=-1与孤立环岛保留均修复。离线运行20261117T193355_p01_d6c1cd1a因Windows XML换行比较失败，失败归档保留；增加保留原始字节的回归测试后，20261117T193651_p01_2e554d34离线重放通过，99.9249秒，源e811519、dirty=false。

小区1140节点/2247边；南山研究窗口20447节点/40105边、33弱分量、6对平行边；Sioux Falls24节点/76弧及576个OD读取成功。62项pytest通过（旧pytest-final.*为61项历史记录，最终以pytest-accepted.*为准），pip check无冲突。独立审计全道路方向、几何、投影长度和三格式一致性，21项输出通过；4图像格式、171输入和42索引链接校验通过。两张最终PNG已逐张检查。实际命令、数据获取失败、许可及边界见docs/PHASE01_REPORT.md。

本次同步PPT与Word纳入两张实际路网图、阶段统计、OSM回退来源、研究窗口与估计属性限制、Sioux原始单位及下一阶段Phase 02；历史Phase 00指标保持37项，不用62项覆盖历史。文档使用Codex捆绑运行时，Word继续使用已安装Microsoft Word导出PDF再渲染。最终页数、指纹及检查方法见docs/deliverables/delivery_manifest.json。GitHub远端和认证仍未就绪。

文档最终检查：PPT 13张和Word 9页均逐页查看；三个嵌入PNG字节与源图完全一致，共用证据和DOI核对通过，原稿指纹不变。PPT第一次finalizer输出与私有回执同目录被拒，改为独立输出目录；第二次遇历史回执已存在，生成脚本改为按输出文件名区分回执，使用新输出后通过。中间文件仅留.cache，维护入口替换为已检查版本。

## Phase 02 实施与最终验收 2026-11-17

用户继续后实现spatial_sources/spatial/phase02、配置、CLI与独立审计。经联网审核下载Copernicus两瓦片、WorldPop 2020约1km人口、NOAA GSOD宝安2023雨量，许可/目录/失败响应保存，人口约49MB慢速下载已完整结束。官方开放平台元数据403，下载需实名，未绕过；其他404/HTML错误/SSL失败见研究记录。复用Phase 01原始XML提取OSM设施，未另造名录。

增加原生栅格不重采样、点清洗、雨量标志、垂直道路排除和几何置信度、合成低DSM聚集规则与不可变快照测试。初版76项通过，增加历史源输入Git blob核验测试后最终77项通过、35条rasterio/affine未来弃用警告，pip check无冲突，原始日志保留docs/validation/phase02/。历史运行审计原来误按当前变动源文件核验，已修复；Phase 01重审通过，3项源输入按原提交验证，原始数据仍按本地字节核验。

实现提交878e467。首次完整运行20261117T203230_p02_9be1082c成功，因两个文档脚本恢复后stat/EOL标志记录dirty=true；git diff未见实际内容变化，刷新索引后工作区清洁。最终离线重放20261117T203637_p02_0286d999，源码878e467、dirty=false，47.4027秒。执行命令：`.conda-env/python.exe -m uftr.cli run --phase 02 --offline-source data/raw/phase02/20261117_source_acquisition`。

结果：DSM563281有效像元，人口233个原生像元、1540614.3657估计人数；医院14/消防15，避难清单缺失；365日雨量、355有效。官方积水点/深度未取得，另存60合成点，高/中/低几何置信度7/25/23，未匹配5。1414候选行、122垂直排除、74选中有向边行。归档审计4图/215输入/74索引链接通过，空间独立审计及六项数据字节重放一致。四张最终PNG分别检查，无裁切或文字重叠，验收副本纳入Git。

原始/处理/合成分开；雨量不拆15min，DSM不作排水DTM，人口不是普查，合成点不是历史灾害。同步维护PPT/Word与七份管理文档，文档渲染、页数和指纹见delivery_manifest。未运行Phase 03以后模型。GitHub未设置remote、gh不可用，保留授权但尚未上传。


Phase 02文档最终检查：PPT 18张、Word 13页全部逐张/逐页查看，无裁切、重叠或孤立说明页。Word初版14页中重复维护说明独立溢出，删除重复段后修复；地形/人口和雨量同页仍清晰。PPT结构、布局、原稿字体与再次导入检查通过，七张嵌入PNG字节一致，三阶段run_id/数值/DOI及原稿指纹检查通过。沿用已确认缺少LibreOffice时的Microsoft Word只读导出PDF方案，未安装软件，未声称检查原生PowerPoint播放。


GitHub上传补充：用户提供https://github.com/zhzhzh666/jiaotong后，配置origin并读取远端。远端仅有初始README，和本地无共同提交；使用allow-unrelated-histories合并，README add/add冲突保留完整项目说明，远端初始提交仍作为父历史保留。本地验收提交3866788，合并提交71e17a07a6e46219f88f5b9b4402f8abe4a4ba6f。Git Credential Manager已有可用认证，普通push -u origin main成功，随后ls-remote确认远端main与本地完整哈希一致。未安装gh、未显示凭据、未强制推送。原先日志中未上传的记载为提供仓库前的历史状态，当前以本补充为准。

## Phase 03 已验收 2026-11-17

最终运行20261117T215510_p03_ab17de87，实现提交410a526224966d7ac30203049978823185876038、dirty=false，36.3785秒。98项测试通过、44条rasterio/affine未来弃用警告，pip check无冲突。568个1000 m裁剪TAZ，236个正产生/吸引TAZ；193个区内道路接入、43个未接入，未删需求；6个真实跨界外部节点。保留233个WorldPop原生像元的1540614.3657147214估计人数。平/早/晚峰总量36974.744777/73949.489554/66554.540599 veh/h，全部为未标定合成小时率原型；每时段58528非零OD对。IPF最大相对边际误差9.64608e-10，最大绝对误差6.891502e-7 veh/h。区内未上图与正常不可达需求单列，原MultiDiGraph不改动。

水位来源由用户确认：深圳市政府数据开放平台抓取，高水位日期筛选，平台地址经高德地理编码。45站、18123条记录；6站/2393条在研究边界，1条东莞POI匹配方式可疑。用户确认0.15/0.30/0.40 m蓝黄橙红分级；SW路面零点仅为“平时近零”的推测，平台未明确，保留raw值，不直接作为道路积水深度。六个原始CSV/ZIP在根目录和sealed snapshot保持字节不变，未纳入Git。

独立审计、5图/55输入/114索引链接校验通过，11项关键输出与首轮成功运行逐字节一致。5张实际PNG逐张查看并保存到docs/validation/phase03；Word19页、PPT24张全部渲染检查，12张嵌入源图字节核验，原稿指纹不变。报告和命令见docs/PHASE03_REPORT.md。下一阶段为Phase 04，本阶段结束停止，收到继续指令再实施。

本轮失败及修复：20261117T214644_p03_61342393的NumPy bool报告序列化失败，转换为原生bool修复；20261117T214831_p03_c01bcc13的源分级带括号说明，改为校验纯等级前缀且保留全文。独立审计float32求和与逐像元float64总量精度不一致，改为float64审计求和。首轮成功20261117T215014_p03_2b8fe770；热力图标签拥挤已修复，实施提交410a526后干净源码重放。所有失败运行、数据和日志保留。最终命令：`.conda-env/python.exe -m uftr.cli run --phase 03 --user-source data/raw/user_sources/20261117T215014_p03_2b8fe770`。独立审计scripts/audit_demand.py与scripts/audit_run.py通过。

冻结输入审计补充：原合成包生成器修正相对配置路径后，历史代码按包内provenance快照的原SHA逐字节接受；原10输入/38输出清单和ZIP字节未修改。当前退水实验7输入均匹配当前字节。

文档用综合性能曲线的图例移至坐标轴外，避免遮挡恢复段。通过scripts/export_traffic_resilience_figure.py从冻结interval_metrics.csv重绘，仅修改排版，PNG/SVG及figure_source.json保留源CSV、原manifest、导图脚本与新图SHA。原运行图片、964项输出指纹与438986070字节ZIP均未修改。
