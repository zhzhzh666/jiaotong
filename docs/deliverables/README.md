# PPT 与 Word 维护说明

- `开题与阶段进展汇报.pptx`：13页，可编辑文字，保留原PPT画布、主题和字体；同步至Phase 01，包含研究路线、论文、历史环境验收及真实路网证据。
- `研究方案与阶段进展.docx`：9页，整合原研究构想与Phase 01实际状态，保留环境图、南山与小区域路网图及来源。
- `content.json`：共用的验收指标、状态、运行ID、图片与文献；源证据见 `../validation/`。
- `delivery_manifest.json`：交付与原稿指纹、预览检查方式、源数据对应检查。

根目录原始 `开题汇报.pptx`、`新建 Microsoft Word 文档.docx` 和五篇论文不覆盖、不移动。维护版纳入Git；大型结果与原始材料留本地。GitHub上传需有效认证和远端配置，当前尚未完成。

每阶段先核对实际验收记录，再更新 content.json 及两个构建脚本中的叙述、阶段规划与方法边界，不能只改日期或指标。图片必须来自已保存真实运行，标明run_id；文献结果、设计假设、项目运行结果分别表述。两文件使用同一验收截止状态。

构建使用 Codex workspace dependencies 返回的捆绑Python、Node与模块路径，不修改项目 `.conda-env`。Python执行 `scripts/build_word.py`，可用 `--output` 指定新文件。PPT将 `scripts/build_presentation.mjs` 复制到 `.cache/doc-sync/`，在该目录链接捆绑 `node_modules`；设置 `CODEX_PRESENTATION_SKILL`、`CODEX_ARTIFACT_PYTHON`、`RUNTIME_NODE_MODULES`，从项目根目录执行该模块。PPT finalizer 默认不覆盖已有输出，可传第一个参数指定新的最终文件路径。检查完成后再替换维护入口，历史版本由Git保留。

每次必须检查导出的最终文档：PPT执行结构、布局、字体和再次导入检查后渲染每张幻灯片；Word先执行 documents skill 的 render_docx.py。当前Windows没有LibreOffice，已用 Microsoft Word COM 只读导出PDF、捆绑pypdfium2生成PNG替代。逐页检查标题、字体、表格、图片、页码与分页，修正后重新渲染。QA中间文件留 `.cache/doc-sync/`，不纳入仓库；最终检查结论和指纹写入交付记录。

本次最终13张幻灯片与9页Word预览已逐张/逐页查看。`scripts/verify_deliverables.py` 用捆绑Python核对共用指标、文献DOI、两阶段run_id、三个嵌入PNG的原始字节及根目录原稿指纹，同时更新交付清单。它不能代替视觉检查。最终测试依据 `../validation/phase01/pytest-accepted.*` 为62通过；Phase 00历史指标仍为37项。地图速度、容量及边界适用限制见 `../PHASE01_REPORT.md`。
