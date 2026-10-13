"""Extract intermediate STEP references; does not reconstruct feature history."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import argparse

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True,help='Restored SolidWorks source directory')
parser.add_argument('--converter',type=Path,default=ROOT/'tools/vendor/sldprt2step/sldprt2step.py')
args=parser.parse_args()
SOURCE=args.source
CONVERTER=args.converter
if not SOURCE.is_dir() or not any(p.suffix.lower()=='.sldprt' for p in SOURCE.rglob('*')):
    parser.error('No SolidWorks parts found; existing extraction report was preserved')
records = []
for src in sorted(SOURCE.rglob("*")):
    if src.suffix.lower() != ".sldprt":
        continue
    rel = src.relative_to(SOURCE)
    dest = ROOT / "references_step" / rel.with_suffix(".step")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        run = subprocess.run([sys.executable, str(CONVERTER), str(src), "-o", str(dest), "--json"],
                             capture_output=True, text=True, timeout=120)
        result = json.loads(run.stdout)
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    result.update(source=str(rel), sha256=hashlib.sha256(src.read_bytes()).hexdigest(),
                  reference=str(dest.relative_to(ROOT)))
    if result.get('ok') and dest.is_file():
        result['reference_sha256']=hashlib.sha256(dest.read_bytes()).hexdigest()
    records.append(result)
    print(rel, result.get("ok"), result.get("faces"), result.get("error", ""), flush=True)
    (ROOT / "extraction_report.json").write_text(json.dumps(records, indent=2, ensure_ascii=False))
