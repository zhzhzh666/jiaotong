# Word 与 PPT 维护说明

2026-11-18维护版：Word19页、PPT19张，包含实际内涝、分配、南山韧性、小网六候选治理、十种子、SUMO和中文界面。共12张源图字节核验，全部逐页/逐张渲染查看。原始根PPT/Word及论文保留，原稿SHA见delivery_manifest.json。

content.json的final.sections是共用正文、图片和备注证据，旧phase00—03字段作为历史保留。当前范围为南山分配/韧性/抽样SUMO、小网优化与十种子；未完成南山全尺度优化，也没有实测标定的洪灾预测。数据零点、代理坐标、不可达需求与小网范围均在两份文件中明示。

先用项目环境执行scripts/build_final_content.py汇总真实成功run。Word使用Codex捆绑Python执行scripts/build_word.py --output 新文件.docx；PPT使用捆绑Node和artifact-tool，不能用python-pptx重建。将build_presentation.mjs和build_final_presentation.mjs一并复制到.cache/doc-sync，其node_modules链接捆绑模块目录，设置CODEX_PRESENTATION_SKILL、CODEX_ARTIFACT_PYTHON、RUNTIME_NODE_MODULES后从项目根目录执行build_presentation.mjs 新输出.pptx。捆绑运行时路径应通过load_workspace_dependencies查询，不修改项目环境。

PPT finalizer禁止覆盖已有输出和旧回执，每次使用新路径，检查后复制到维护文件名。结构、字体、几何和再次导入检查通过后，对最终文件再次导入并逐张导PNG查看。Word的render_docx.py依赖LibreOffice；本机缺少该程序已诊断，采用Microsoft Word新建COM实例只读打开维护候选，ExportAsFixedFormat PDF17，pypdfium2生成每页PNG并逐页查看。不得操作用户正在编辑的原稿。

QA文件留.cache/doc-sync。人工看图后更新docs/validation/final_visual_review.json的实际文件SHA与结论，再用捆绑Python执行scripts/verify_deliverables.py，核对标题/DOI/12张嵌图/原稿/交付文件SHA并更新manifest。当前验证分支scripts/verify_final_deliverables.py的回执文件名对应本次final-reviewed；下一轮必须按新回执路径更新，不能挪用历史通过结论。最终数值审计使用项目环境-m uftr.cli run --phase 13。

依赖锁是可安装的实际版本集合；docs/validation/installed-pip-freeze.txt保留原始pip provenance（含Conda构建位置与旧editable提交），requirements-lock.txt将本机构建URL规范为已安装版本并移除项目editable地址，项目本身另用pip install -e .安装。

验收范围、失败与修复记录、数据位置详见docs/FINAL_REPORT.md、USER_GUIDE.md和EXPERIMENT_LOG.md。此检查未声称原生PowerPoint播放或真实灾害校准已完成。
