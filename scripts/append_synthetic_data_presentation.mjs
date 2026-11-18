// Append the new scenario facts to the maintained, already reviewed deck.
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';

const root=process.cwd(), build=path.resolve(process.argv[2]), finalPath=path.resolve(process.argv[3]);
const skill=process.env.CODEX_PRESENTATION_SKILL, python=process.env.CODEX_ARTIFACT_PYTHON;
if(!skill||!python||!process.argv[3])throw new Error('Bundled runtime, build folder and new final path required');
await fs.mkdir(build,{recursive:true}); await fs.mkdir(path.dirname(finalPath),{recursive:true});
const source=path.resolve(process.argv[4]||path.join(root,'docs/deliverables/开题与阶段进展汇报.pptx'));
await fs.copyFile(source,path.join(build,'source.pptx'));
const data=JSON.parse(await fs.readFile(path.join(root,'docs/deliverables/content.json'),'utf8'));
const sections=data.final.sections.filter(s=>s.title.startsWith('补充情景 '));
const packagePath=path.join(root,data.synthetic_data_package.path);
const p=await PresentationFile.importPptx(await FileBlob.load(source));
if(p.slides.items.length!==19)throw new Error('Provide the reviewed 19-slide source as argument 4; local backup: .cache/synthetic-doc-sync/before/开题与阶段进展汇报.pptx');
function box(slide,text,x,y,w,h,size=24){
 const sh=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 sh.text=text;sh.text.style={fontSize:`${size}pt`,typeface:'等线',color:'#142936'};return sh;
}
async function csv(relative){
 const rows=(await fs.readFile(path.join(packagePath,relative),'utf8')).replace(/^\uFEFF/,'').trim().split(/\r?\n/).map(s=>s.split(','));
 const keys=rows.shift();return rows.map(r=>Object.fromEntries(keys.map((k,i)=>[k,r[i]])));
}
const rainfall=await csv('rainfall/areal_reference_rainfall_15min.csv');
const pointDepth=await csv('flood/point_depth_timeseries.csv');
const profile=await csv('demand/departure_profile_15min.csv');
const names=['general','severe','extreme'],labels=['一般 100 mm','严重 200 mm','极端 300 mm'],colors=['#4B8CAA','#E39A35','#BE4058'];
const textStyle={typeface:'等线',fontSize:17,fill:'#223746'};
const axis={textStyle,majorGridlines:{fill:'#E2E8F0',width:1},line:{fill:'#899BA8',width:1}};
function chart(slide,title,categories,series,x,y,w,h,unit,legend=true){
 return slide.charts.add('scatter',{position:{left:x,top:y,width:w,height:h},title,titleTextStyle:{...textStyle,fontSize:22},
  series:series.map(s=>({...s,xValues:categories.map(Number),values:s.values.map(v=>Number(v.toPrecision(12))),marker:{symbol:'none'}})),hasLegend:legend,legend:{position:'bottom',textStyle},
  scatterOptions:{style:'line'},xAxis:{textStyle,title:{text:'相对起点小时',textStyle},min:0,max:24,majorUnit:4,numberFormatCode:'0'},
  yAxis:{...axis,title:{text:unit,textStyle},min:0,numberFormatCode:unit==='水深 m'?'0.0':'0'},
  dataLabels:{showValue:false,textStyle},chartFill:'#FFFFFF',plotAreaFill:'#FFFFFF'});
}
for(const [i,s] of sections.entries()){
 const slide=p.slides.add();slide.background.fill='#FFFFFF';
 box(slide,s.title,75,35,1130,80,34);
 if(i===0){
  const rainSeries=names.map((name,j)=>({name:labels[j],values:rainfall.filter(r=>r.scenario===name).map(r=>Number(r.intensity_mm_h)),line:{fill:colors[j],width:2.5}}));
  const cats=Array.from({length:96},(_,j)=>String(j/4));
  chart(slide,'合成降雨过程',cats,rainSeries,65,135,560,385,'雨强 mm/h');
  const depthSeries=names.map((name,j)=>({name:labels[j],values:Array.from({length:97},(_,k)=>Math.max(...pointDepth.filter(r=>r.scenario===name&&Number(r.time_s)===k*900).map(r=>Number(r.depth_m)))),line:{fill:colors[j],width:2.5}}));
  chart(slide,'候选点最大合成水深',Array.from({length:97},(_,j)=>String(j/4)),depthSeries,655,135,560,385,'水深 m');
  box(slide,'总雨量与排水参数均为实验假设，未标定重现期。\n独立蓄水桶不解析排水管网、汇水区及河潮顶托。',85,550,1110,115,23);
 }else if(i===1){
  const bytes=await fs.readFile(path.join(root,s.figure));
  slide.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),contentType:'image/png',alt:s.caption,fit:'contain',position:{left:55,top:130,width:1170,height:445}});
  box(slide,'60个合成候选点，55点关联54条有向路段，5点未匹配。\n图示为各点事件峰值，未重跑交通分配与韧性评估。',85,585,1110,100,21);
 }else{
  box(slide,'574 × 574 完整矩阵\n568个内部TAZ及6个外部网关\n\n三套基准小时需求率\n96套15分钟期望车次矩阵\n\n保留零需求区及区内出行\n保留正常网络不可达需求',80,170,515,370,25);
  chart(slide,'24小时合成出发需求',profile.map(r=>String(Number(r.start_hour))),
   [{name:'合成出发需求',values:profile.map(r=>Number(r.total_rate_veh_h)),line:{fill:'#367DA1',width:2.5}}],625,150,570,390,'需求率 veh/h',false);
  box(slide,'区间矩阵单位是期望车次，换算小时率需除以0.25。\nOD与时间分布未实测校准，各天气情景保持相同需求。',80,565,1120,110,23);
 }
 slide.speakerNotes.text=s.paragraphs.join('\n\n')+'\n完整合成数据：'+data.synthetic_data_package.path+'\n配置：configs/synthetic_data_package.yaml；16项生成一致性检查通过，非实测标定。原始CSV存数据包中，原生图表保留全部96或97时点。';
}
const candidate=path.join(build,'candidate.pptx');await(await PresentationFile.exportPptx(p)).save(candidate);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const receipt=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath,pythonExecutable:python,
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 explicitTotalSlideCount:22,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[20,22],
 materializeLiteralChartWorkbooks:true,
 fontPolicy:{basis:'reference',families:['等线','等线 Light'],referencePath:source,referenceSha256:createHash('sha256').update(await fs.readFile(source)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(build,'validation.json')});
console.log(JSON.stringify(receipt));
const check=await PresentationFile.importPptx(await FileBlob.load(finalPath));
await fs.mkdir(path.join(build,'slides'),{recursive:true});
for(const [i,s] of check.slides.items.entries()){
 const b=await check.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(build,'slides',`slide-${i+1}.png`),new Uint8Array(await b.arrayBuffer()));
}
console.log('Rendered '+check.slides.items.length+' final slides');
