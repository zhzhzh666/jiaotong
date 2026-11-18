# Word 与 PPT 维护说明

## 2026-11-18 新合成情景交通评估

131项测试、14项运行一致性检查与全部188个求解状态的独立BPR/间隙/节点守恒/需求记账审计通过；Word/PPT现为30页/张，原27页/张像素一致，新增28—30页/张逐张检查，23/15张源图SHA和14个原生图表45条序列核验通过。

本轮追加命令`scripts/append_traffic_process_presentation.mjs 构建目录 新输出.pptx 27张已审源文件`；源备份.cache/traffic-doc-sync/before。当前QA为.cache/traffic-doc-sync/final-word.pdf、final-word-pages、v1/validation.json、v1/slides，审核证据见../validation/final_visual_review.json。原10个源图表XML与工作簿原字节保留，新4个图表x/y显示值采用12位有效数并按1e-10容差核对全部源值。

R按96区间起点状态保持加权平均，正常基准逐区间使用同一OD；与旧97端点梯形积分不同。区内和不可达需求保留，全部568人口区保留在可达性分母；v/c使用退化容量。合成数据未经实测标定，独立时片不传递排队，本轮未进行全尺度治理优化或新SUMO仿真。各天气全天未服务量均与正常相同，医院消防覆盖也未变化；较高R仅描述当前54边暴露模型，不能证明真实暴雨影响很小。

最新131项测试与独立数值审计位于../validation/traffic_process；完整模型说明../TRAFFIC_PROCESS_MODEL.md。

以下保留此前模块与历史验收记录。

## 2026-11-18 道路交通性能退化更新

当前维护版Word27页/PPT27张，新增速度容量、中断恢复、南山道路状态三节。Word20张/PPT14张源图SHA匹配，10个原生可编辑图表29条序列与源数据逐值核验。最新124项测试、14项道路状态检查；容量、封路阈值与合成深度均未实测校准，未重跑分配或韧性。

本轮PPT命令为`scripts/append_road_performance_presentation.mjs 构建目录 新输出.pptx 24张已审源文件`，对应源备份`.cache/road-doc-sync/before/开题与阶段进展汇报.pptx`。捆绑运行时、node_modules链接、环境变量与前轮相同。保留六个源图表与XLSX原字节，新增四个图表使用源JSON，x/y显示缓存取12位有效数后逐值核验。

当前QA：`.cache/road-doc-sync/final-word.pdf`和`final-word-pages`、`v2/validation.json`和`v2/slides`。前24页/张与上一已审版本像素一致，新增25—27页/张逐一检查。最终文件和审核指纹见delivery_manifest.json及../validation/final_visual_review.json。`scripts/verify_final_deliverables.py`验证27页/张、嵌图、原生图表与原稿SHA。历史审查链和失败候选保留，不将结构检查称为原生PowerPoint播放验收。

以下保留此前模块及历史实验记录。

当前维护版为Word24页/PPT24张，新增降雨积水全过程与退水敏感性两节。Word17张/PPT13张嵌图、6个原生图表18条序列核验通过。115项测试和11项过程核验通过，原稿SHA保持。完整模型说明见../STORM_FLOOD_MODEL.md。

本轮PPT命令为scripts/append_storm_process_presentation.mjs 构建目录 新输出.pptx 22张已审源文件；源备份.cache/storm-doc-sync/before/开题与阶段进展汇报.pptx。帮助脚本preserve_existing_chart_workbooks.py逐字节保留旧图表和XLSX，不重构源公式。当前Word PDF/PNG位于.cache/storm-doc-sync/final-word.pdf和final-word-pages；PPT回执和PNG在v4。新23/24页张逐张检查，其余22页张与上一版像素一致。验证脚本按final_visual_review.json读取对应证据，不使用旧回执。

以下为上一轮流程与范围记录。

上一轮2026-11-18维护版：Word22页、PPT22张。原19节实验报告后增加降雨驱动积水、60个南山合成点、完整OD与出发时间分布三节。降雨、水深及OD未经实测校准，新包未重跑分配或韧性。原始根PPT/Word、论文及用户水位数据保持不动。

共用正文与图表证据为content.json的final.sections及synthetic_data_package。Word嵌入15张源图，PPT嵌入13张；新增降雨/水深/需求采用三个原生可编辑图表，7条序列与源CSV逐值核对。共享标题、DOI、原稿指纹和交付文件SHA通过核验；详情见delivery_manifest.json。此前106项核心测试记录沿用，本轮另通过16项生成一致性检查，未重跑核心模型与长仿真。

## 维护与渲染

文档使用Codex捆绑Python，PPT使用捆绑Node与artifact-tool。通过load_workspace_dependencies查询运行时；模型与GIS生成只用项目.conda-env。Word命令为`scripts/build_final_word.py --output 新路径.docx`。本机缺少LibreOffice，沿用新建后台Word COM实例只读打开候选、ExportAsFixedFormat PDF17、pypdfium2逐页导PNG的方法；原稿不打开编辑。

追加PPT使用`scripts/append_synthetic_data_presentation.mjs 构建目录 新输出.pptx 19张源文件.pptx`。本次19张已审源备份为`.cache/synthetic-doc-sync/before/开题与阶段进展汇报.pptx`；脚本拒绝向22张版重复追加。将脚本复制到.cache/doc-sync（node_modules链接捆绑模块），设置CODEX_PRESENTATION_SKILL、CODEX_ARTIFACT_PYTHON、RUNTIME_NODE_MODULES后，从项目根运行。PPT输出与私有回执放不同目录，每次使用新输出路径。原19节从头构建脚本仍保留，使用前须进行完整视觉复核。

finalizer核验包结构、字体、几何、原生图表与嵌入XLSX，并重新导入最终文件逐张导PNG。当前QA位于`.cache/synthetic-doc-sync/`：Word PDF与22页PNG、v3回执与22张PNG、before旧维护文件。新Word20—22页、PPT2/3/20—22张打开检查；其余Word19页和PPT17张PNG与上一逐页审核版本字节一致。旧版审核记录也留在before和Git历史中。

人工检查后更新docs/validation/final_visual_review.json，使用捆绑Python运行`scripts/verify_final_deliverables.py`。该脚本按当前审核记录读取对应PDF/回执，验证页数、共享正文、DOI、嵌图、源CSV图表与原稿，更新delivery_manifest.json。不得挪用旧回执或把结构核验称为原生PowerPoint播放验收。

## 数据包与复现边界

完整新数据包和ZIP保留本机`data/synthetic/scenario_packages/20261118T141443_nanshan_seed42`，字段与模型见../SYNTHETIC_DATA_PACKAGE.md；小型核验副本在../validation/synthetic_data_package。Git包含源码、配置、维护文档与小型核验材料，不包含全部原始输入和完整生成数据。重新生成前须恢复configs所指本机输入；输入SHA记在包manifest.json。修改合成参数后，新运行结果必须重新验收。

依赖锁是实际安装版本集合。docs/validation/installed-pip-freeze.txt保留原始pip provenance；requirements-lock.txt将本机构建URL规范为版本并移除旧editable地址，项目另用pip install -e .安装。范围及历史限制见../FINAL_REPORT.md、../USER_GUIDE.md和根EXPERIMENT_LOG.md。
