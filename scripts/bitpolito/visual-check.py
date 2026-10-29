#!/usr/bin/env python3
"""Render real starter slides at fixed size; CI never refreshes approved references."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser();parser.add_argument('--update',action='store_true');args=parser.parse_args()
if args.update and os.environ.get('CI'):raise SystemExit('CI cannot approve visual references')
output=ROOT/'.local/visual';output.mkdir(parents=True,exist_ok=True)
actual={}
for starter in ('bitpolito-talk','bitpolito-workshop'):
    dest=output/(starter+'.png')
    subprocess.run(['cargo','run','--locked','-q','-p','deckcraft-cli','--','run','--cmd','file.new='+json.dumps({'template':starter}),
                    '--export',str(dest),'--export-params',json.dumps({'all':True,'scale':1})],cwd=ROOT,check=True)
    for image in sorted(output.glob(starter+'*.png')):
        actual[image.name]=hashlib.sha256(image.read_bytes()).hexdigest()
reference=ROOT/'tests/bitpolito/visual.json'
if args.update:
    reference.write_text(json.dumps(actual,indent=2)+'\n');print('Updated visual references; inspect the rendered slides before committing.')
else:
    expected=json.loads(reference.read_text())
    if expected!=actual:
        raise SystemExit('Visual regression: inspect .local/visual and deliberately update references after design review.')
    print(f'Visual references: {len(actual)} slides match')
