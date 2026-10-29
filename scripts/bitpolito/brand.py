#!/usr/bin/env python3
"""Validate/build the brand package or import a manually exported package atomically.

Normal builds use only committed files. No Figma connection is required.
"""
import argparse
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BRAND = ROOT / 'brand/bitpolito'
LAYOUTS = {'cover', 'section', 'content', 'columns', 'image', 'diagram', 'quote', 'closing'}
STARTERS = {'bitpolito-blank', 'bitpolito-talk', 'bitpolito-workshop'}


def read(root, name):
    return json.loads((root / name).read_text())


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f'Missing or unsafe package path: {name}')
    return path


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', value):
        raise ValueError(f'Invalid stable identifier: {value!r}')
    return value


def unique(items):
    ids = [identifier(x['id']) for x in items]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate stable identifiers')
    return set(ids)


def rect(values):
    if len(values) != 4 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in values):
        raise ValueError('Geometry must contain four finite numbers')
    x, y, w, h = values
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 960.01 or y + h > 540.01:
        raise ValueError(f'Geometry exceeds the slide: {values}')


def color(value):
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError(f'Invalid color: {value!r}')


def validate(root):
    config, pack, assets = read(root, 'config.json'), read(root, 'templates.json'), read(root, 'assets.json')['assets']
    if config['schemaVersion'] != 1 or pack['schemaVersion'] != 1 or config['font'] != 'Inter':
        raise ValueError('Expected schema version 1 and the bundled Inter font')
    color(config['accent']); color(config['darkAccent'])
    tokens = read(root, 'tokens.json')
    for value in tokens['colors'].values(): color(value)
    if tokens['colors']['primary'] != config['accent'] or tokens['typography']['family'] != config['font']:
        raise ValueError('Tokens and application branding must agree on primary color and font')
    if config['defaultTemplate'] not in STARTERS:
        raise ValueError('Unknown default starter')
    if not isinstance(config['title'], str) or not config['title'].strip():
        raise ValueError('Application title is required')
    if unique(pack['layouts']) != LAYOUTS or unique(pack['starters']) != STARTERS:
        raise ValueError('The package must define the eight layouts and three BitPolito starters')
    for layout in pack['layouts']:
        color(layout['background'])
        if not any(f['role'] == 'title' for f in layout['placeholders']):
            raise ValueError(f'{layout["id"]}: missing editable title')
        for field in layout['placeholders']:
            rect(field['rect']); color(field['color'])
            if field['role'] not in {'title', 'subtitle', 'body', 'caption', 'footer'}:
                raise ValueError('Unsupported editable placeholder role')
            if not isinstance(field['size'], (float, int)) or not math.isfinite(field['size']) or not 1 <= field['size'] <= 200:
                raise ValueError('Invalid font size')
            if not isinstance(field['text'], str) or not isinstance(field['bold'], bool):
                raise ValueError('Invalid placeholder text or weight')
        for decoration in layout.get('decorations', []):
            rect(decoration['rect'])
    for starter in pack['starters']:
        if not starter['layouts'] or any(x not in LAYOUTS for x in starter['layouts']):
            raise ValueError('Starter references an unknown layout')
    ids = unique(assets)
    if not {'logo-blue', 'logo-white'} <= ids:
        raise ValueError('Both official logo variants are required')
    for layout in pack['layouts']:
        if any(x['asset'] not in ids for x in layout.get('decorations', [])):
            raise ValueError('Layout references an unknown decoration asset')
    for asset in assets:
        if asset['file'] != f'runtime/{asset["id"]}.png':
            raise ValueError('Runtime paths must match their stable asset IDs')
        data = inside(root, asset['file']).read_bytes()
        if len(data) > 16 * 1024 * 1024 or data[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError(f'{asset["id"]}: expected a PNG under 16 MiB')
        w, h = struct.unpack('>II', data[16:24])
        if not 0 < w <= 8192 or not 0 < h <= 8192:
            raise ValueError('Invalid or oversized runtime image')
        if 'slideSize' in asset:
            sw, sh = asset['slideSize']
            if w != round(sw * 3) or h != round(sh * 3):
                raise ValueError(f'{asset["id"]}: export a PNG at 3× its intended slide size')
    for path in (root / 'sources').glob('*.svg'):
        text = path.read_text().lower()
        if any(x in text for x in ('<script', '<foreignobject', '<!entity', 'javascript:', 'http://', 'https://')):
            # SVG namespace declarations are metadata, not external resources.
            cleaned = re.sub(r'xmlns(?::\w+)?=[\"\']https?://[^\"\']+[\"\']', '', text)
            if any(x in cleaned for x in ('<script', '<foreignobject', '<!entity', 'javascript:', 'http://', 'https://')):
                raise ValueError(f'Unsafe SVG content in {path.name}')
    if read(root, 'provenance.json')['license'] not in {'CC0-1.0', 'CC-BY-4.0', 'CC-BY-SA-4.0', 'MIT OR Apache-2.0'}:
        raise ValueError('The package needs a documented open asset license')
    if not (root / 'LICENSE').is_file():
        raise ValueError('Missing asset license text')
    return config, pack, assets


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for name in ('sources', 'runtime') for p in sorted((root / name).glob('*')) if p.suffix in {'.svg', '.png'}}


def registry(assets):
    rows = ['const ASSETS: &[Asset] = &[']
    for a in assets:
        # serde/Rust source strings share JSON escapes except Unicode escapes; retain Unicode.
        values = [json.dumps(a[k], ensure_ascii=False) for k in ('id', 'label', 'category')]
        rows.append('    Asset { id: %s, label: %s, category: %s, bytes: include_bytes!("%s.png") },' % (*values, a['id']))
    rows.append('];\n')
    return '\n'.join(rows)


def generated(root):
    config, _, assets = validate(root)
    (root / 'runtime/registry.rs').write_text(registry(assets))
    provenance = read(root, 'provenance.json'); provenance['hashes'] = hashes(root)
    dump(root / 'provenance.json', provenance)
    return config


def web(config):
    title = html.escape(config['title'])
    return f'''<!DOCTYPE html>
<!-- Generated by scripts/bitpolito/brand.py build from brand/bitpolito/config.json. -->
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link data-trunk rel="rust" data-bin="deckcraft-web" data-wasm-opt="z" data-weak-refs>
<link data-trunk rel="icon" href="../../brand/bitpolito/sources/bull.svg">
<link data-trunk rel="copy-file" href="../../brand/bitpolito/runtime/logo-blue.png">
<style>html,body{{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#eef0ff}}#deckcraft_canvas{{position:absolute;inset:0;width:100%;height:100%;display:block}}#deckcraft_loading{{position:absolute;inset:0;display:flex;flex-direction:column;gap:24px;align-items:center;justify-content:center;color:{config['accent']};font:18px system-ui,sans-serif}}#deckcraft_loading img{{width:240px;height:auto}}</style>
</head><body><canvas id="deckcraft_canvas"></canvas><div id="deckcraft_loading"><img src="logo-blue.png" alt="BitPolito"><span>Loading {title}…</span></div></body></html>
'''


def import_manual(source, target=BRAND):
    source = source.resolve()
    # First validate everything without touching the last known good package.
    validate(source)
    with tempfile.TemporaryDirectory(prefix='.import-', dir=target.parent) as tmp:
        staged = Path(tmp) / target.name
        staged.mkdir()
        for name in ('config.json', 'tokens.json', 'templates.json', 'assets.json', 'mapping.json', 'provenance.json', 'LICENSE'):
            shutil.copyfile(inside(source, name), staged / name)
        for directory in ('sources', 'runtime'):
            (staged / directory).mkdir()
            for path in (source / directory).iterdir():
                if path.suffix in {'.svg', '.png'}:
                    shutil.copyfile(inside(source, str(path.relative_to(source))), staged / directory / path.name)
        generated(staged)
        # Swap directories, rolling back if the second rename fails. No partial imports.
        backup = Path(tmp) / 'previous'
        target.rename(backup)
        try:
            staged.rename(target)
        except BaseException:
            backup.rename(target)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'build', 'import-manual'])
    parser.add_argument('source', type=Path, nargs='?')
    args = parser.parse_args()
    if args.command == 'import-manual':
        if not args.source: parser.error('import-manual requires an export directory')
        import_manual(args.source)
    if args.command == 'check':
        _, _, assets = validate(BRAND)
        if (BRAND / 'runtime/registry.rs').read_text() != registry(assets):
            raise ValueError('Generated asset registry differs; run brand.py build')
        if read(BRAND, 'provenance.json')['hashes'] != hashes(BRAND):
            raise ValueError('Asset hashes changed; run brand.py build and review the change')
        if (ROOT / 'apps/deckcraft-web/index.html').read_text() != web(read(BRAND, 'config.json')):
            raise ValueError('Generated HTML differs; run brand.py build')
    else:
        config = generated(BRAND)
        (ROOT / 'apps/deckcraft-web/index.html').write_text(web(config))
    print('BitPolito brand package: valid')

if __name__ == '__main__':
    try: main()
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(f'Brand update failed; inspect the package: {error}') from error
