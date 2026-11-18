import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';

const root=process.cwd(),build=path.resolve(process.argv[2]),finalPath=path.resolve(process.argv[3]);
const source=path.join(build,'before/开题与阶段进展汇报.pptx'),stage=path.join(build,process.argv[4]||'v1');
const skill=process.env.CODEX_PRESENTATION_SKILL,python=process.env.CODEX_ARTIFACT_PYTHON;
if(!skill||!python||!process.argv[3])throw new Error('Bundled runtime and output paths required');
await fs.mkdir(stage,{recursive:true});await fs.mkdir(path.dirname(finalPath),{recursive:true});
const data=JSON.parse(await fs.readFile('docs/deliverables/content.json','utf8'));
const p=await PresentationFile.importPptx(await FileBlob.load(source));
if(p.slides.items.length!==33||data.final.sections.length!==37)throw new Error('Expected reviewed 33-slide source and 37 sections');
await fs.writeFile(path.join(stage,'source-inspection.json'),JSON.stringify(await p.inspect({kind:'layout',maxChars:12000})));
let coverCount=0;
for(const shape of p.slides.items[0].shapes.items){
 if(shape.text.toString().includes('龙岗不含大鹏 合成OD完成，拓扑待核')){
  shape.text.replace('龙岗不含大鹏 合成OD完成，拓扑待核','龙岗不含大鹏 合成OD与蓄水情景完成');coverCount++;
 }
}
if(coverCount!==1)throw new Error('Cover text anchor mismatch');
p.slides.items[0].speakerNotes.text=data.final.sections[0].paragraphs.join('\n\n');
let odCount=0;
for(const shape of p.slides.items[32].shapes.items){
 if(shape.text.toString().includes('时段峰形为假设。推定拓扑待核，尚未计算龙岗积水、交通分配或韧性。')){
  shape.text.replace('时段峰形为假设。推定拓扑待核，尚未计算龙岗积水、交通分配或韧性。','时段峰形与推定拓扑待核。后续积水情景见第34—36张，交通影响尚未重算。');odCount++;
 }
}
if(odCount!==1)throw new Error('OD historical text anchor mismatch');
p.slides.items[32].speakerNotes.text=data.final.sections[32].paragraphs.join('\n\n');
for(const [k,s] of data.final.sections.slice(33).entries()){
 const slide=p.slides.add();slide.background.fill='#FFFFFF';
 function box(text,x,y,w,h,size=20){
  const shape=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  shape.text=text;shape.text.style={fontSize:`${size}pt`,typeface:'等线',color:'#142936'};
 }
 box(s.title,75,35,1130,75,34);
 if(s.figure){
  const bytes=await fs.readFile(path.join(root,s.figure));
  slide.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),contentType:'image/png',alt:s.caption,
    fit:'contain',position:{left:45,top:135,width:750,height:470}});
  const side=[
   '24小时，15分钟步长\n96区间／97端点\n\n合成雨量0／100／200／300 mm\n第5—13小时双峰雨型\n\nI=R×g×C×α\nD=min(H+I, cΔt+HΔt/τ)\nH新=H+I−D\n\n最大代理水深 m\n0.2613／0.5439／0.8266\n基准峰值均在第10.5小时',
   '250 m道路网格，4,139个代理\n道路采样33,597点\n\n6,848个地面源线建模\n952个桥隧等要素保留未知\n\n源线取关联单元最大水深\n精确连接86,807条推定图弧\n426条跨界弧单独标记\n\n尚未重算道路性能和交通影响',
   '雨停后全部曾超1 cm单元恢复\n100 mm：5.93 h\n200 mm：8.56 h\n300 mm：10.11 h\n\n慢退水τ=8 h的未恢复单元\n24小时末：38／925／1,833个\n\n五参数组，共20组过程\n5分钟复核最大端点差约1.23 cm\n141项测试及17项运行检查通过'
  ][k];
  box(side,820,140,405,450,19);
  box([
    '合成道路低点与独立蓄水桶，参数未实测标定。尚未计算地表汇流或管网二维耦合。',
    '未知水深不填0。源线数量不等于独立道路数或淹没面积，图拓扑仍待核。',
    '恢复阈值用于分析。0.30 m仅作本轮暴露统计，尚未据此实施封路或计算交通影响。'
  ][k],75,635,1130,60,17);
 }else{
  box('当前资料条件\n\n尚未取得龙岗真实管井数据\n现有公开内容为统计与质检工具入口\n\n所需字段包括管径、连接关系\n管底与井盖高程、排口及边界水位\n另需精细裸地地形和事件降雨\n\n申请渠道与草案已保存，尚未提交',75,155,535,410,21);
  box('取得资料后的实施顺序\n\n1 归档元数据与许可，核对管井拓扑\n2 选择完整排水分区建立SWMM模型\n3 构建二维网格与地表边界\n4 管井与地表双向交换，核验水量\n5 用独立积水流量资料标定和验证\n6 输出道路水深并接入交通模型',670,155,540,410,21);
  box('C方案尚未实施。当前独立桶结果保留为未标定压力情景，不能称为SWMM或二维耦合结果。',75,620,1130,65,18);
 }
 slide.speakerNotes.text=s.paragraphs.join('\n\n')+'\n来源 '+s.source_label;
}
const candidate=path.join(stage,'candidate.pptx');await(await PresentationFile.exportPptx(p)).save(candidate);
const preserved=path.join(stage,'preserved.pptx');
console.log(execFileSync(python,['scripts/preserve_existing_chart_workbooks.py',source,candidate,preserved],{encoding:'utf8'}));
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const receipt=await finalizePresentation({workspaceDir:root,candidatePath:preserved,finalPath,pythonExecutable:python,
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 explicitTotalSlideCount:37,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[20,22,23,24,25,26,28,29],
 fontPolicy:{basis:'reference',families:['等线','等线 Light'],referencePath:source,referenceSha256:createHash('sha256').update(await fs.readFile(source)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(stage,'validation.json')});
const checked=await PresentationFile.importPptx(await FileBlob.load(finalPath));await fs.mkdir(path.join(stage,'slides'),{recursive:true});
for(const [i,s] of checked.slides.items.entries()){
 const png=await checked.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(stage,'slides',`slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
console.log(JSON.stringify({slides:checked.slides.items.length,sha256:receipt.finalSha256}));
