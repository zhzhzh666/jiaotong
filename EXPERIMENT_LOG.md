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
