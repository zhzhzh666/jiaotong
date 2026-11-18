"""Preserve original chart XML/embedded workbooks lost during deck import.

No data reconstruction: original chart and workbook bytes are copied intact.
The imported chart's title and series count must still identify the same chart.
"""
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED
import argparse
import posixpath
import xml.etree.ElementTree as ET

parser=argparse.ArgumentParser()
parser.add_argument('source',type=Path);parser.add_argument('candidate',type=Path);parser.add_argument('output',type=Path)
args=parser.parse_args()
if args.output.exists():raise FileExistsError(args.output)
ns={'c':'http://schemas.openxmlformats.org/drawingml/2006/chart','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
with ZipFile(args.source) as source, ZipFile(args.candidate) as candidate:
    payload={n:candidate.read(n) for n in candidate.namelist()}
    count=0
    for name in source.namelist():
        if not name.startswith('ppt/slides/charts/chart') or not name.endswith('.xml'):continue
        original=ET.fromstring(source.read(name)); imported=ET.fromstring(candidate.read(name))
        def title(tree):return ''.join(t.text or '' for t in tree.findall('c:chart/c:title//a:t',ns))
        assert title(original)==title(imported),(name,'chart title changed')
        assert len(original.findall('.//c:ser',ns))==len(imported.findall('.//c:ser',ns))
        relation=str(PurePosixPath(name).parent/'_rels'/(PurePosixPath(name).name+'.rels'))
        payload[name]=source.read(name);payload[relation]=source.read(relation)
        for rel in ET.fromstring(payload[relation]):
            assert rel.get('TargetMode')!='External'
            target=posixpath.normpath(posixpath.join(str(PurePosixPath(name).parent),rel.get('Target')))
            assert target.startswith('ppt/embeddings/') and target.endswith('.xlsx')
            assert target not in payload or payload[target]==source.read(target)
            payload[target]=source.read(target)
        count+=1
    types=ET.fromstring(payload['[Content_Types].xml'])
    for item in ET.fromstring(source.read('[Content_Types].xml')):
        if item.get('Extension')=='xlsx' and not any(i.get('Extension')=='xlsx' for i in types):types.append(item)
    ET.register_namespace('', 'http://schemas.openxmlformats.org/package/2006/content-types')
    payload['[Content_Types].xml']=ET.tostring(types,encoding='utf-8',xml_declaration=True)
    with ZipFile(args.output,'w',ZIP_DEFLATED) as result:
        for name,content in payload.items():result.writestr(name,content)
print(f'Preserved {count} original charts and source workbooks byte-for-byte')
