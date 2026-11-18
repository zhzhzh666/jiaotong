import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';

const root=process.cwd(),build=path.resolve(process.argv[2]),finalPath=path.resolve(process.argv[3]);
const source=path.resolve(process.argv[4]||'docs/deliverables/开题与阶段进展汇报.pptx');
const skill=process.env.CODEX_PRESENTATION_SKILL,python=process.env.CODEX_ARTIFACT_PYTHON;
if(!skill||!python||!process.argv[3])throw new Error('Provide bundled runtime, build directory and output');
await fs.mkdir(build,{recursive:true});await fs.mkdir(path.dirname(finalPath),{recursive:true});
const data=JSON.parse(await fs.readFile(path.join(root,'docs/deliverables/content.json'),'utf8'));
const sections=data.final.sections.filter(s=>s.title.startsWith('龙岗研究区 '));
const p=await PresentationFile.importPptx(await FileBlob.load(source));
if(p.slides.items.length!==30||sections.length!==1)throw new Error('Provide the reviewed 30-slide source');
await fs.writeFile(path.join(build,'before-layout.ndjson'),JSON.stringify(await p.inspect({kind:'slide,textbox,shape,layout',search:'真实路网',maxChars:10000})));
const cover=p.slides.items[0];
let replaced=0;
for(const shape of cover.shapes.items){
  const before=shape.text.toString();
  if(before.includes('真实路网 · 参数化内涝 · 交通韧性与治理原型')){
    shape.text.replace('真实路网 · 参数化内涝 · 交通韧性与治理原型','研究区调整：龙岗含大鹏；南山结果作为历史保留');replaced++;
  }
}
if(replaced!==1)throw new Error('Expected one cover text anchor');
cover.speakerNotes.text='当前研究区：用户确认随包440307龙岗区边界，包含大鹏范围。已接收资料，龙岗拓扑/需求/仿真尚未重算。第2—30张为南山及小网历史实验，第31张为本轮接收情况。';
const section=sections[0],slide=p.slides.add();slide.background.fill='#FFFFFF';
function box(text,x,y,w,h,size=21){
  const shape=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  shape.text=text;shape.text.style={fontSize:`${size}pt`,typeface:'等线',color:'#142936'};
}
box(section.title,75,35,1130,80,34);
const bytes=await fs.readFile(path.join(root,section.figure));
slide.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),contentType:'image/png',alt:section.caption,
  fit:'contain',position:{left:55,top:135,width:735,height:535}});
box('范围：随包440307，包含大鹏。\n9,624条候选道路线，尚未建图。\n\n15个候选站／6,125条记录。\n14站标签一致，另1站待核。\n\n未新增官方OD或实测车流。\n需重建拓扑、需求与积水输入。\n南山结果保留，龙岗尚未重算。',815,150,400,480,19);
slide.speakerNotes.text=section.paragraphs.join('\n\n')+'\n'+section.source_label+'\n说明：docs/LONGGANG_DATA_INTAKE.md。图内点为地址代理位置；最近道路不是已验证受灾边。';
const candidate=path.join(build,'candidate.pptx');await(await PresentationFile.exportPptx(p)).save(candidate);
const preserved=path.join(build,'preserved.pptx');
console.log(execFileSync(python,[path.join(root,'scripts/preserve_existing_chart_workbooks.py'),source,candidate,preserved],{encoding:'utf8'}));
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const receipt=await finalizePresentation({workspaceDir:root,candidatePath:preserved,finalPath,pythonExecutable:python,
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 explicitTotalSlideCount:31,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[20,22,23,24,25,26,28,29],
 fontPolicy:{basis:'reference',families:['等线','等线 Light'],referencePath:source,referenceSha256:createHash('sha256').update(await fs.readFile(source)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(build,'validation.json')});
const checked=await PresentationFile.importPptx(await FileBlob.load(finalPath));await fs.mkdir(path.join(build,'slides'),{recursive:true});
for(const [i,s] of checked.slides.items.entries()){
 const png=await checked.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(build,'slides',`slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
console.log(JSON.stringify({slides:checked.slides.items.length,sha256:receipt.finalSha256}));
