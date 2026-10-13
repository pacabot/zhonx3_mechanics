"""Read saved SolidWorks XML instance trees and their exact transforms."""
from pathlib import Path
import sys,json,zlib,argparse,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
cli=argparse.ArgumentParser(description=__doc__)
cli.add_argument('--source',type=Path,required=True,help='Restored SolidWorks source directory')
SOURCE=cli.parse_args().source
if not SOURCE.is_dir() or not any(p.suffix.lower()=='.sldasm' for p in SOURCE.rglob('*')):
    cli.error('No SolidWorks assemblies found; existing assembly manifest was preserved')
sys.path.insert(0,str(ROOT/'tools/vendor/sldprt2step'))
from sldprt2step_lib.container.ole_cfb import OleContainerParser
NS={'sw':'http://www.solidworks.com/sw2003/schema'}
inventory={str(p.relative_to(SOURCE)).lower():str(p.relative_to(SOURCE)) for p in SOURCE.rglob('*') if p.is_file()}

def local_path(windows):
    value=windows.replace('\\','/')
    marker='modelisation_zhonx_iii/'
    if marker in value.lower():
        rel=value[value.lower().index(marker)+len(marker):]
        if rel.lower() in inventory:return inventory[rel.lower()]
    matches=[v for v in inventory.values() if v.split('/')[-1].lower()==value.split('/')[-1].lower()]
    return matches[0] if len(matches)==1 else None

def extract(src):
    parser=OleContainerParser(src.read_bytes())
    stream=parser.extract_stream('COMPINSTANCETREE__ZLB')
    if stream is None:raise ValueError('No component instance tree')
    raw=zlib.decompress(stream.data[24:])
    root=ET.fromstring(raw)
    files={e.get('id'):dict(e.attrib,local=local_path(e.get('swPath',''))) for e in root.findall('./sw:swHeader/sw:swFile',NS)}
    models={e.get('id'):dict(e.attrib,file=files.get(e.get('swFileRef')),children=[c.attrib for c in e.findall('sw:swReference',NS)]) for e in root.findall('./sw:swModelList/sw:swModel',NS)}
    configs=[e.attrib for e in root.findall('./sw:swConfigurationList/sw:swConfiguration',NS)]
    active=next((c for c in configs if c.get('swMostRecentConfiguration')=='YES'),configs[0])
    return dict(source=str(src.relative_to(SOURCE)),models=models,configurations=configs,root_model=active['swModelRef'])

if __name__=='__main__':
    records=[]
    for p in sorted(SOURCE.rglob('*')):
        if p.suffix.lower()!='.sldasm':continue
        try:
            item=extract(p)
            print(item['source'],len(item['models']),'models','missing',[m['file']['swPath'] for m in item['models'].values() if m['file'] and not m['file']['local']])
        except Exception as exc:item=dict(source=str(p.relative_to(SOURCE)),error=str(exc));print(item)
        records.append(item)
    (ROOT/'assembly_manifest.json').write_text(json.dumps(records,indent=2,ensure_ascii=False))
