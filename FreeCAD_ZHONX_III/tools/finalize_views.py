"""Persist solid body display for assembly links, without changing geometry."""
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]

def finalize(path):
    with zipfile.ZipFile(path) as archive:
        contents={item.filename:archive.read(item.filename) for item in archive.infolist()}
    document=ET.fromstring(contents['Document.xml'])
    bodies={o.get('name') for o in document.findall('./Objects/Object') if o.get('type')=='PartDesign::Body'}
    gui=ET.fromstring(contents['GuiDocument.xml'])
    for provider in gui.findall('./ViewProviderData/ViewProvider'):
        if provider.get('name') in bodies:
            value=provider.find("./Properties/Property[@name='DisplayModeBody']/Integer")
            if value is not None:value.set('value','1') # Tip: render the body's complete solid.
        if provider.get('name')=='Bibliotheque':
            provider.find("./Properties/Property[@name='Visibility']/Bool").set('value','true')
    for obj in document.findall('./ObjectData/Object'):
        if obj.get('name')=='Bibliotheque':
            obj.find("./Properties/Property[@name='Visibility']/Bool").set('value','true')
    contents['GuiDocument.xml']=ET.tostring(gui,encoding='utf-8',xml_declaration=True)
    contents['Document.xml']=ET.tostring(document,encoding='utf-8',xml_declaration=True)
    temp=path.with_suffix('.view-tmp')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in contents.items():archive.writestr(name,data)
    temp.replace(path)

if __name__=='__main__':
    for path in list((ROOT/'assemblages').rglob('*.FCStd'))+[ROOT/'ZHONX_III.FCStd']:
        finalize(path)
        print(path.relative_to(ROOT))
