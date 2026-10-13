"""Create self-contained FreeCAD assemblies with exact saved SW placements."""
from build_freecad import *

def colour(name):
    s=name.lower()
    if 'pneu' in s:return (.12,.13,.15)
    if 'platine' in s or 'carte' in s or 'pcb' in s:return (.10,.43,.25)
    if 'lipo' in s:return (.20,.35,.65)
    if 'capteur' in s or 'sfh' in s or 'teft' in s:return (.22,.25,.31)
    if 'ssd' in s:return (.13,.17,.20)
    if 'dents' in s:return (.80,.72,.43)
    return (.72,.74,.78)

def configure(body):
    for o in getattr(body,'Group',[]):
        if 'Visibility' in o.PropertiesList:o.Visibility=False
    if body.TypeId=='PartDesign::Body' and body.Tip:body.Tip.Visibility=True
    body.Visibility=True

def property(obj,name,value):
    if name not in obj.PropertiesList:obj.addProperty('App::PropertyString',name,'Conversion')
    setattr(obj,name,value)

def prepare_parts():
    report=json.loads((ROOT/'reconstruction_report.json').read_text())
    extracted=json.loads((ROOT/'extraction_report.json').read_text())
    catalogue={}
    for record in extracted:
        rel=Path(record['source'])
        parametric=ROOT/'pieces'/rel.with_suffix('.FCStd')
        if parametric.exists():
            doc=App.openDocument(str(parametric))
            obj=next(o for o in doc.Objects if o.TypeId=='PartDesign::Body')
            configure(obj)
            # Dimension every full circle: radii remain directly editable.
            for sk in doc.Objects:
                if sk.TypeId!='Sketcher::SketchObject':continue
                for i,g in enumerate(sk.Geometry):
                    if isinstance(g,Part.Circle) and not any(c.Type in ('Radius','Diameter') and c.First==i for c in sk.Constraints):
                        ci=sk.addConstraint(Sketcher.Constraint('Radius',i,g.Radius))
                        sk.renameConstraint(ci,'Rayon_%03d'%(i+1))
            doc.recompute()
            doc.save()
            path=parametric;kind='parametric'
        else:
            doc=App.newDocument('Reference')
            obj=doc.addObject('PartDesign::Body','Body')
            base=obj.newObject('PartDesign::Feature','ImportedSolid')
            base.Label='Solide importe — historique non reconstruit'
            base.Shape=Part.read(str(ROOT/record['reference']))
            obj.Label=rel.stem+' [reference importee]'
            property(obj,'Source',str(rel))
            property(obj,'Reconstruction','Solide importe uniquement : aucune esquisse pilote')
            configure(obj)
            doc.Label=rel.stem+' — reference'
            path=ROOT/'composants_importes'/rel.with_suffix('.FCStd')
            path.parent.mkdir(parents=True,exist_ok=True)
            doc.recompute();doc.saveAs(str(path));kind='reference_importee'
            report=[r for r in report if r['source']!=str(rel.with_suffix('.step'))]
            report.append(dict(source=str(rel.with_suffix('.step')),status=kind,file=str(path.relative_to(ROOT)),
                               reason='Geometrie preservee ; reconstruction des fonctions non validee'))
        catalogue[str(rel).lower()]=dict(path=str(path),kind=kind)
        App.closeDocument(doc.Name)
    (ROOT/'reconstruction_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    return catalogue

def placement(value):
    a=list(map(float,value.split()))
    if len(a)!=16:raise ValueError('Unsupported transform')
    m=App.Matrix(a[0],a[4],a[8],a[12]*1000,
                 a[1],a[5],a[9],a[13]*1000,
                 a[2],a[6],a[10],a[14]*1000,0,0,0,1)
    if abs(m.determinant()-1)>1e-6:raise ValueError('Non-rigid transform')
    return App.Placement(m)

def assembly(item,catalogue,dest):
    doc=App.newDocument('Assembly')
    library=doc.addObject('App::DocumentObjectGroup','Bibliotheque')
    library.Label='Pieces sources — esquisses et fonctions'
    root=doc.addObject('App::Part','Assemblage')
    root.Label=Path(item['source']).stem
    property(root,'Source',item['source'])
    property(root,'Assemblage','Positions et hierarchie recuperees ; contraintes de liaison SolidWorks non transferees')
    masters={};stats={'source':item['source'],'instances':0,'parametric_instances':0,'reference_instances':0,'suppressed':0,'missing':[]}
    def get_master(file):
        key=file.lower()
        if key in masters:return masters[key]
        path=catalogue[key]['path']
        source=App.openDocument(path)
        obj=next(o for o in source.Objects if o.TypeId=='PartDesign::Body')
        copy=doc.copyObject(obj,True)
        App.closeDocument(source.Name)
        copy.Label=Path(file).stem+(' [reference]' if catalogue[key]['kind']!='parametric' else '')
        configure(copy);copy.Visibility=False
        library.addObject(copy)
        masters[key]=copy
        return copy
    def walk(model_id,parent,ancestors=()):
        if model_id in ancestors:raise ValueError('Assembly cycle')
        model=item['models'][model_id]
        for ref in model['children']:
            if ref.get('swSuppressed')=='YES':stats['suppressed']+=1;continue
            child=item['models'][ref['swModelRef']]
            label=ref['swName']+'-'+ref.get('swReferenceNumber','1')
            if child['children']:
                part=doc.addObject('App::Part','Subassembly');part.Label=label
                parent.addObject(part);part.Placement=placement(ref['swTransform'])
                property(part,'SourceHidden',ref.get('swHidden','NO'))
                walk(ref['swModelRef'],part,ancestors+(model_id,))
                part.Visibility=ref.get('swHidden')!='YES'
            else:
                file=child.get('file',{}).get('local')
                if not file or file.lower() not in catalogue:
                    stats['missing'].append(label);continue
                target=get_master(file)
                link=doc.addObject('App::Link','Component')
                link.setLink(target);link.Label=label
                parent.addObject(link)
                link.LinkPlacement=placement(ref['swTransform'])
                link.Visibility=ref.get('swHidden')!='YES'
                property(link,'Source',file)
                property(link,'SourceHidden',ref.get('swHidden','NO'))
                property(link,'Statut',catalogue[file.lower()]['kind'])
                stats['instances']+=1
                stats['parametric_instances' if catalogue[file.lower()]['kind']=='parametric' else 'reference_instances']+=1
    walk(item['root_model'],root)
    doc.recompute()
    for master in masters.values():master.Visibility=False
    root.Visibility=True
    doc.Label=Path(item['source']).stem
    dest.parent.mkdir(parents=True,exist_ok=True)
    doc.saveAs(str(dest))
    stats.update(file=str(dest.relative_to(ROOT)),unique_parts=len(masters),errors=[o.Name for o in doc.Objects if 'Invalid' in o.State])
    App.closeDocument(doc.Name)
    return stats

if __name__=='__main__':
    catalogue=prepare_parts()
    results=[]
    for item in json.loads((ROOT/'assembly_manifest.json').read_text()):
        dest=ROOT/'assemblages'/Path(item['source']).with_suffix('.FCStd')
        result=assembly(item,catalogue,dest);results.append(result);print(json.dumps(result),flush=True)
        if Path(item['source']).stem=='Zhonx_III_Assemblage_Final':
            # A self-contained entry point: no absolute document links.
            import shutil
            shutil.copyfile(dest,ROOT/'ZHONX_III.FCStd')
    (ROOT/'assembly_report.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
