# Word 与 PPT 维护说明

2026-11-18维护版：Word22页、PPT22张。原19节实验报告后增加降雨驱动积水、60个南山合成点、完整OD与出发时间分布三节。降雨、水深及OD未经实测校准，新包未重跑分配或韧性。原始根PPT/Word、论文及用户水位数据保持不动。

共用正文与图表证据为content.json的final.sections及synthetic_data_package。Word嵌入15张源图，PPT嵌入13张；新增降雨/水深/需求采用三个原生可编辑图表，7条序列与源CSV逐值核对。共享标题、DOI、原稿指纹和交付文件SHA通过核验；详情见delivery_manifest.json。此前106项核心测试记录沿用，本轮另通过16项生成一致性检查，未重跑核心模型与长仿真。

## 维护与渲染

文档使用Codex捆绑Python，PPT使用捆绑Node与artifact-tool。通过load_workspace_dependencies查询运行时；模型与GIS生成只用项目.conda-env。Word命令为`scripts/build_final_word.py --output 新路径.docx`。本机缺少LibreOffice，沿用新建后台Word COM实例只读打开候选、ExportAsFixedFormat PDF17、pypdfium2逐页导PNG的方法；原稿不打开编辑。

追加PPT使用`scripts/append_synthetic_data_presentation.mjs 构建目录 新输出.pptx 19张源文件.pptx`。本次19张已审源备份为`.cache/synthetic-doc-sync/before/开题与阶段进展汇报.pptx`；脚本拒绝向22张版重复追加。将脚本复制到.cache/doc-sync（node_modules链接捆绑模块），设置CODEX_PRESENTATION_SKILL、CODEX_ARTIFACT_PYTHON、RUNTIME_NODE_MODULES后，从项目根运行。PPT输出与私有回执放不同目录，每次使用新输出路径。原19节从头构建脚本仍保留，使用前须进行完整视觉复核。

finalizer核验包结构、字体、几何、原生图表与嵌入XLSX，并重新导入最终文件逐张导PNG。当前QA位于`.cache/synthetic-doc-sync/`：Word PDF与22页PNG、v3回执与22张PNG、before旧维护文件。新Word20—22页、PPT2/3/20—22张打开检查；其余Word19页和PPT17张PNG与上一逐页审核版本字节一致。旧版审核记录也留在before和Git历史中。

人工检查后更新docs/validation/final_visual_review.json，使用捆绑Python运行`scripts/verify_final_deliverables.py`。该脚本按当前审核记录读取对应PDF/回执，验证页数、共享正文、DOI、嵌图、源CSV图表与原稿，更新delivery_manifest.json。不得挪用旧回执或把结构核验称为原生PowerPoint播放验收。

## 数据包与复现边界

完整新数据包和ZIP保留本机`data/synthetic/scenario_packages/20261118T141443_nanshan_seed42`，字段与模型见../SYNTHETIC_DATA_PACKAGE.md；小型核验副本在../validation/synthetic_data_package。Git包含源码、配置、维护文档与小型核验材料，不包含全部原始输入和完整生成数据。重新生成前须恢复configs所指本机输入；输入SHA记在包manifest.json。修改合成参数后，新运行结果必须重新验收。

依赖锁是实际安装版本集合。docs/validation/installed-pip-freeze.txt保留原始pip provenance；requirements-lock.txt将本机构建URL规范为版本并移除旧editable地址，项目另用pip install -e .安装。范围及历史限制见../FINAL_REPORT.md、../USER_GUIDE.md和根EXPERIMENT_LOG.md。
