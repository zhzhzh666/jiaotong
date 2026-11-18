import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';

const root=process.cwd(),build=path.resolve(process.argv[2]),finalPath=path.resolve(process.argv[3]);
const skill=process.env.CODEX_PRESENTATION_SKILL,python=process.env.CODEX_ARTIFACT_PYTHON;
if(!skill||!python||!process.argv[3])throw new Error('Provide bundled runtime, build directory and new output');
await fs.mkdir(build,{recursive:true});await fs.mkdir(path.dirname(finalPath),{recursive:true});
const source=path.resolve(process.argv[4]||'docs/deliverables/开题与阶段进展汇报.pptx');
await fs.copyFile(source,path.join(build,'source.pptx'));
const data=JSON.parse(await fs.readFile(path.join(root,'docs/deliverables/content.json'),'utf8'));
const sections=data.final.sections.filter(s=>s.title.startsWith('情景建模 '));
const chartData=JSON.parse(await fs.readFile(path.join(root,data.storm_process.path,'raw/native_chart_data.json'),'utf8'));
const p=await PresentationFile.importPptx(await FileBlob.load(source));
if(p.slides.items.length!==22||sections.length!==2)throw new Error('Provide the reviewed 22-slide source as argument 4');
function box(slide,text,x,y,w,h,size=23){
 const shape=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 shape.text=text;shape.text.style={fontSize:`${size}pt`,typeface:'等线',color:'#142936'};
}
const textStyle={typeface:'等线',fontSize:17,fill:'#223746'};
function chart(slide,data,x,y,w,h,min=0){
 slide.charts.add('scatter',{position:{left:x,top:y,width:w,height:h},title:data.title,
  titleTextStyle:{...textStyle,fontSize:22},scatterOptions:{style:'line'},
  series:data.series.map(s=>({name:s.name,xValues:s.x,values:s.y.map(v=>Number(v.toPrecision(12))),
   line:{fill:s.color,width:2.5},marker:{symbol:'none'}})),
  hasLegend:true,legend:{position:'bottom',textStyle},
  xAxis:{textStyle,title:{text:'相对情景起点小时',textStyle},min,max:24,majorUnit:min?2:4,numberFormatCode:'0'},
  yAxis:{textStyle,title:{text:data.unit,textStyle},min:0,numberFormatCode:data.unit==='水深 m'?'0.0':'0',
   majorGridlines:{fill:'#E2E8F0',width:1},line:{fill:'#899BA8',width:1}},
  dataLabels:{showValue:false,textStyle},chartFill:'#FFFFFF',plotAreaFill:'#FFFFFF'});
}
for(const [i,s] of sections.entries()){
 const slide=p.slides.add();slide.background.fill='#FFFFFF';box(slide,s.title,75,35,1130,80,34);
 if(i===0){
  chart(slide,chartData[0],65,135,560,390);chart(slide,chartData[1],655,135,560,390);
  box(slide,'15分钟步长，13小时雨停，基准最大积水在10.5小时出现。\n独立假设蓄水桶；合成降雨与排水参数均未实测校准。',85,555,1110,110,22);
 }else{
  chart(slide,chartData[2],80,135,1120,395,13);
  box(slide,'基准三种暴雨雨停后约5.01 / 7.62 / 9.16小时退至1厘米。\n消退常数8小时的极端情景，24小时仍有32点超过1厘米。\n退水阈值用于过程分析；参数敏感性不等同于工程效果。',85,555,1110,130,21);
 }
 slide.speakerNotes.text=s.paragraphs.join('\n\n')+'\n数据与源码：'+data.storm_process.path+
  '\n原生图表源值：raw/native_chart_data.json。模型输出为合成实验，未重跑交通分配或治理。';
}
const candidate=path.join(build,'candidate.pptx');await(await PresentationFile.exportPptx(p)).save(candidate);
const preserved=path.join(build,'preserved-candidate.pptx');
console.log(execFileSync(python,[path.join(root,'scripts/preserve_existing_chart_workbooks.py'),source,candidate,preserved],{encoding:'utf8'}));
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const receipt=await finalizePresentation({workspaceDir:root,candidatePath:preserved,finalPath,pythonExecutable:python,
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 explicitTotalSlideCount:24,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[20,22,23,24],
 materializeLiteralChartWorkbooks:true,
 fontPolicy:{basis:'reference',families:['等线','等线 Light'],referencePath:source,referenceSha256:createHash('sha256').update(await fs.readFile(source)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(build,'validation.json')});
console.log(JSON.stringify({sha256:receipt.finalSha256,package:receipt.packageIntegrity.status,charts:receipt.nativeChartValidation.passed}));
const check=await PresentationFile.importPptx(await FileBlob.load(finalPath));await fs.mkdir(path.join(build,'slides'),{recursive:true});
for(const [i,s] of check.slides.items.entries()){
 const b=await check.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(build,'slides',`slide-${i+1}.png`),new Uint8Array(await b.arrayBuffer()));
}
console.log(`Rendered ${check.slides.items.length} slides`);
