#!/usr/bin/env python3
"""Optional API importer. Manual exports remain the default, and no token is needed to build.

Mappings select exact node IDs. Inspect/export only licensed, approved nodes.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from brand import BRAND, ROOT, LAYOUTS, dump, generated, import_manual, read, web


class Figma:
    def __init__(self, token):
        if not token: raise ValueError('Set FIGMA_TOKEN in the environment; do not commit it')
        self.token = token

    def get(self, path, params):
        url = 'https://api.figma.com/v1/' + path + '?' + urlencode(params)
        try:
            with urlopen(Request(url, headers={'X-Figma-Token': self.token}), timeout=60) as response:
                return json.load(response)
        except HTTPError as e:
            if e.code == 429: raise ValueError('Figma rate limit reached; retry later. The current package is unchanged.') from e
            if e.code in (401, 403): raise ValueError('Figma access denied; check the read-only token and file access') from e
            raise ValueError(f'Figma returned HTTP {e.code}; the current package is unchanged') from e

    def export(self, key, version, node_id, fmt):
        result = self.get('images/' + key, {'ids': node_id, 'version': version, 'format': fmt, 'scale': 3})
        url = result.get('images', {}).get(node_id)
        if not url or urlparse(url).scheme != 'https': raise ValueError(f'Export missing for node {node_id}')
        # Signed export URLs are downloaded without the Figma credential.
        with urlopen(url, timeout=60) as response:
            data = response.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024: raise ValueError(f'Oversized asset {node_id}')
        return data


def nodes_in(node):
    yield node
    for child in node.get('children', []):
        if child.get('visible', True): yield from nodes_in(child)


def solid(node):
    fills = [x for x in node.get('fills', []) if x.get('visible', True)]
    if len(fills) != 1 or fills[0]['type'] != 'SOLID' or fills[0].get('opacity', 1) != 1:
        raise ValueError(f'{node["id"]}: expected one opaque solid fill')
    c = fills[0]['color']
    return '#' + ''.join(f'{round(c[k]*255):02X}' for k in ('r','g','b'))


def position(node, frame):
    a, b = node['absoluteBoundingBox'], frame['absoluteBoundingBox']
    return [(a['x']-b['x'])*960/b['width'], (a['y']-b['y'])*540/b['height'], a['width']*960/b['width'], a['height']*540/b['height']]


def convert_layout(mapping, frame, all_nodes):
    if frame['type'] not in ('FRAME', 'COMPONENT'):
        raise ValueError('Mapped layouts must be Figma frames or components')
    if abs(frame['absoluteBoundingBox']['width']/frame['absoluteBoundingBox']['height'] - 16/9) > .001:
        raise ValueError('Mapped slide frames must be widescreen 16:9')
    fields = []
    covered = {frame['id']}
    for field in mapping['placeholders']:
        node = all_nodes.get(field['nodeId'])
        if not node or node['type'] != 'TEXT' or node.get('characterStyleOverrides') or node.get('effects') or node.get('rotation', 0):
            raise ValueError(f'{field["nodeId"]}: unsupported or missing editable text; map plain text explicitly')
        covered.add(node['id'])
        style = node['style']
        if style.get('textAlignHorizontal', 'LEFT') != 'LEFT':
            raise ValueError(f'{node["id"]}: align text left or adjust the supported template mapping')
        fields.append({'role': field['role'], 'rect': position(node, frame), 'size': style['fontSize']*540/frame['absoluteBoundingBox']['height'],
                       'bold': style.get('fontWeight',400)>=600, 'text':node['characters'], 'color':solid(node)})
    decorations = []
    for decoration in mapping.get('decorations', []):
        node = all_nodes.get(decoration['nodeId'])
        if not node: raise ValueError(f'Missing decoration node {decoration["nodeId"]}')
        covered.update(n['id'] for n in nodes_in(node))
        decorations.append({'asset': decoration['asset'], 'rect':position(node,frame)})
    for node in nodes_in(frame):
        if node['id'] not in covered and node['type'] not in ('GROUP', 'FRAME'):
            raise ValueError(f'Unmapped visible element {node["id"]}; map it as text or a decorative asset')
    return {'id':mapping['id'],'label':mapping['label'],'background':solid(frame),'placeholders':fields,'decorations':decorations}


def run(mapping, api, target=BRAND):
    if {x['id'] for x in mapping['layouts']} != LAYOUTS or not mapping['assets']:
        raise ValueError('Audit and populate all eight layout mappings and approved assets before importing')
    key = mapping['fileKey']
    ids = [x['nodeId'] for x in mapping['layouts'] + mapping['assets']]
    params = {'ids': ','.join(ids)}
    if mapping.get('version'): params['version'] = mapping['version']
    response = api.get('files/' + key + '/nodes', params)
    version = response['version']
    selected = {k:v['document'] for k,v in response['nodes'].items() if v}
    if set(ids) - selected.keys(): raise ValueError('Mapped Figma nodes are missing; package unchanged')
    all_nodes = {n['id']: n for frame in selected.values() for n in nodes_in(frame)}
    with tempfile.TemporaryDirectory(prefix='bitpolito-figma-') as tmp:
        staged = Path(tmp) / 'package'
        shutil.copytree(target, staged)
        pack = read(staged, 'templates.json')
        pack['layouts'] = [convert_layout(x,selected[x['nodeId']],all_nodes) for x in mapping['layouts']]
        dump(staged/'templates.json',pack)
        assets=[]
        for asset in mapping['assets']:
            node_id=asset['nodeId']; ident=asset['id']
            if not __import__('re').fullmatch('[a-z][a-z0-9-]{0,63}',ident): raise ValueError('Invalid asset ID')
            (staged/'sources'/f'{ident}.svg').write_bytes(api.export(key,version,node_id,'svg'))
            (staged/'runtime'/f'{ident}.png').write_bytes(api.export(key,version,node_id,'png'))
            assets.append({'id':ident,'label':asset['label'],'category':asset['category'],'file':f'runtime/{ident}.png'})
        dump(staged/'assets.json',{'assets':assets})
        config=read(staged,'config.json');config['audited']=True;config['designStatus']='Mapped Figma export';dump(staged/'config.json',config)
        dump(staged/'provenance.json',{'schemaVersion':1,'source':f'https://www.figma.com/design/{key}','figmaVersion':version,'nodeIds':ids,'license':mapping['license'],'hashes':{}})
        generated(staged)
        import_manual(staged,target)
    print(f'Imported Figma version {version}; review the generated package before release')


if __name__ == '__main__':
    try:
        run(read(BRAND,'mapping.json'),Figma(os.environ.get('FIGMA_TOKEN')))
        (ROOT/'apps/deckcraft-web/index.html').write_text(web(read(BRAND,'config.json')))
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(f'Figma import failed: {error}') from error
