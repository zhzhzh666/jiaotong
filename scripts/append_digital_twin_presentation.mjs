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
if(p.slides.items.length!==53||data.final.sections.length!==56)throw new Error('Expected reviewed 53-slide source and 56 sections');
let coverCount=0;
for(const shape of p.slides.items[0].shapes.items){
 if(shape.text.toString().includes('龙岗代表片区 SUMO五组试验完成')){
  shape.text.replace('龙岗代表片区 SUMO五组试验完成','龙岗片区 SUMO与三维回放已核验');coverCount++;
 }
}
if(coverCount!==1)throw new Error(`Cover anchor mismatch ${coverCount}`);
p.slides.items[0].speakerNotes.text=data.final.sections[0].paragraphs.join('\n\n');
for(const s of data.final.sections.slice(53)){
 const slide=p.slides.add();slide.background.fill='#FFFFFF';
 function box(text,x,y,w,h,size=20){
  const shape=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  shape.text=text;shape.text.style={fontSize:`${size}pt`,typeface:'等线',color:'#142936'};
 }
 box(s.title,75,35,1130,75,34);
 if(s.figure){
  const bytes=await fs.readFile(path.join(root,s.figure));
  slide.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),contentType:s.figure.endsWith('.jpg')?'image/jpeg':'image/png',alt:s.caption,
    fit:'contain',position:{left:45,top:130,width:750,height:475}});
  box(s.ppt_left,820,145,405,460,18);
 }else{
  box(s.ppt_left,75,135,535,475,20);
  box(s.ppt_right,670,135,540,475,20);
 }
 box(s.ppt_footer,75,635,1130,60,17);
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
 explicitTotalSlideCount:56,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[20,22,23,24,25,26,28,29],
 fontPolicy:{basis:'reference',families:['等线','等线 Light'],referencePath:source,referenceSha256:createHash('sha256').update(await fs.readFile(source)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(stage,'validation.json')});
const checked=await PresentationFile.importPptx(await FileBlob.load(finalPath));await fs.mkdir(path.join(stage,'slides'),{recursive:true});
for(const [i,s] of checked.slides.items.entries()){
 const png=await checked.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(stage,'slides',`slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
console.log(JSON.stringify({slides:checked.slides.items.length,sha256:receipt.finalSha256}));
