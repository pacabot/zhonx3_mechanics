"""Bidirectional sampled surface distance, volume and native shape validation."""
from build_freecad import *

def samples(shape,limit=500):
    points=[]
    for edge in shape.Edges:
        if edge.Length<1e-8:
            points.extend(v.Point for v in edge.Vertexes)
        else:points.extend(edge.discretize(Number=5))
    # Surface mesh vertices are sampled ON the analytic face; triangle interiors
    # are not used, since they would measure tessellation chordal error.
    points.extend(shape.tessellate(.05)[0])
    step=max(1,len(points)//limit)
    return points[::step]

def compare(a,b,limit=500):
    distances=[]
    counts=[]
    worst=[]
    for src,dst in [(a,b),(b,a)]:
        shell=Part.makeCompound(dst.Faces)
        maximum=0
        worst_point=None
        pts=samples(src,limit)
        for p in pts:
            dist=Part.Vertex(p).distToShape(shell)[0]
            if dist>maximum:maximum=dist;worst_point=list(p)
        distances.append(maximum);counts.append(len(pts));worst.append(worst_point)
    delta=abs(a.Volume-b.Volume)
    return dict(valid=a.isValid(),solids=len(a.Solids),volume_mm3=a.Volume,
                reference_volume_mm3=b.Volume,volume_difference_mm3=delta,
                relative_volume_difference=delta/max(abs(b.Volume),1e-12),
                sampled_surface_distance_mm=max(distances),directed_distances_mm=distances,
                sample_counts=counts,worst_points=worst)

if __name__=='__main__':
    report=[]
    for p in sorted((ROOT/'pieces').rglob('*.FCStd')):
        if '--only' in sys.argv and sys.argv[sys.argv.index('--only')+1] not in str(p):continue
        ref=ROOT/'references_step'/p.relative_to(ROOT/'pieces').with_suffix('.step')
        doc=App.openDocument(str(p))
        body=next(o for o in doc.Objects if o.TypeId=='PartDesign::Body')
        doc.recompute(None,True,True)
        result=compare(body.Shape,Part.read(str(ref)))
        result.update(file=str(p.relative_to(ROOT)),sketches=sum(o.TypeId=='Sketcher::SketchObject' for o in doc.Objects),
                      errors=[o.Name for o in doc.Objects if 'Invalid' in o.State])
        result['accepted']=result['valid'] and result['solids']==1 and not result['errors'] and result['sampled_surface_distance_mm']<.01 and result['relative_volume_difference']<1e-4
        print(json.dumps(result),flush=True)
        report.append(result)
        (ROOT/'validation_report.json').write_text(json.dumps(report,indent=2))
        App.closeDocument(doc.Name)
    (ROOT/'validation_report.json').write_text(json.dumps(report,indent=2))
