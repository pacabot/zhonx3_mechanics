"""Rebuild the turned wheel and motor from the extracted analytic surfaces."""
from build_freecad import *

def poly(points):
    pts=[V(*p) for p in points]
    return Part.Wire([Part.makeLine(a,b) for a,b in zip(pts,pts[1:]+pts[:1])])

def revolve_profile(doc,body,wires,name,placement=None,subtractive=False):
    placement=placement or App.Placement(V(),App.Rotation(V(1,0,0),90))
    sk=body.newObject('Sketcher::SketchObject','Sketch')
    sk.Label=name+' — esquisse'
    edges_to_sketch(sk,wires,placement.inverse())
    sk.Placement=placement
    rev=body.newObject('PartDesign::Groove' if subtractive else 'PartDesign::Revolution','Groove' if subtractive else 'Revolution')
    rev.Label=name
    rev.Profile=sk
    rev.ReferenceAxis=(sk,['V_Axis'])
    rev.Angle=360
    doc.recompute()
    if rev.Shape.isNull():raise ValueError(rev.getStatusString())
    return rev

def pocket(doc,body,wires,top,depth,name):
    sk=body.newObject('Sketcher::SketchObject','Sketch')
    sk.Label=name+' — esquisse'
    edges_to_sketch(sk,wires)
    sk.Placement.Base=V(0,0,top)
    f=body.newObject('PartDesign::Pocket','Pocket')
    f.Label=name
    f.Profile=sk
    f.Length=depth
    doc.recompute()
    if f.Shape.isNull():raise ValueError(f.getStatusString())
    return f

def jante(doc,source):
    body=doc.addObject('PartDesign::Body','Body')
    # Both B-spline meridians are read directly from the source, not sampled.
    curves=[]
    for i in (3,86):
        e=source.Faces[i].Surface.BasisCurve.toShape()
        e.rotate(V(),V(0,0,1),-90)
        curves.append(e)
    z=5.0177251514056165
    r=8.99931410280726
    points=[(10,0,0),(10,0,7.5),(10.4,0,7.5),(10.4,0,8.5),
            (9.09931410280726,0,8.5),(9.09931410280726,0,2),(r,0,2)]
    edges=[Part.makeLine(V(*a),V(*b)) for a,b in zip(points,points[1:])]
    edges.append(curves[0])
    points=[(4,0,6.5),(4,0,11.5),(3,0,11.5),(3,0,9),(2.75,0,9),
            (2.75,0,7.5),(3,0,7.5),(3,0,z),(4,0,z)]
    edges.extend(Part.makeLine(V(*a),V(*b)) for a,b in zip(points,points[1:]))
    edges.append(curves[1])
    edges.append(Part.makeLine(V(r,0,0),V(10,0,0)))
    wire=Part.Wire(Part.__sortEdges__(edges))
    revolve_profile(doc,body,[wire],'Profil tourne de la jante')
    edges=[]
    for face in source.Faces[4:84]:
        surf=face.Surface
        if isinstance(surf,Part.Cylinder):
            a,b,c,d=face.ParameterRange
            pts=[surf.value(t,(c+d)/2) for t in (a,(a+b)/2,b)]
            edges.append(Part.Arc(*[V(p.x,p.y,0) for p in pts]).toShape())
        elif isinstance(surf,Part.Plane):
            pts=[]
            for vertex in face.Vertexes:
                p=V(vertex.Point.x,vertex.Point.y,0)
                if not any((p-q).Length<1e-4 for q in pts):pts.append(p)
            assert len(pts)==2
            edges.append(Part.makeLine(*pts))
    wires=[Part.Wire(es) for es in Part.sortEdges(edges,1e-4)]
    assert len(wires)==10 and all(w.isClosed() for w in wires)
    pocket(doc,body,wires,7.5,7.5001,'Dix ouvertures de la jante')
    pocket(doc,body,[poly([(-5,-.5,0),(5,-.5,0),(5,.5,0),(-5,.5,0)])],11.5,2.5,'Fentes du moyeu')
    return body

def motor(doc,source):
    body=doc.addObject('PartDesign::Body','Body')
    rz=[(0,-2.4),(7.45,-2.4),(7.45,0),(7.95,0),(7.95,2),(8.5,2.55),
        (8.5,17),(3,17),(3,18),(1.5,18),(1.5,18.2),(1.75,18.2),
        (1.75,19.1),(.75,19.1),(.75,25.1),(0,25.1)]
    revolve_profile(doc,body,[poly([(r,0,z) for r,z in rz])],'Corps et arbre moteur')
    centers=[]
    wires=[]
    for f in source.Faces:
        surf=f.Surface
        if isinstance(surf,Part.Cylinder) and abs(surf.Radius-.625)<1e-8:
            c=surf.Center
            centers.append(V(c.x,c.y,14.5))
            wires.append(Part.Wire(Part.makeCircle(.625,V(c.x,c.y,0))))
    assert len(wires)==6
    pocket(doc,body,wires,17,2.5,'Six percages de fixation')
    depth=.625/math.tan(math.radians(59))
    for i,c in enumerate(centers):
        triangle=poly([(c.x,c.y,c.z),(c.x+.625,c.y,c.z),(c.x,c.y,c.z-depth)])
        placement=App.Placement(c,App.Rotation(V(1,0,0),90))
        revolve_profile(doc,body,[triangle],'Pointe de foret %d'%(i+1),placement,True)
    pocket(doc,body,[poly([(-10,-10,0),(10,-10,0),(10,-5.85,0),(-10,-5.85,0)])],0,2.4,'Meplat du flasque arriere')
    return body

def battery(doc,source):
    body=doc.addObject('PartDesign::Body','Body')
    sk=body.newObject('Sketcher::SketchObject','Sketch')
    sk.Label='Encombrement de la batterie — 36 x 20 mm'
    edges_to_sketch(sk,[poly([(-36,-20,0),(0,-20,0),(0,0,0),(-36,0,0)])])
    pad=body.newObject('PartDesign::Pad','Pad');pad.Profile=sk;pad.Length=4.2
    doc.recompute()
    edges=['Edge%d'%(i+1) for i,e in enumerate(pad.Shape.Edges) if e.BoundBox.ZLength<1e-6]
    fillet=body.newObject('PartDesign::Fillet','Fillet');fillet.Base=(pad,edges);fillet.Radius=2
    doc.recompute()
    if fillet.Shape.isNull():raise ValueError(fillet.getStatusString())
    return body

def sensor(doc,source):
    body=doc.addObject('PartDesign::Body','Body')
    sphere=next(f.Surface for f in source.Faces if isinstance(f.Surface,Part.Sphere))
    r=sphere.Radius
    flange_top=source.Faces[0].BoundBox.ZMin
    flange_bottom=source.Faces[3].BoundBox.ZMin
    edges=[Part.Arc(V(0,0,0),V(r/math.sqrt(2),0,r-r/math.sqrt(2)),V(r,0,r)).toShape(),
           Part.makeLine(V(r,0,r),V(r,0,flange_bottom)),
           Part.makeLine(V(r,0,flange_bottom),V(0,0,flange_bottom)),
           Part.makeLine(V(0,0,flange_bottom),V(0,0,0))]
    revolve_profile(doc,body,[Part.Wire(edges)],'Boitier optique')
    sk=body.newObject('Sketcher::SketchObject','Sketch')
    sk.Label='Contour de la collerette'
    edges_to_sketch(sk,[source.Faces[0].OuterWire],App.Placement(V(0,0,-flange_top),App.Rotation()))
    sk.Placement.Base=V(0,0,flange_bottom)
    pad=body.newObject('PartDesign::Pad','Pad');pad.Label='Collerette';pad.Profile=sk;pad.Length=flange_top-flange_bottom
    doc.recompute()
    # Each lead is a constant extrusion along X, including the bent versions.
    for xmin in (-1.57,.97):
        faces=[f for f in source.Faces if isinstance(f.Surface,Part.Plane) and abs(f.Surface.Axis.x)>.99 and abs(f.BoundBox.XMin-xmin)<1e-5 and f.BoundBox.ZMin>=flange_top-1e-6]
        face=max(faces,key=lambda f:f.Area)
        placement=App.Placement(V(xmin,0,0),App.Rotation(V(0,0,1),V(1,0,0)))
        sk=body.newObject('Sketcher::SketchObject','Sketch');sk.Label='Profil de patte'
        edges_to_sketch(sk,face.Wires,placement.inverse());sk.Placement=placement
        pad=body.newObject('PartDesign::Pad','Pad');pad.Label='Patte';pad.Profile=sk;pad.Length=.6
        doc.recompute()
    return body

def pad_wires(doc,body,wires,base,length,name):
    sk=body.newObject('Sketcher::SketchObject','Sketch');sk.Label=name+' — esquisse'
    edges_to_sketch(sk,wires);sk.Placement.Base=V(0,0,base)
    pad=body.newObject('PartDesign::Pad','Pad');pad.Label=name;pad.Profile=sk;pad.Length=length
    doc.recompute()
    if pad.Shape.isNull():raise ValueError(pad.getStatusString())
    return pad

def screw(doc,source):
    body=doc.addObject('PartDesign::Body','Body')
    p=lambda r,z:V(r,0,z)
    edges=[]
    points=[p(0,0),p(.65,0),p(.8,.15),p(.8,2.9)]
    edges.extend(Part.makeLine(a,b) for a,b in zip(points,points[1:]))
    d=.1/math.sqrt(2)
    edges.append(Part.Arc(p(.8,2.9),p(.9-d,2.9+d),p(.9,3)).toShape())
    edges.append(Part.makeLine(p(.9,3),p(1.4,3)))
    edges.append(Part.Arc(p(1.4,3),p(1.4+d,3.1-d),p(1.5,3.1)).toShape())
    edges.append(Part.makeLine(p(1.5,3.1),p(1.5,4.4)))
    edges.append(Part.Arc(p(1.5,4.4),p(1.4+d,4.4+d),p(1.4,4.5)).toShape())
    edges.extend([Part.makeLine(p(1.4,4.5),p(0,4.5)),Part.makeLine(p(0,4.5),p(0,0))])
    revolve_profile(doc,body,[Part.Wire(edges)],'Corps de vis et tete arrondie')
    r=.8/math.cos(math.pi/6)
    wire=poly([(r*math.cos(math.radians(30+i*60)),r*math.sin(math.radians(30+i*60)),0) for i in range(6)])
    cut=pocket(doc,body,[wire],4.5,.8,'Empreinte hexagonale')
    edges=['Edge%d'%(i+1) for i,e in enumerate(cut.Shape.Edges) if e.BoundBox.ZMin>3.69 and all(v.Point.x**2+v.Point.y**2<1.1**2 for v in e.Vertexes)]
    fillet=body.newObject('PartDesign::Fillet','Fillet');fillet.Base=(cut,edges);fillet.Radius=.1
    doc.recompute()
    if fillet.Shape.isNull():raise ValueError(fillet.getStatusString())
    return body

def trackball(doc,source):
    body=doc.addObject('PartDesign::Body','Body')
    pad_wires(doc,body,[poly([(-6.7,-5.5,0),(6.7,-5.5,0),(6.7,5.5,0),(-6.7,5.5,0)])],-4.5,1,'Semelle')
    wires=section_wires(source,-1)
    for w in wires:w.translate(V(0,0,1))
    pad_wires(doc,body,wires,-3.5,3.5,'Boitier')
    top=source.common(Part.makeBox(30,30,10,V(-15,-15,0)))
    sec=top.section(Part.makePlane(30,30,V(-15,0,-10),V(0,-1,0),V(1,0,0)))
    wires=[Part.Wire(es) for es in Part.sortEdges(sec.Edges,1e-5)]
    face=Part.makeFace([w for w in wires if w.isClosed()],'Part::FaceMakerBullseye')
    half=face.common(Part.makeBox(15,30,20,V(0,-15,-5)))
    positive=[w for f in half.Faces for w in f.Wires]
    if not positive:raise ValueError('Missing top section')
    revolve_profile(doc,body,positive,'Bille et collerette')
    return body

def nut(doc,source):
    body=doc.addObject('PartDesign::Body','Body')
    wires=section_wires(source,1)
    for w in wires:w.translate(V(0,0,-1))
    pad=pad_wires(doc,body,wires,0,2,'Hexagone perce')
    rings=[Part.Wire(Part.makeCircle(r)) for r in (2.2,1)]
    raw_boss=pad_wires(doc,body,rings,2,.5,'Collet de freinage')
    edge_names=['Edge%d'%(i+1) for i,e in enumerate(raw_boss.Shape.Edges) if e.BoundBox.ZLength<1e-6 and (abs(e.BoundBox.ZMin)<1e-6 or (abs(e.BoundBox.ZMin-2)<1e-6 and isinstance(e.Curve,Part.Line)))]
    fillet=body.newObject('PartDesign::Fillet','Fillet');fillet.Base=(raw_boss,edge_names);fillet.Radius=.2
    doc.recompute()
    if fillet.Shape.isNull():raise ValueError(fillet.getStatusString())
    boss=fillet
    edge_names=['Edge%d'%(i+1) for i,e in enumerate(boss.Shape.Edges) if e.BoundBox.ZMin>1.79 and e.BoundBox.ZMax<2.01 and all(abs(math.hypot(v.Point.x,v.Point.y)-2.2)<1e-4 for v in e.Vertexes)]
    print('NUT shoulder edges',edge_names,flush=True)
    fillet=body.newObject('PartDesign::Fillet','Fillet');fillet.Base=(boss,edge_names);fillet.Radius=.1
    doc.recompute()
    if fillet.Shape.isNull():raise ValueError(fillet.getStatusString())
    cut=pocket(doc,body,[Part.Wire(Part.makeCircle(2))],2.5,.1,'Logement de bague')
    edge_names=['Edge%d'%(i+1) for i,e in enumerate(cut.Shape.Edges) if e.BoundBox.ZLength<1e-6 and (abs(e.BoundBox.ZMin-2.5)<1e-5 or (abs(e.BoundBox.ZMin-2.4)<1e-5 and isinstance(e.Curve,Part.Circle) and abs(e.Curve.Radius-1)<1e-5))]
    fillet=body.newObject('PartDesign::Fillet','Fillet');fillet.Base=(cut,edge_names);fillet.Radius=.04
    doc.recompute()
    if fillet.Shape.isNull():raise ValueError(fillet.getStatusString())
    return body

def save_special(name,fn):
    source=Part.read(str(ROOT/'references_step'/(name+'.step')))
    doc=App.newDocument('Special')
    try:
        body=fn(doc,source)
        doc.recompute()
        delta=abs(body.Shape.Volume-source.Volume)
        print(name,'valid',body.Shape.isValid(),'volumes',body.Shape.Volume,source.Volume,'delta',delta,flush=True)
        if not body.Shape.isValid() or delta>max(.002,source.Volume*5e-5):raise ValueError('Mismatch '+str(delta))
        if 'Source' not in body.PropertiesList:body.addProperty('App::PropertyString','Source','Conversion')
        if 'Reconstruction' not in body.PropertiesList:body.addProperty('App::PropertyString','Reconstruction','Conversion')
        body.Source=name+'.SLDPRT'
        body.Reconstruction='Esquisses et fonctions reconstruites a partir des surfaces de reference'
        dest=ROOT/'pieces'/(name+'.FCStd')
        dest.parent.mkdir(parents=True,exist_ok=True)
        doc.Label=name.split('/')[-1]
        doc.saveAs(str(dest))
        report=json.loads((ROOT/'reconstruction_report.json').read_text())
        report=[r for r in report if r['source']!=name+'.step']
        report.append(dict(source=name+'.step',status='parametric',file=str(dest.relative_to(ROOT)),method='revolution_pockets',volume_difference_mm3=delta))
        (ROOT/'reconstruction_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    finally:App.closeDocument(doc.Name)

def mirrored_layers(right_name):
    def build(doc,source):
        right=App.openDocument(str(ROOT/'pieces'/right_name))
        try:
            original=next(o for o in right.Objects if o.TypeId=='PartDesign::Body')
            body=doc.copyObject(original,True)
        finally:App.closeDocument(right.Name)
        for obj in body.Group:
            if obj.TypeId=='Sketcher::SketchObject':
                placement=obj.Placement
                placement.Base.z=1.5-placement.Base.z
                obj.Placement=placement
            elif obj.TypeId=='PartDesign::Pad':obj.Reversed=not obj.Reversed
        doc.recompute()
        return body
    return build

if __name__=='__main__':
    for name,fn in [('Roue/Jante',jante),('Transmission/1717TSR',motor),('Composants/Lipo_210mAh_30x20x5',battery),
                    ('Composants/M2x3,5',screw),('Composants/TrackBall',trackball),
                    ('Transmission/Ecrou_M2',nut),
                    ('Composants/SFH4545',sensor),('Composants/TEFT4300',sensor),
                    ('Composants/Capteurs_Distance_V2/SFH4545',sensor),('Composants/Capteurs_Distance_V2/TEFT4300',sensor),
                    ('Transmission/Entretoise_Gauche',mirrored_layers('Transmission/Entretoise_Droite.FCStd')),
                    ('Transmission/Intercalaire_Gauche - Copie',mirrored_layers('Transmission/Intercalaire_Droit.FCStd'))]:
        if '--only' in sys.argv and sys.argv[sys.argv.index('--only')+1] not in name:continue
        try:save_special(name,fn)
        except Exception:traceback.print_exc()
