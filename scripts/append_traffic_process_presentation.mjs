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
const sections=data.final.sections.filter(s=>s.title.startsWith('交通评估 '));
const chartData=JSON.parse(await fs.readFile(path.join(root,data.traffic_process.path,'raw/native_chart_data.json'),'utf8'));
const p=await PresentationFile.importPptx(await FileBlob.load(source));
if(p.slides.items.length!==27||sections.length!==3)throw new Error('Provide the reviewed 27-slide source as argument 4');
function box(slide,text,x,y,w,h,size=23){
 const shape=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 shape.text=text;shape.text.style={fontSize:`${size}pt`,typeface:'等线',color:'#142936'};
}
const textStyle={typeface:'等线',fontSize:17,fill:'#223746'};
function chart(slide,data,x,y,w,h){
 slide.charts.add('scatter',{position:{left:x,top:y,width:w,height:h},title:data.title,
  titleTextStyle:{...textStyle,fontSize:22},scatterOptions:{style:'line'},
  series:data.series.map(s=>({name:s.name,xValues:s.x.map(v=>Number(v.toPrecision(12))),values:s.y.map(v=>Number(v.toPrecision(12))),
   line:{fill:s.color,width:2.5},marker:{symbol:'none'}})),
  hasLegend:true,legend:{position:'bottom',textStyle},
  xAxis:{textStyle,title:{text:data.x_label||'相对情景起点小时',textStyle},min:0,max:data.x_max||24,
   majorUnit:data.x_step||4,numberFormatCode:data.x_max?'0.0':'0'},
  yAxis:{textStyle,title:{text:data.unit,textStyle},min:data.title.includes('综合')?Math.floor(Math.min(...data.series.flatMap(s=>s.y))*10000)/10000-.00005:0,numberFormatCode:data.title.includes('综合')?'0.0000':data.title.includes('比例')?'0.0000':'0',
   majorGridlines:{fill:'#E2E8F0',width:1},line:{fill:'#899BA8',width:1}},
  dataLabels:{showValue:false,textStyle},chartFill:'#FFFFFF',plotAreaFill:'#FFFFFF'});
}
for(const [i,s] of sections.entries()){
 const slide=p.slides.add();slide.background.fill='#FFFFFF';box(slide,s.title,75,35,1130,80,34);
 if(i<2){
  chart(slide,chartData[2*i],65,130,560,390);chart(slide,chartData[2*i+1],655,130,560,390);
  const result=data.traffic_process.report,byScenario=Object.fromEntries(result.scenario_summary.map(r=>[r.scenario,r]));
  box(slide,i===0?
   `四种天气共384个区间，完成${result.unique_solved_states}次独立均衡求解。\n一般、严重、极端R为${['general','severe','extreme'].map(s=>byScenario[s].R.toFixed(6)).join(' / ')}。\n每区间对照同需求正常道路，采用起点状态保持。`:
   `全天${byScenario.normal.total_vehicles.toFixed(2)}期望车次，未删除区内与不可达需求。\n逐时片核对已服务、未服务与区内需求记账。\nv/c使用当时退化容量，独立时片之间不传递排队。`,85,550,1120,135,21);
 }else{
  const bytes=await fs.readFile(path.join(root,s.figure));
  slide.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),
   contentType:'image/png',alt:s.caption,fit:'contain',position:{left:65,top:125,width:1150,height:440}});
  box(slide,'黑色为关闭边，彩色为相对同需求正常基准的分配流量变化。\n54条关联边由合成积水驱动，其余边假设原状。未实测校准。',85,585,1120,95,21);
 }
 slide.speakerNotes.text=s.paragraphs.join('\n\n')+'\n数据与源码：'+data.traffic_process.path+
  '\n原生图表源值：raw/native_chart_data.json。过程图连接15分钟区间起点指标。采用区间起点保持、独立UE，未重新开展治理优化或SUMO。';
}
const candidate=path.join(build,'candidate.pptx');await(await PresentationFile.exportPptx(p)).save(candidate);
const preserved=path.join(build,'preserved-candidate.pptx');
console.log(execFileSync(python,[path.join(root,'scripts/preserve_existing_chart_workbooks.py'),source,candidate,preserved],{encoding:'utf8'}));
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const receipt=await finalizePresentation({workspaceDir:root,candidatePath:preserved,finalPath,pythonExecutable:python,
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 explicitTotalSlideCount:30,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[20,22,23,24,25,26,28,29],
 materializeLiteralChartWorkbooks:true,
 fontPolicy:{basis:'reference',families:['等线','等线 Light'],referencePath:source,referenceSha256:createHash('sha256').update(await fs.readFile(source)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(build,'validation.json')});
console.log(JSON.stringify({sha256:receipt.finalSha256,package:receipt.packageIntegrity.status,charts:receipt.nativeChartValidation.passed}));
const check=await PresentationFile.importPptx(await FileBlob.load(finalPath));await fs.mkdir(path.join(build,'slides'),{recursive:true});
for(const [i,s] of check.slides.items.entries()){
 const b=await check.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(build,'slides',`slide-${i+1}.png`),new Uint8Array(await b.arrayBuffer()));
}
console.log(`Rendered ${check.slides.items.length} slides`);
