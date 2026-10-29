#!/usr/bin/env python3
"""Activate fork protections only after a successful complete validation run."""
import json
import os
from pathlib import Path
import re
import subprocess


def gh(*args, input=None):
    result = subprocess.run(
        ['gh', 'api', *args], input=json.dumps(input) if input is not None else None,
        text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout) if result.stdout else None


def origin_repository(url):
    for prefix in ('git@github.com:', 'https://github.com/', 'ssh://git@github.com/'):
        if url.startswith(prefix):
            repo = url[len(prefix):].rstrip('/').removesuffix('.git')
            if re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
                return repo
    raise ValueError('Use a GitHub origin remote or set GITHUB_REPOSITORY=owner/repo')


def repository():
    repo = os.environ.get('GITHUB_REPOSITORY')
    if repo:
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', repo):
            raise ValueError('GITHUB_REPOSITORY must be owner/repo')
        return repo
    # gh's default for a fork can be its upstream: always resolve our origin explicitly.
    return origin_repository(subprocess.check_output(['git', 'remote', 'get-url', 'origin'], text=True).strip())


def configure():
    repo = gh(f'repos/{repository()}')['full_name']
    config = json.loads((Path(__file__).resolve().parents[2] / 'brand/bitpolito/config.json').read_text())
    if repo.casefold() == config['upstream'].casefold():
        raise ValueError('Refusing to change the original upstream repository; run setup in your fork')
    runs = gh(f'repos/{repo}/actions/workflows/bitpolito-ci.yml/runs?branch=main&status=success&per_page=1')['workflow_runs']
    head = gh(f'repos/{repo}/commits/main')['sha']
    if not runs or runs[0]['head_sha'] != head:
        raise ValueError('Run complete BitPolito validation successfully on the current main before activating automation')
    gh(f'repos/{repo}', '-X', 'PATCH', '--input', '-', input={'allow_auto_merge': True, 'allow_merge_commit': True})
    gh(f'repos/{repo}/branches/main/protection', '-X', 'PUT', '--input', '-', input={
        'required_status_checks': {'strict': True, 'contexts': ['validation', 'design-review']},
        'enforce_admins': True, 'required_pull_request_reviews': None, 'restrictions': None,
        'allow_force_pushes': False, 'allow_deletions': False,
    })
    try:
        page = gh(f'repos/{repo}/pages')
    except subprocess.CalledProcessError as error:
        if '404' not in error.stderr:
            raise
        gh(f'repos/{repo}/pages', '-X', 'POST', '--input', '-', input={'build_type': 'workflow'})
    else:
        if page['build_type'] != 'workflow':
            gh(f'repos/{repo}/pages', '-X', 'PUT', '--input', '-', input={'build_type': 'workflow'})
    print(f'Protected {repo}:main, enabled checked auto-merge, and configured GitHub Pages.')


if __name__ == '__main__':
    try:
        configure()
    except ValueError as error:
        raise SystemExit(str(error)) from error
    except subprocess.CalledProcessError as error:
        raise SystemExit('Repository setup failed: ' + (error.stderr or str(error)).strip()) from error
