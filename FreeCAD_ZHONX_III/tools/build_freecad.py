"""Run with the Python bundled with FreeCAD (headless)."""
import sys
from pathlib import Path
sys.path.append("/Applications/FreeCAD.app/Contents/Resources/lib")
import FreeCAD as App
import Part
import Sketcher
import json
from collections import Counter
import math
import traceback

ROOT = Path(__file__).resolve().parents[1]
V = App.Vector

def edges_to_sketch(sketch, wires, transform=None):
    """Keep analytic lines/arcs/circles and original spline geometry."""
    geometry = []
    for wire in wires:
        w = wire.copy()
        if transform:
            w.Placement = transform.multiply(w.Placement)
        for e in w.Edges:
            c = e.Curve
            if isinstance(c, Part.Line):
                g = Part.LineSegment(e.Vertexes[0].Point, e.Vertexes[-1].Point)
            elif isinstance(c, Part.Circle):
                g = c if e.isClosed() else Part.ArcOfCircle(c,e.FirstParameter,e.LastParameter)
            elif isinstance(c, Part.Ellipse):
                g = c if e.isClosed() else Part.ArcOfEllipse(c,e.FirstParameter,e.LastParameter)
            else:
                g = e.toNurbs().Edges[0].Curve
                g.segment(e.FirstParameter,e.LastParameter)
            geometry.append(g)
    sketch.addGeometry(geometry,False)
    ends=[]
    for i,g in enumerate(geometry):
        if isinstance(g,(Part.Circle,Part.Ellipse)):continue
        for j in (1,2):ends.append((i,j,sketch.getPoint(i,j)))
    repaired=set()
    for i,j,p in ends:
        for k,l,q in ends:
            if k<=i:continue
            distance=(p-q).Length
            if 1e-8<distance<1e-4 and (i,j) not in repaired and (k,l) not in repaired:
                sketch.addConstraint(Sketcher.Constraint('Coincident',i,j,k,l))
                repaired.update([(i,j),(k,l)])
    sketch.solve()
    return len(geometry)

def section_wires(shape,z):
    bb=shape.BoundBox
    section=shape.section(Part.makePlane(bb.XLength+20,bb.YLength+20,V(bb.XMin-10,bb.YMin-10,z)))
    exact=[]
    for f in shape.Faces:
        surf=f.Surface
        if type(surf).__name__=='SurfaceOfExtrusion' and abs(surf.Direction.z)>1-1e-8:
            if f.BoundBox.ZMin-1e-7<=z<=f.BoundBox.ZMax+1e-7:
                u0,u1,v0,v1=f.ParameterRange
                e=surf.BasisCurve.toShape(u0,u1)
                e.translate(V(0,0,z-e.Vertexes[0].Point.z))
                exact.append(e)
    edges=[]
    for e in section.Edges:
        if isinstance(e.Curve,Part.BSplineCurve):
            pts=[v.Point for v in e.Vertexes]
            for candidate in exact:
                if all(min((p-v.Point).Length for v in candidate.Vertexes)<1e-5 for p in pts) and abs(candidate.Length-e.Length)<1e-4:
                    e=candidate
                    break
        edges.append(e)
    wires=[Part.Wire(es) for es in Part.sortEdges(edges,1e-4)]
    for w in wires:
        if not w.isClosed():w.fix(1e-5,1e-7,1e-4)
    if not wires or not all(w.isClosed() for w in wires):
        raise ValueError('Open/empty section at '+str(z))
    return wires

def difference(a,b):
    if abs(a.Volume-b.Volume)>max(1e-5,abs(b.Volume)*1e-6):
        return abs(a.Volume-b.Volume)
    return abs(a.Volume-b.Volume)

def extrusion_layers(shape, axis):
    rot = [App.Rotation(V(0,1,0),-90),App.Rotation(V(1,0,0),90),App.Rotation()][axis]
    s=shape.copy()
    s.Placement=App.Placement(V(),rot).multiply(s.Placement)
    bounds=[s.BoundBox.ZMin,s.BoundBox.ZMax]
    for face in s.Faces:
        surf=face.Surface
        if isinstance(surf,Part.Plane) and abs(surf.Axis.z)>1-1e-8:
            bounds.append(surf.Position.z)
    zs=[]
    for z in sorted(bounds):
        if not zs or z-zs[-1]>1e-5:zs.append(z)
    if len(zs)>80:raise ValueError('Too many layers')
    layers=[]
    for lo,hi in zip(zs,zs[1:]):
        if hi-lo<1e-5:continue
        mid=(lo+hi)/2
        wires=section_wires(s,mid)
        face=Part.makeFace(wires,'Part::FaceMakerBullseye')
        face.translate(V(0,0,lo-mid))
        slab=face.extrude(V(0,0,hi-lo))
        # Section extrusion must match the complete reference slab.
        # Reject curved/tapered layers cheaply before expensive solid booleans.
        for ratio in (0.2,0.8):
            check=Part.makeFace(section_wires(s,lo+(hi-lo)*ratio),'Part::FaceMakerBullseye')
            if abs(check.Area-face.Area)>max(1e-6,face.Area*1e-7):
                raise ValueError('Non-constant section')
        layers.append((lo,hi,mid,wires,slab.Volume))
    return rot,layers

def make_layers(doc,shape,axis):
    rot,layers=extrusion_layers(shape,axis)
    body=doc.addObject('PartDesign::Body','Body')
    body.Label='Corps parametrique'
    if 'AllowCompound' in body.PropertiesList:body.AllowCompound=True
    # Start in the largest slab and grow in both directions, ensuring contact.
    idx=max(range(len(layers)),key=lambda i:layers[i][4])
    order=list(range(idx,len(layers)))+list(range(idx-1,-1,-1))
    tip=None
    for i in order:
        lo,hi,mid,wires,_=layers[i]
        sketch=doc.addObject('Sketcher::SketchObject','Sketch')
        body.addObject(sketch)
        sketch.Label='Esquisse %02d — profil mesure'%(i+1)
        base=hi if i<idx else lo
        edges_to_sketch(sketch,wires,App.Placement(V(0,0,-mid),App.Rotation()))
        sketch.Placement.Base=V(0,0,base)
        pad=body.newObject('PartDesign::Pad','Pad')
        pad.Label='Extrusion %02d — %.6g mm'%(i+1,hi-lo)
        pad.Profile=sketch
        pad.Length=hi-lo
        pad.Reversed=(i<idx)
        doc.recompute()
        if pad.Shape.isNull():raise ValueError('Pad failed: '+str(pad.State))
        tip=pad
    body.Placement=App.Placement(V(),rot.inverted())
    doc.recompute()
    delta=difference(body.Shape,shape)
    if delta>max(1e-5,abs(shape.Volume)*5e-6):raise ValueError('Rebuilt solid differs %.9g'%delta)
    return body,dict(method='layered_sketch_pads',axis=axis,features=len(layers),volume_difference_mm3=delta)

def make_revolution(doc,shape):
    # Axial parts in the source are centred on Z. Cut on the XZ half-plane.
    bb=shape.BoundBox
    plane=Part.makePlane(bb.XLength+20,bb.ZLength+20,V(bb.XMin-10,0,bb.ZMin-10),V(0,-1,0),V(1,0,0))
    section=shape.section(plane)
    # Clip section edges to x >= 0; the axial boundary closes any bore-free region.
    wires=[Part.Wire(e) for e in Part.sortEdges(section.Edges,1e-5)]
    positive=[w for w in wires if w.isClosed() and w.BoundBox.XMin>=-1e-6]
    if positive:
        half=Part.makeFace(positive,'Part::FaceMakerBullseye')
    else:
        face=Part.makeFace(wires,'Part::FaceMakerBullseye')
        half=face.common(Part.makeBox(bb.XMax+10,20,bb.ZLength+20,V(0,-10,bb.ZMin-10)))
    if not half.Faces:raise ValueError('Empty revolution profile')
    wires=[w for f in half.Faces for w in f.Wires]
    candidate=half.revolve(V(),V(0,0,1),360)
    delta=difference(candidate,shape)
    if delta>max(1e-5,abs(shape.Volume)*1e-6):raise ValueError('Not a surface of revolution: %.6g'%delta)
    body=doc.addObject('PartDesign::Body','Body')
    sketch=body.newObject('Sketcher::SketchObject','Sketch')
    sketch.Label='Esquisse — section radiale'
    placement=App.Placement(V(),App.Rotation(V(1,0,0),90))
    edges_to_sketch(sketch,wires,placement.inverse())
    sketch.Placement=placement
    rev=body.newObject('PartDesign::Revolution','Revolution')
    rev.Profile=sketch
    rev.ReferenceAxis=(sketch,['V_Axis'])
    rev.Angle=360
    doc.recompute()
    if rev.Shape.isNull():raise ValueError('Revolution failed')
    delta=difference(body.Shape,shape)
    if delta>max(1e-5,abs(shape.Volume)*1e-6):raise ValueError('Revolution mismatch %.6g'%delta)
    return body,dict(method='sketch_revolution',features=1,volume_difference_mm3=delta)

def build():
    report=json.loads((ROOT/'reconstruction_report.json').read_text()) if (ROOT/'reconstruction_report.json').exists() else []
    for p in sorted((ROOT/'references_step').rglob('*.step')):
        if '--only' in sys.argv and sys.argv[sys.argv.index('--only')+1] not in str(p):continue
        rel=p.relative_to(ROOT/'references_step')
        if '--resume' in sys.argv and any(r['source']==str(rel) for r in report):continue
        shape=Part.read(str(p))
        failures=[]
        output=None
        for mode in ['z','revolve','x','y']:
            print('TRY',rel,mode,flush=True)
            doc=App.newDocument('Conversion')
            try:
                if mode=='revolve':body,result=make_revolution(doc,shape)
                else:body,result=make_layers(doc,shape,'xyz'.index(mode))
                body.addProperty('App::PropertyString','Source','Conversion').Source=str(rel.with_suffix('.SLDPRT'))
                body.addProperty('App::PropertyString','Reconstruction','Conversion').Reconstruction='Profils mesures ; contraintes SolidWorks non transferees'
                dest=ROOT/'pieces'/rel.with_suffix('.FCStd')
                dest.parent.mkdir(parents=True,exist_ok=True)
                doc.Label=p.stem
                doc.recompute()
                doc.saveAs(str(dest))
                output=dict(source=str(rel),status='parametric',file=str(dest.relative_to(ROOT)),**result)
                break
            except Exception as exc:
                failures.append(mode+': '+str(exc))
            finally:
                App.closeDocument(doc.Name)
        if not output:output=dict(source=str(rel),status='pending',attempts=failures)
        report=[r for r in report if r['source']!=str(rel)]+[output]
        print(json.dumps(output,ensure_ascii=False),flush=True)
        (ROOT/'reconstruction_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))

def inspect():
    report = []
    for p in sorted((ROOT / "references_step").rglob("*.step")):
        try:
            s = Part.read(str(p))
            bb = s.BoundBox
            item = dict(path=str(p.relative_to(ROOT)), valid=s.isValid(), solids=len(s.Solids),
                        volume=s.Volume, bounds=[bb.XMin,bb.XMax,bb.YMin,bb.YMax,bb.ZMin,bb.ZMax],
                        surfaces=dict(Counter(type(f.Surface).__name__ for f in s.Faces)))
        except Exception as exc:
            item = dict(path=str(p.relative_to(ROOT)),error=str(exc))
        report.append(item)
        print(json.dumps(item), flush=True)
    (ROOT / "geometry_report.json").write_text(json.dumps(report, indent=2))

if __name__ == "__main__":
    if '--inspect' in sys.argv:inspect()
    else:build()
