#!/usr/bin/env python3
"""Run in a clean Actions checkout. Preserve upstream ancestry and merge only behind CI."""
import json,os,re,subprocess
from pathlib import Path

def run(*args,check=True):
    return subprocess.run(args,check=check,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

def main():
    root=Path(__file__).resolve().parents[2]
    config=json.loads((root/'brand/bitpolito/config.json').read_text())
    repo=os.environ['GITHUB_REPOSITORY']
    if not re.fullmatch(r'[\w.-]+/[\w.-]+',config['upstream']):raise ValueError('Invalid upstream repository')
    protection=json.loads(run('gh','api',f'repos/{repo}/branches/main').stdout)
    required=protection.get('protection',{}).get('required_status_checks',{}).get('contexts',[])
    if not protection.get('protected') or not {'validation','design-review'} <= set(required):
        raise SystemExit('Configure required validation/design-review checks before enabling unattended upstream merging')
    branch='automation/deckcraft-main'
    run('git','fetch','origin','main')
    run('git','fetch','origin',f'+refs/heads/{branch}:refs/remotes/origin/{branch}',check=False)
    run('git','fetch','https://github.com/'+config['upstream']+'.git',config['upstreamBranch'])
    upstream=run('git','rev-parse','FETCH_HEAD').stdout.strip()
    if run('git','merge-base','--is-ancestor',upstream,'origin/main',check=False).returncode==0:
        print('Already follows upstream main');return
    run('git','config','user.name','BitPolito updater')
    run('git','config','user.email','bitpolito-updater@users.noreply.github.com')
    run('git','checkout','-B',branch,'origin/main')
    merged=run('git','merge','--no-edit',upstream,check=False)
    conflict=merged.returncode!=0
    if conflict:
        run('git','merge','--abort')
        # A draft PR from the upstream tip preserves the exact conflicting commits for review.
        run('git','reset','--hard',upstream)
    run('git','push','--force-with-lease','origin',f'HEAD:refs/heads/{branch}')
    listed=json.loads(run('gh','pr','list','--repo',repo,'--head',branch,'--state','open','--json','number').stdout)
    body=f'Integrates `{config["upstream"]}:{config["upstreamBranch"]}` at `{upstream}`.\n\n'
    body+=('Merge conflicts require maintainer resolution. Automatic merging is disabled.' if conflict else 'Automatic merge requires all protected-branch checks and an up-to-date branch. Preserve the merge commit; do not squash.')
    bodyfile=root/'.local/upstream-pr.md';bodyfile.parent.mkdir(exist_ok=True);bodyfile.write_text(body)
    if listed:
        number=str(listed[0]['number'])
        run('gh','pr','edit',number,'--repo',repo,'--body-file',str(bodyfile))
        if conflict:
            run('gh','pr','merge',number,'--repo',repo,'--disable-auto',check=False)
            run('gh','pr','ready',number,'--repo',repo,'--undo',check=False)
        else:run('gh','pr','ready',number,'--repo',repo,check=False)
    else:
        args=['gh','pr','create','--repo',repo,'--base','main','--head',branch,'--title','Sync Deckcraft main','--body-file',str(bodyfile)]
        if conflict:args.append('--draft')
        run(*args)
        number=branch
    if not conflict:run('gh','pr','merge',number,'--repo',repo,'--auto','--merge')

if __name__=='__main__':main()
