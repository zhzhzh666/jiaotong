import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {FileBlob,PresentationFile} from '@oai/artifact-tool';
const root=process.cwd(),tmp=path.join(root,'.cache/doc-sync'),skill=process.env.CODEX_PRESENTATION_SKILL,python=process.env.CODEX_ARTIFACT_PYTHON;
if(!skill||!python)throw new Error('Bundled artifact runtime required');
await fs.mkdir(path.join(tmp,'final-slides'),{recursive:true});
const data=JSON.parse(await fs.readFile(path.join(root,'docs/deliverables/content.json'),'utf8'));
const original=path.join(root,'开题汇报.pptx'),p=await PresentationFile.importPptx(await FileBlob.load(original));
function box(slide,text,x,y,w,h,size=24,font='等线'){
 const sh=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 sh.text=text;sh.text.style={fontSize:`${size}pt`,typeface:font,color:'#000000'};return sh;
}
function set(sh,text,size=24){sh.text=text;sh.text.style={fontSize:`${size}pt`,typeface:'等线',color:'#000000'};}
const sections=data.final.sections;
for(let i=0;i<sections.length;i++){
 const s=sections[i],slide=i<3?p.slides.items[i]:p.slides.add();slide.background.fill='#FFFFFF';
 if(i===0){
  const title=slide.shapes.items.find(x=>x.name==='标题 1')||slide.shapes.items[0];set(title,s.title,40);
  const subtitle=slide.shapes.items.find(x=>x.name==='副标题 2');set(subtitle,s.slide_points.slice(0,3).join('\n'),24);
 }else if(i<3){
  set(slide.shapes.items.find(x=>x.name==='标题 1'),s.title,40);
  set(slide.shapes.items.find(x=>x.name==='内容占位符 2'),s.slide_points.join('\n'),24);
 }else{
  box(slide,s.title,88,38,1104,130,36,'等线 Light');
  if(s.figure){
   const bytes=await fs.readFile(path.join(root,s.figure));const mime=s.figure.endsWith('.jpg')?'image/jpeg':'image/png';
   slide.images.add({blob:bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),contentType:mime,alt:s.caption,fit:'contain',position:{left:65,top:165,width:1150,height:435}});
   box(slide,s.slide_points.join('\n'),88,615,1104,90,19);
  }else{
   s.slide_points.forEach((text,j)=>box(slide,text,88,185+j*96,1104,90,i===sections.length-1?20:24));
  }
 }
 slide.speakerNotes.text=s.paragraphs.join('\n\n')+'\n'+(s.figure?'实际运行图片：'+s.figure+'。'+s.caption:'')+'\n共享证据 docs/deliverables/content.json。运行ID：'+Object.entries(data.final.runs).map(([k,v])=>k+':'+v).join('; ');
}
const candidate=path.join(tmp,'final-candidate.pptx');await(await PresentationFile.exportPptx(p)).save(candidate);
const finalPath=path.resolve(process.argv[2]||'docs/deliverables/final-checked.pptx');
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const receipt=await finalizePresentation({workspaceDir:root,candidatePath:candidate,finalPath,pythonExecutable:python,
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],explicitTotalSlideCount:sections.length,
 requiredNativeTableOwnerSlides:[],fontPolicy:{basis:'reference',families:['等线','等线 Light'],referencePath:original,referenceSha256:createHash('sha256').update(await fs.readFile(original)).digest('hex')},
 verifyArtifactToolImport:true,receiptPath:path.join(tmp,path.basename(finalPath)+'.validation.json')});
console.log(JSON.stringify(receipt));
const check=await PresentationFile.importPptx(await FileBlob.load(finalPath));
for(const [i,s] of check.slides.items.entries()){
 const b=await check.export({slide:s,format:'png',scale:1});await fs.writeFile(path.join(tmp,'final-slides',`slide-${i+1}.png`),new Uint8Array(await b.arrayBuffer()));
}
console.log('Rendered '+check.slides.items.length+' final slides');
