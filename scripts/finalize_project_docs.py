"""Synchronize project state only after successful independent final audit."""
from pathlib import Path
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'docs/deliverables/content.json').read_text(encoding='utf-8'))
audit=json.loads((ROOT/'docs/validation/final_audit.json').read_text(encoding='utf-8'))
assert audit['status']=='passed'
runs={p:r['run_id'] for p,r in audit['runs'].items()}
p13=sorted((ROOT/'results/runs').glob('*_p13_*/manifest.json'))[-1]
assert json.loads(p13.read_text(encoding='utf-8'))['status']=='success'
runs['13']=p13.parent.name
historical=ROOT/'docs/history-phase03';historical.mkdir(exist_ok=True)
for name in ['AGENTS.md','PLAN.md','PROGRESS.md','DATA_SOURCES.md','MODEL_ASSUMPTIONS.md','EXPERIMENT_LOG.md','README.md']:
    if not (historical/name).exists():shutil.copy2(ROOT/name,historical/name)

def write(name,text):
    (ROOT/name).parent.mkdir(exist_ok=True,parents=True)
    (ROOT/name).write_text(text.strip()+'\n',encoding='utf-8')

scope='南山已完成全图用户均衡、24小时/97端点韧性与固定2000辆计划的SUMO抽样；关键性、治理及十种子实验使用三个TAZ的小型真实区域。尚未实施南山全尺度优化，不能宣称全区治理收益或已校准历史灾害预测。'
status=f'2026-11-18：Phase 00—13按上述实际范围完成研究原型与最终审计；106项测试通过、44条既有弃用警告，pip check无冲突。{scope}'
rows='\n'.join(f'| {p} | `{run}` |' for p,run in runs.items())
metrics='''Sioux Falls相对间隙9.92645e-5，参考流量相对RMSE0.05736%；南山平峰间隙1.70415e-5，未服务3649.7494 veh/h与区内1353.4766 veh/h均保留。南山正常/一般/严重/极端R为1 / 0.999913959 / 0.999664636 / 0.999460725，全部180次分配收敛，约21.6分钟。小网六路组、成本1、K=3、预算3、效果0.6，贪心选择road_05/road_03/road_04：R由0.991268226提高至0.997156009，与流量优先并列；42集合穷举差距0。独立十种子配对增益0.007565316，95% t区间[0.006974898,0.008155734]，只描述随机模型差异。'''
limits='''监测SW零点与测站地址代理位置未核实；OD、容量、积水、治理成本效果与情景概率未实测标定；人口与OSM年份不同，完整避难所缺失。南山时间效率为15起点抽样，介数32起点抽样。南山SUMO治理集合与风险无交集，灾害与治理结果相同；不据此证明全区治理有效。C/D/E只用种子42，B/F各十种子。GA为可选扩展未实现；G为实际分配效率表，不冒充南山优化耗时。'''
commands=r'''
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
'''
write('README.md',f'''# 深圳暴雨内涝交通韧性研究原型

{status}

## 使用与结果

界面启动后打开 http://127.0.0.1:8501 。八页中文系统展示预计算结果，侧栏筛选情景、时间、K、策略与效果；未计算组合明确提示。治理图为小网选中道路，Phase09参考曲线有固定参数标识。

{commands}

## 实际结果

{metrics}

{limits}

## 文档、图片与数据

- [Word研究报告](docs/deliverables/研究方案与阶段进展.docx)：19页；[PPT汇报](docs/deliverables/开题与阶段进展汇报.pptx)：19张，均逐页渲染查看，12张嵌入源图SHA匹配。
- [最终报告](docs/FINAL_REPORT.md)、[操作说明](docs/USER_GUIDE.md)、[最终审计](docs/validation/final_audit.json)。
- 本机完整图片索引`results/index.html`；每次`results/runs/<run_id>/`保留raw、figures、screenshots、logs、配置与manifest。Git中可查`docs/validation/phase04`至`phase12`的小型验收副本。
- 原始资料、完整`data`和`results/runs`留本机，克隆仓库不包含这些大型输入，复现需按`configs`路径恢复本机备份；`docs/validation/final_data_inventory.json`冻结54个输入文件字节。
- 根目录论文、原PPT/Word和用户六份水位CSV/ZIP保留；原稿指纹见`delivery_manifest.json`。字段字典存本机`data/raw/user_sources/field_dictionary_e9e5a7bd`。

## 环境与来源

使用本项目`.conda-env/python.exe`（Python3.11），锁定依赖见`requirements-lock.txt`，Eclipse SUMO/traci/sumolib1.28.0。新机器在独立Python3.11环境中安装`requirements-lock.txt`和`pip install -e .`；不修改系统/base环境。包锁来自Windows，不保证其他平台二进制依赖完全一致。

OSM / WorldPop / Copernicus / NOAA / TNTP来源、许可及估计字段见[DATA_SOURCES.md](DATA_SOURCES.md)。45站18123条水位来自用户抓取的深圳开放平台，SW为m、SJ北京时间；路面零点仍未正式说明，不将观测直接当道路积水深度。

[GitHub仓库](https://github.com/zhzhzh666/jiaotong)。逐阶段run_id见[PROGRESS.md](PROGRESS.md)，历史Phase03文档保存在`docs/history-phase03/`；历史“未开始”描述不代表当前状态。
''')
write('PROGRESS.md',f'''# 当前进度

{status}

{metrics}

Word19页、PPT19张全部查看；原稿指纹与12张嵌入源图字节核验通过。八页界面、情景/时间/预算/效果、未计算提示和136行CSV下载逐值核验通过。最终审计小网重算误差0；六次SUMO全车辆记账平衡、teleport0；Phase01—12输入和图片指纹通过。此轮运行源码状态为dirty=true且原样保留，使用快照、原Git blob或精确恢复源码核验，未改为虚假干净状态。

| 阶段 | 已验收run_id |
| --- | --- |
{rows}

{limits}

本地验收已完成；Git提交与远端核对结果见交付时Git历史。历史Phase00—03记录见docs/history-phase03/PROGRESS.md。
''')
stages=[('00—03','环境、真实路网、数据和合成OD','历史已验收'),('04','97端点四情景、54有向边、图/GIF','已验收，参数化场'),('05','文献速度、独立容量与中断','已验收'),('06','Sioux与两种深圳规模UE','已验收'),('07','小网/南山结构性能功能与积分','已验收'),('08','六候选逐路治理、失效与排名','小网已验收'),('09','六策略、预算、重算边际与穷举','小网已验收'),('10','两规模三情景SUMO、完整去向','抽样原型已验收'),('11','A—G、B/F十种子、独立测试','按报告范围验收'),('12','八页中文交互与CSV导出','已验收'),('13','基础阶段+后续档案、数据、守恒、重放、文档审计','已通过')]
write('PLAN.md',f'''# 开发计划与实际完成范围

{status}

| 阶段 | 实际输出 | 状态 |
| --- | --- | --- |
'''+ '\n'.join('| '+' | '.join(row)+' |' for row in stages)+f'''

任务书原文保留docs/TASK_SPEC.md，未改写初始目标。阶段报告docs/PHASE00_REPORT.md至PHASE13_REPORT.md给实际命令与结果；研究原型不等同于全部扩展目标完成。

{limits}

后续研究扩展：核验SW路面零点和传感器位置；标定OD/容量/水深与治理成本；扩大南山治理候选并完成全尺度优化；改进设施入口及避难所覆盖；记录更细的全尺度优化内存/迭代性能，验证独立真实灾害事件；可选GA对照。以上未计入当前已完成实验。

原逐阶段计划与验收清单完整保留docs/history-phase03/PLAN.md。用户“直接一直继续完成”的授权覆盖旧阶段停止门禁。
''')
write('AGENTS.md',f'''# 项目长期规范与当前状态

{status}

## 授权与范围

- 项目根目录为jiaotong独立仓库，不写父目录其他项目。用户已授权连续完成、维护Word/PPT、保存图片并向origin正常推送，无需重复确认。禁止force push或覆盖远端历史。
- 根目录论文、原PPT/Word、水位CSV/ZIP保留不动且不入Git；大型数据、环境及完整results留本机。
- 此轮按实际规模验收，不再从Phase04重新开始。后续以PROGRESS.md和最终审计为准；旧停止指令和未开始状态均为历史。

## 数据与模型

- 实测、估计、合成分开；水位字典只支持m和北京时间，SW路面零点未核实。地址地理编码不当作传感器实测点。记录资料冲突。
- 保留MultiDiGraph平行边、真实方向和断连；WGS84存储、EPSG32650距离。道路关闭移出网络，未服务与区内需求保留并计成本。
- 距离/水深m、时间s、流量/容量veh/h；文献公式注明PDF页码、式号和换算。容量退化与封路阈值是项目假设。时间片UE不称完整动态分配，参数化场不称历史水动力重建。
- {limits}

## 工程与验收

- 仅使用独立`.conda-env/python.exe`，默认seed42、workers1；主要参数放configs，不改系统/base。
- 每次新run_id，保留失败、检查点和原始输出；源码/配置快照及数据SHA可追溯，不能篡改历史manifest。历史精确恢复源码只按原SHA逐字节接受。
- 实际运行图保留PNG及合适的SVG/GIF，浏览器截图记录实际界面；检查最终图。HTML/CSV索引可重建，manifest是权威记录。
- 修改模型后执行pytest与pip check，必要的数值重放和独立审计；不为单纯文案反复运行长仿真。不得把未实测项目写为通过。
- 更新七份根文档及阶段报告；Word/PPT共用content.json真实证据，最终导出后逐页渲染查看，核验嵌图、DOI、数值和原稿指纹。
- 桌面Python/GIS/Streamlit/SUMO项目没有移动测试任务；若新增移动测试再遵循用户的ARTEMIS探索规则。

历史规范及验收细节保留docs/history-phase03/AGENTS.md；当前状态和连续授权以本文件为准。
''')
sections=data['final']['sections']
model_titles={'交通分配模型与基准验证','24小时参数化内涝情景','道路速度与容量退化','综合韧性的定义与成本口径','六组候选道路的关键性','预算约束优化与穷举核验','十种子策略与独立鲁棒性','预算、效果与消融实验','SUMO车辆过程与完整去向'}
write('MODEL_ASSUMPTIONS.md','# 当前模型与假设\n\n'+scope+'\n\n'+ '\n\n'.join('## '+s['title']+'\n\n'+'\n\n'.join(s['paragraphs']) for s in sections if s['title'] in model_titles)+'\n\n'+limits+'\n\n阶段00—03的公式、OD和空间处理假设保留docs/history-phase03/MODEL_ASSUMPTIONS.md。')
write('DATA_SOURCES.md',f'''# 数据来源与真实性

更新2026-11-18。真实来源、估计属性与合成结果严格分开。{scope}

## 用户水位与字段字典

45站18123条样本；边界内6站2393条。深圳开放平台[水位目录](https://opendata.sz.gov.cn/data/dataSet/toDataDetails/29200_01403147)、[测站目录](https://opendata.sz.gov.cn/data/dataSet/toDataDetails/29200_01400987)。用户确认由平台抓取高水位日期，站址经高德编码；风险断点0.15/0.30/0.40m为蓝黄橙红标签。原始CSV/ZIP保持原字节，未入Git。

新增用户《深圳市积涝点水位数据字段说明.docx》原件和UTF8提取存data/raw/user_sources/field_dictionary_e9e5a7bd，SHA256=e9e5a7bd05a6ee9daa24f05f623e9349f760127e01f74fb1c47d599ba70be1c1。仅据其支持SW单位m、SJ北京时间；零点无正式声明，不能从平时近零直接证明路面零点。说明文档为证据，非可执行开发指令。

保留两处冲突：字典事件截至19:40而实际CSV截至2023-09-08 20:04:05；测站9281292012字典“沙井路近似”与CSV东莞POI匹配方式不同。地址坐标及GCJ02转换未经现场核验，不当传感器精确位置。

## 数据层与许可

| 来源 | 本项目用途 | 限制 |
| --- | --- | --- |
| OpenStreetMap，ODbL1.0 | 真实有向几何、医院14/消防15 | 缺失车道速度按类型估计，容量全为模型；入口不完整 |
| WorldPop2020，CC BY4.0 | 原生约1km模型人数、TAZ产生吸引 | 非普查，年份/边界有差；233像元保留1540614.3657模型人数 |
| Copernicus GLO30 | 地形背景和风险代理 | DSM含建筑植被，不是排水DTM |
| NOAA GSOD宝安2023 | 365日背景雨量，355有效 | 缺失保留，未伪拆15分钟 |
| TransportationNetworks/TNTP | Sioux Falls算法基准与参考流量 | 时间单位0.01h转秒；保留基准流量单位 |
| 深圳开放平台，用户抓取 | 水位观测与位置代理核查 | SW路面零点未说明，未自动转道路深度 |
| 项目合成 | OD、54有向边参数化积水、小网六候选压力情景 | 非历史重建/真实灾害概率或工程效果 |

详细下载URL、版本、许可、原始论文指纹、失败响应与坐标处理见历史阶段报告与docs/history-phase03/DATA_SOURCES.md。原论文原始模型数据未因下载全文而自动取得。

## 最终数据冻结

docs/validation/final_data_inventory.json记录最终审计时54个输入文件路径、长度和SHA；基础Phase01—03及后续manifest输入也逐项核验。冻结发生在最终审计，不能倒称早期运行已经完整记录后来新增的字段。data/raw、processed、synthetic和完整results未纳入Git，须保留本地备份。
''')
old=(historical/'EXPERIMENT_LOG.md').read_text(encoding='utf-8')
write('EXPERIMENT_LOG.md',f'''# 实验记录：当前验收与完整历史

{status}

| 阶段 | run_id |
| --- | --- |
{rows}

{metrics}

## 本轮失败、修复与恢复

所有失败run和日志均保留。GraphML字符串u/v属性覆盖节点标识，读取时改为图实际端点；NumPy已移除trapz，改用受支持积分接口；旧测试只接受早期CLI阶段和当前源码指纹，随新增功能更新。SUMO动态封路影响待发路线，改为保留外部队列、核查可发路线再入网；原有自环在SUMO沿同曲线拆为两段并保留映射，未新增连接。十种子训练完成后Tk绘图后端失败，切换Agg；从20261118T000318_p11_f3be35ea恢复已完成训练，保存源结果SHA，独立测试重跑。phase11_fresh.yaml可完全重算，phase11.yaml依赖该本机检查点。

早期dirty运行缺少不可变源码副本，最终审计以原Git blob和SHA完全一致的恢复文件核验，恢复文件保存在docs/validation/source_snapshots；未改历史git状态或hash。后续归档增加源码/配置快照与输出清单。历史数据按真实本地字节核查。

文档生成发现PPT空项目符号，删空行后修复；finalizer禁止覆盖旧输出，改新输出路径；子进程缺少RUNTIME_NODE_MODULES，显式配置捆绑路径后通过。Word沿已诊断的LibreOffice缺失使用Microsoft Word只读COM导PDF，再pypdfium2渲染；19页和19张逐一查看，12张源图字节核验，PPT结构/字体/再次导入检查通过。未声称原生PowerPoint播放测试。

最终审计{runs['13']}：基础和后续输入/图件、守恒、收敛、公平预算、独立种子、六次SUMO全车辆去向、界面与交付指纹通过；小网fresh重算R绝对误差0，54个数据文件冻结。最终106项测试/44警告、pip check通过，原始stdout见docs/validation/current-tests.txt与current-pip-check.txt。

{commands}

{limits}

## 历史Phase00—03（当时状态，保留原文）

{old}
''')
write('docs/FINAL_REPORT.md','# 最终研究报告\n\n'+status+'\n\n'+ '\n\n'.join('## '+s['title']+'\n\n'+'\n\n'.join(s['paragraphs'])+('\n\n!['+s['caption']+']('+s['figure'].replace('docs/','../docs/',1)+')' if s.get('figure') else '') for s in sections)+ '\n\n## 最终审计\n\n'+f"运行{runs['13']}，测试106，数据文件54，数值重放误差0。见validation/final_audit.json。")
write('docs/USER_GUIDE.md',f'''# 操作说明

工作目录C:/Users/zh/Desktop/git/jiaotong。{scope}

## 安装与运行

{commands}

## 界面

打开http://127.0.0.1:8501；按八页查看路网、积水、退化、韧性、可达性、关键道路、治理和实验。时间滑块按15分钟，从0到96；南山积水图和小网治理压力场是独立数据，界面有明确说明。预算/效果按已算方案筛选，K超过6会截断；未计算组合不运行后台新优化。Phase09曲线始终固定种子42/K3/效果0.6。

实验页下载136行完整CSV，界面按实验组筛选表格。来源折叠栏可下载manifest，本机完整图片索引results/index.html；下载的HTML需要与原results路径配套。勿把孤立HTML文件理解为已打包全部图片。

## 复现与备份

GitHub含源码、配置、依赖锁、Word/PPT和小型验收副本。请备份本机整个data与results/runs以及根目录原始资料；源码克隆不带大型输入。按configs路径恢复同名目录，输入指纹见manifest及final_data_inventory.json。测试与pip check通过后先运行06或07小网，南山07约22分钟。11_fresh从零算，11恢复本机失败运行的训练检查点；不要删除该检查点后再用恢复配置。

每次运行新建目录，旧成功或失败不会覆盖。结果和图保存于results/runs/<run_id>/raw、figures、screenshots，日志在logs；查询索引可reindex重建。模型配置变更后要重新生成对应实验，不直接修改历史CSV或图片。13审计依赖既有完整运行、界面验收与交付文件，不能替代新模型的重新验收。

## 报告维护

维护版docs/deliverables/研究方案与阶段进展.docx和开题与阶段进展汇报.pptx来自content.json。Python文档和artifact-tool PPT使用Codex捆绑运行时，见该目录README；图像均有源文件和run_id。原始根PPT/Word不改。19页/19张已渲染检查，最终图片检查记录和交付指纹在docs/validation及delivery_manifest.json。

{limits}
''')
for phase in ['12','13']:
    folder=ROOT/'results/runs'/runs[phase]
    val=ROOT/f'docs/validation/phase{phase}';val.mkdir(exist_ok=True)
    for source in [folder/'manifest.json',folder/'raw/stage_report.json']:
        shutil.copy2(source,val/('accepted-run-manifest.json' if source.name=='manifest.json' else source.name))
    report=json.loads((folder/'raw/stage_report.json').read_text(encoding='utf-8'))
    write(f'docs/PHASE{phase}_REPORT.md',f'# Phase {phase} 验收\n\n运行`{runs[phase]}`。命令`.conda-env/python.exe -m uftr.cli run --phase {phase}`。\n\n{scope}\n\n```json\n'+json.dumps(report,ensure_ascii=False,indent=2)+'\n```')
write('docs/validation/accepted_runs.json',json.dumps(runs,ensure_ascii=False,indent=2))
print('Updated seven project documents, final report, user guide and Phase12/13 reports.')
