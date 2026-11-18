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
if(p.slides.items.length!==37||data.final.sections.length!==41)throw new Error('Expected reviewed 37-slide source and 41 sections');
let coverCount=0,historyCount=0;
for(const shape of p.slides.items[0].shapes.items){
 if(shape.text.toString().includes('龙岗不含大鹏 合成OD与蓄水情景完成')){
  shape.text.replace('龙岗不含大鹏 合成OD与蓄水情景完成','龙岗不含大鹏 ERA5地形汇流原型完成');coverCount++;
 }
}
for(const shape of p.slides.items[33].shapes.items){
 if(shape.text.toString().includes('合成道路低点与独立蓄水桶，参数未实测标定。尚未计算地表汇流或管网二维耦合。')){
  shape.text.replace('合成道路低点与独立蓄水桶，参数未实测标定。尚未计算地表汇流或管网二维耦合。','本节为较早独立桶情景，参数未标定。新ERA5地形汇流原型见第38—41张。');historyCount++;
 }
}
if(coverCount!==1||historyCount!==1)throw new Error('Historical text anchors mismatch');
for(const i of [0,33])p.slides.items[i].speakerNotes.text=data.final.sections[i].paragraphs.join('\n\n');
for(const [k,s] of data.final.sections.slice(37).entries()){
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
  const side={
   0:'北京时间 2023年9月6日00时\n至9月11日00时，共120小时\n\n9个0.25°网格，1,080条雨量\n6格用于主域，4格用于区均\n\n区均累计180.10 mm\n最大区均1小时量5.964 mm\n\n再分析估计，非站点观测\n空间分片常数，小时内均匀\n\nOpen-Meteo / ECMWF ERA5\nCC BY 4.0，完整署名见备注',
   2:'150 m网格，主域66,920格\n5 km外扩，完整上游待核\n\n道路样点峰值1.0309 m\n同时暴露源线最多\n45个 >0.15 m；2个 ≥0.30 m\n\n6,848个地面源线建模\n952个桥隧等保持未知\n\n最大同时面积0.6088 km²\n峰值并集面积0.6763 km²\n150 m代理，非实测淹没',
   3:'损失能力c为2／4／8 mm/h\n道路峰值4.0988／1.0309／0.0113 m\n\n151项测试，10项运行检查\n独立原始雨量及水量审计通过\n数值通过不代表实测标定\n\n180→60秒端点差2.315 cm\n5→10 km外扩差3.935 cm\n\n120小时末仍有61.23万m³蓄水\n99.725%损失为参数设定\n不能当作实测排水效率'
  }[k];
  box(side,820,140,405,460,18);
  box({0:'ERA5约25 km再分析，小时降雨均分至180秒步长；图示末端仍有蓄水，不能宣称全部退水。',
       2:'地图为各格各自峰值，非同时淹没图；颜色截至99.5分位。源线统计不等于实测积水道路或实际封路。',
       3:'参数尚未标定，未求解二维水动力或管网；未更新道路速度容量、交通分配、韧性或SUMO。'}[k],75,635,1130,60,17);
 }else{
  box('地形与连接\n\n30 m DSM面积平均至150 m\npriority-flood建立固定D8无环树\nd=max(F−z,0)，原高程z保持\n最大阈值29.38 m或含伪洼地\n\nτ=clip(L/v,900,21600) s\nv=0.04√[max(s,0.0001)/0.01]\n假设流动尺度，非Manning求解\n\n干初始，180秒步长，481端点',75,140,535,440,20);
  box('每步雨量与蓄泄 水深单位m\n\nR=P(mm)Δt/3600/1000\nh̃=h+R；ℓ=min(h̃,cΔt/3600/1000)\nq=max(h̃−ℓ−d,0)(1−exp(−Δt/τ))\nh新=h̃−ℓ−q+Σ上游q\n\nc=4 mm/h，合并入渗和未解析排水\n同步转移，收到水下一步再下传\n\n全域降雨−损失−出域=储量变化\n无外部入流，无河潮顶托',670,140,540,440,20);
  box('固定D8与逐格阈值是简化汇流；DSM非裸地DTM，无连通洼地统一水面、二维动量或管井交换。',75,635,1130,60,17);
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
 explicitTotalSlideCount:41,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[20,22,23,24,25,26,28,29],
 fontPolicy:{basis:'reference',families:['等线','等线 Light'],referencePath:source,referenceSha256:createHash('sha256').update(await fs.readFile(source)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(stage,'validation.json')});
const checked=await PresentationFile.importPptx(await FileBlob.load(finalPath));await fs.mkdir(path.join(stage,'slides'),{recursive:true});
for(const [i,s] of checked.slides.items.entries()){
 const png=await checked.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(stage,'slides',`slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
console.log(JSON.stringify({slides:checked.slides.items.length,sha256:receipt.finalSha256}));
