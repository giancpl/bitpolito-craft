#!/usr/bin/env python3
"""Activate repository protections only after a successful complete validation run."""
import json,subprocess

def gh(*args,input=None):
    p=subprocess.run(['gh','api',*args],input=json.dumps(input) if input is not None else None,text=True,capture_output=True,check=True)
    return json.loads(p.stdout) if p.stdout else None
repo=gh('repos/{owner}/{repo}')['full_name']
workflow=gh(f'repos/{repo}/actions/workflows/bitpolito-ci.yml/runs?branch=main&status=success&per_page=1')['workflow_runs']
head=gh(f'repos/{repo}/commits/main')['sha']
if not workflow or workflow[0]['head_sha']!=head:
    raise SystemExit('Run the complete BitPolito validation successfully on the current main before activating automation.')
gh(f'repos/{repo}', '-X','PATCH','--input','-',input={'allow_auto_merge':True,'allow_merge_commit':True})
gh(f'repos/{repo}/branches/main/protection','-X','PUT','--input','-',input={
 'required_status_checks':{'strict':True,'contexts':['validation','design-review']},'enforce_admins':True,
 'required_pull_request_reviews':None,'restrictions':None,'allow_force_pushes':False,'allow_deletions':False})
try:
    page=gh(f'repos/{repo}/pages')
    if page['build_type']!='workflow':
        gh(f'repos/{repo}/pages','-X','PUT','--input','-',input={'build_type':'workflow'})
except subprocess.CalledProcessError:
    gh(f'repos/{repo}/pages','-X','POST','--input','-',input={'build_type':'workflow'})
print('Protected main, enabled checked auto-merge, and configured GitHub Pages. Set BITPOLITO_ENABLED=true to enable the fork workflows.')
