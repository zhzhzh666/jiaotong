// Run a copy of this ES module from a private build directory linked to the
// Codex bundled node_modules. Output is always a new, separately finalized file.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';

const root=process.cwd();
const skill=process.env.CODEX_PRESENTATION_SKILL;
const python=process.env.CODEX_ARTIFACT_PYTHON;
if(!skill||!python) throw new Error('Set CODEX_PRESENTATION_SKILL and CODEX_ARTIFACT_PYTHON to bundled runtime paths.');
const data=JSON.parse(await fs.readFile(path.join(root,'docs/deliverables/content.json'),'utf8'));
const tmp=path.join(root,'.cache/doc-sync');
await fs.mkdir(path.join(tmp,'slides'),{recursive:true});
const original=path.join(root,'开题汇报.pptx');
const p=await PresentationFile.importPptx(await FileBlob.load(original));
const inspect=await p.inspect({kind:'slide,textbox,shape,layout',maxChars:24000});
await fs.writeFile(path.join(tmp,'import-inspection.ndjson'),inspect.ndjson);
const m=data.metrics;
function box(slide,text,x,y,w,h,size=24,bold=false,font='等线'){
 const sh=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 sh.text=text; sh.text.style={fontSize:`${size}pt`,typeface:font,bold,color:'#000000'};
 return sh;
}
function title(slide,text){return box(slide,text,88,38.33,1104,139.17,40,false,'等线 Light');}
function body(slide,blocks,notes){
 blocks.forEach((t,i)=>box(slide,t,88,195+i*104,1104,92,24));
 slide.speakerNotes.text=notes;
}
function add(text,blocks,notes){const s=p.slides.add();s.background.fill='#FFFFFF';title(s,text);body(s,blocks,notes);return s;}
const cover=p.slides.items[0];
const subtitle=cover.shapes.items.find(s=>s.name==='副标题 2');
subtitle.text='研究方案与阶段进展\n2026年11月17日\nPhase 00 已验收';
subtitle.text.style={fontSize:'24pt',typeface:'等线',color:'#000000',alignment:'center'};
cover.speakerNotes.text='依据原始开题汇报与项目 docs/PHASE00_REPORT.md。Phase 01—13 尚未开始；暂无交通韧性或治理实验结果。';
const bg=p.slides.items[1];
const bgBody=bg.shapes.items.find(s=>s.name==='内容占位符 2');
bgBody.text='积水导致道路降速或中断，交通绕行会改变拥堵分布及应急设施可达性。\n道路局部受灾程度与全网治理收益需要分别评价。\n核心问题：在有限预算和治理数量约束下，优先改善哪些道路，才能提高灾害全过程的网络性能？\n研究从深圳南山区小型真实路网开始，再逐步扩大。';
bgBody.text.style={fontSize:'24pt',typeface:'等线',color:'#000000'};
bg.speakerNotes.text='背景机制参考本地 Ma 2023 DOI 10.1016/j.trd.2023.103928、Hong 2024 DOI 10.3390/land13111894。原稿206.5毫米缺乏本项目独立核验来源，维护版本不作为已核实测量引用。保留原稿用于追溯。';
const route=p.slides.items[2];
const rt=route.shapes.items.find(s=>s.name==='标题 1');rt.text='研究技术路线';
const rb=route.shapes.items.find(s=>s.name==='内容占位符 2');
rb.text='真实有向路网与 OD 需求：先小区域，再扩展南山区。\n参数化内涝与道路退化：水深时序、速度和容量变化。\n时间片交通分配与综合韧性：正常基准、未满足需求、设施可达性。\n预算约束治理与验证：公平策略比较，后续以 SUMO 补充车辆过程。';
rb.text.style={fontSize:'24pt',typeface:'等线',color:'#000000'};
route.speakerNotes.text='以上均为拟实施路线。阶段定义见 PLAN.md；Phase 00 之外尚未实施。';
const lit=p.slides.add();lit.background.fill='#FFFFFF'; title(lit,'五篇本地论文与采用边界');
data.references.forEach((r,i)=>{
 box(lit,r.label,88,190+i*90,260,65,22,true);
 box(lit,r.note,365,190+i*90,827,75,21);
});
lit.speakerNotes.text=data.references.map((r,i)=>`[${i+1}] ${r.citation}\nDOI https://doi.org/${r.doi}\n定位：${r.pages}`).join('\n\n')+'\n所有PDF已本地全文核查。中文在线元数据访问失败已记录。';
add('拟实施模型与实验假设',[
 '24小时、15分钟步长：97端点、96区间；采用参数化积水情景。',
 '速度参考 Pregnolato 函数；容量退化单列。30 cm 中断阈值为可调实验假设。',
 '时间片 Frank–Wolfe 用户均衡；不可达 OD 保留并计入成本。',
 '结构、性能、功能权重拟取0.2 / 0.5 / 0.3；预算及 K 约束下重算治理收益。'
],'依据 MODEL_ASSUMPTIONS.md、PLAN.md。Pregnolato 原式 v=0.0009w²−0.5529w+86.9448，w:mm，v:km/h，PDF第7页Eq.4。工程适配需零积水正常值、正常速度上限和封路规则。Ma 的损失面积越小越好，本项目平均性能R越大越好。时间片静态均衡不等于完整动态分配。30cm不是安全建议。');
add('Phase 00 已通过基础验收',[
 `${m.tests_passed}项测试通过，0失败；1条 rasterio / affine 未来弃用警告。`,
 `${m.imports_passed}/${m.imports_total} 项依赖实际导入成功；pip check 无依赖冲突。`,
 `Python ${m.python} 独立环境；配置、单位、归档、CLI 与 GIS 读写已核验。`,
 `最终复核运行成功，耗时 ${m.runtime_seconds} 秒；Phase 01—13 未开始。`
],'来源：docs/PHASE00_REPORT.md；docs/validation/pytest-final.txt、pytest-final.xml、pip-check.txt、environment.json。验收run_id：'+data.run_id+'。所有数值来自已保存验收记录，本次文档更新没有重跑交通实验。');
const fig=p.slides.add();fig.background.fill='#FFFFFF';title(fig,'实际运行图片');
const bytes=await fs.readFile(path.join(root,data.figure));
fig.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),contentType:'image/png',alt:'Phase 00 实际内存磁盘快照与20项依赖导入检查',fit:'contain',position:{left:65,top:185,width:1150,height:470}});
box(fig,'环境检查图；尚无交通韧性与治理收益结果',88,665,1104,35,16);
fig.speakerNotes.text='实际图像：'+data.figure+'。原始数据：docs/validation/environment.json。run_id：'+data.run_id+'；观察时间2026-11-17T17:35:15+08:00，seed42。图片原始PNG/SVG及SHA256见 accepted-run-manifest.json；资源快照并非未来运行时的可用内存承诺。';
add('运行图片留存与查询',[
 '每次生成独立 run_id，保存源数据、配置、图片、日志与 manifest。',
 'PNG 用于查看，适合的曲线另存 SVG；失败结果与历次运行均保留。',
 '本地入口 results/index.html；按阶段、日期、区域、情景、策略查询。',
 '本次2个图片与6个输入指纹已验证；两次运行保留4条图像格式记录。'
],'来源：docs/ARTIFACTS.md、docs/validation/run_audit.json、docs/PHASE00_REPORT.md。两次运行PNG/SVG合计4条索引记录，非4次实验。大型results/runs未纳入Git，需本地备份；小型验收副本位于docs/validation。');
add('下一阶段与文档同步',[
 'Phase 01：公开 OSM 小区域路网、南山区边界、Sioux Falls 标准网络。',
 '验收方向、长度、平行边、稳定 edge_id 与实际可达最短路，再扩大规模。',
 '真实积水、降雨、DEM、人口、POI 和 OD 尚未获取；SUMO 可执行程序待配置。',
 '每阶段验收后同步更新 PPT、Word 与关键运行图，明确实际结果和未完成内容。'
],'来源：PLAN.md、PROGRESS.md、DATA_SOURCES.md。下一阶段需用户继续指令；当前仅完成Phase00。维护版本由 docs/deliverables/content.json 同步验收信息，根目录原稿保留。');
const candidate=path.join(tmp,'candidate.pptx');
await (await PresentationFile.exportPptx(p)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const finalPath=path.resolve(process.argv[2]||'docs/deliverables/开题与阶段汇报.pptx');
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath,pythonExecutable:python,
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 requiredNativeTableOwnerSlides:[],fontPolicy:{basis:'reference',families:['等线','等线 Light'],referencePath:original,referenceSha256:createHash('sha256').update(await fs.readFile(original)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(tmp,'presentation-validation.json')});
console.log(JSON.stringify(result));
const final=await PresentationFile.importPptx(await FileBlob.load(finalPath));
for(const [i,s] of final.slides.items.entries()){
 const b=await final.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(tmp,'slides',`slide-${i+1}.png`),new Uint8Array(await b.arrayBuffer()));
}
console.log(`Rendered ${final.slides.items.length} slides`);
