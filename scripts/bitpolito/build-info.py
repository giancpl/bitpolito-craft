#!/usr/bin/env python3
"""Attach reproducible build identity without recording secrets or local filesystem paths."""
import hashlib,json,subprocess,shutil,os
from pathlib import Path
root=Path(__file__).resolve().parents[2]
def run(*args):return subprocess.check_output(args,cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
config=json.loads((root/'brand/bitpolito/config.json').read_text())
upstream='f893f6af7d36a5409fd804e81a34fd895cfefedf'
try:upstream=run('git','merge-base','HEAD','refs/remotes/upstream/main')
except subprocess.CalledProcessError:pass
info={'commit':run('git','rev-parse','HEAD'),'upstreamCommit':upstream,'brandVersion':config['brandVersion'],'brandAudited':json.loads((root/'brand/bitpolito/config.json').read_text())['audited'],'rust':run('rustc','--version'),'trunk':run('trunk','--version'),'cargoLockSha256':hashlib.sha256((root/'Cargo.lock').read_bytes()).hexdigest(),'fontCommit':'37827adc41fd165f9a9234ac40f94dbad353aa69'}
(root/'dist/web/build-info.json').write_text(json.dumps(info,indent=2)+'\n')

# Ship required notices alongside the compiled application, including embedded font licenses.
site=root/'dist/web'
for name in ('LICENSE-MIT','LICENSE-APACHE','NOTICE','ATTRIBUTION.md'):
    shutil.copyfile(root/name,site/name)
shutil.copyfile(root/'brand/bitpolito/LICENSE',site/'BITPOLITO-LICENSE.txt')
fonts=os.environ.get('CRAFT_FONTS_DIR')
if fonts:
    for license in Path(fonts).glob('fonts/*/OFL.txt'):
        shutil.copyfile(license,site/('OFL-'+license.parent.name+'.txt'))
