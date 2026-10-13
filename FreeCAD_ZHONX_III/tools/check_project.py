"""Reopen deliverables, check local links, and exercise editable parameters in memory."""
from build_freecad import *
import hashlib
import argparse

def check(source_root=None):
    results=[]
    files=sorted((ROOT/'pieces').rglob('*.FCStd'))
    files+=sorted((ROOT/'composants_importes').rglob('*.FCStd'))
    files+=sorted((ROOT/'assemblages').rglob('*.FCStd'))
    files+=[ROOT/'ZHONX_III.FCStd']
    for path in files:
        doc=App.openDocument(str(path))
        doc.recompute(None,True,True)
        bodies=[o for o in doc.Objects if o.TypeId=='PartDesign::Body']
        links=[o for o in doc.Objects if o.TypeId=='App::Link']
        errors=[o.Name for o in doc.Objects if 'Invalid' in o.State]
        invalid=[o.Name for o in bodies if o.Shape.isNull() or not o.Shape.isValid()]
        broken=[o.Name for o in links if not o.LinkedObject or o.LinkedObject.Document!=doc]
        item=dict(file=str(path.relative_to(ROOT)),bodies=len(bodies),links=len(links),
                  errors=errors,invalid_shapes=invalid,external_or_broken_links=broken)
        item['accepted']=not (errors or invalid or broken)
        results.append(item)
        print(json.dumps(item),flush=True)
        App.closeDocument(doc.Name)
    # A changed extrusion and a changed sketch radius must alter the solid.
    edits=[]
    path=ROOT/'pieces/Chassis/Platine_Superieure.FCStd'
    for parameter in ['thickness','radius']:
        doc=App.openDocument(str(path))
        body=next(o for o in doc.Objects if o.TypeId=='PartDesign::Body')
        before=body.Shape.Volume
        if parameter=='thickness':
            pad=next(o for o in doc.Objects if o.TypeId=='PartDesign::Pad')
            pad.Length=pad.Length.Value+.1
        else:
            sketch=next(o for o in doc.Objects if o.TypeId=='Sketcher::SketchObject'
                        and any(c.Type=='Radius' for c in o.Constraints))
            i=next(i for i,c in enumerate(sketch.Constraints) if c.Type=='Radius')
            sketch.setDatum(i,App.Units.Quantity(sketch.Constraints[i].Value+.05))
        doc.recompute(None,True,True)
        item=dict(parameter=parameter,file=str(path.relative_to(ROOT)),before_volume=before,
                  after_volume=body.Shape.Volume,valid=body.Shape.isValid(),
                  errors=[o.Name for o in doc.Objects if 'Invalid' in o.State])
        item['accepted']=item['valid'] and not item['errors'] and abs(before-body.Shape.Volume)>1e-6
        edits.append(item)
        App.closeDocument(doc.Name) # Deliberately do not save the test modifications.
    hashes=[]
    references=[]
    for row in json.loads((ROOT/'extraction_report.json').read_text()):
        reference=ROOT/row['reference']
        references.append(dict(file=row['reference'],unchanged=reference.is_file() and
            hashlib.sha256(reference.read_bytes()).hexdigest()==row['reference_sha256']))
        if source_root is not None:
            source=source_root/row['source']
            hashes.append(dict(source=row['source'],unchanged=source.is_file() and
                hashlib.sha256(source.read_bytes()).hexdigest()==row['sha256']))
    report=dict(documents=results,edit_checks=edits,reference_checks=references,
                source_checks=hashes,source_checks_requested=source_root is not None,
                accepted=all(r['accepted'] for r in results+edits)
                and all(r['unchanged'] for r in hashes+references))
    (ROOT/'project_check_report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(accepted=report['accepted'],documents=len(results),edit_checks=edits)),flush=True)
    if not report['accepted']:raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,help='Optional restored SolidWorks source directory for SHA-256 checks')
    check(parser.parse_args().source)
