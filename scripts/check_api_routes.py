#!/usr/bin/env python3
"""Compare the API routes nano-crucible calls with an API's OpenAPI document.

Usage:
    python scripts/check_api_routes.py https://crucible.lbl.gov/testapi-staging/openapi.json
    python scripts/check_api_routes.py path/to/openapi.json [--strict]

Reports routes the client calls that the API does not define (exit 1), and
routes the API marks deprecated (exit 1 with --strict). Paths built from
variables the script cannot read are listed as unchecked.
"""

import argparse
import ast
import json
import sys
import urllib.request
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / 'crucible'
REQUEST_CALLS = {'_request': (0, 1), '_api': (1, 2), '_paginate': (None, 0)}


def _path_template(node):
    """'/datasets/{}/files' for a literal or f-string path, or None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(value.value)
            else:
                parts.append('{}')
        return ''.join(parts)
    return None


def client_routes(package: Path = PACKAGE):
    """[(method, template, 'file:line')] for every API call, and unchecked calls."""
    routes, unchecked = [], []
    for source in sorted(package.rglob('*.py')):
        tree = ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call):
                continue
            name = getattr(call.func, 'attr', None) or getattr(call.func, 'id', None)
            if name not in REQUEST_CALLS:
                continue
            method_at, path_at = REQUEST_CALLS[name]
            if len(call.args) <= path_at:
                continue
            where = f'{source.relative_to(package.parent)}:{call.lineno}'
            method = 'GET'
            if method_at is not None:
                node = call.args[method_at]
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                    unchecked.append(where)
                    continue
                method = node.value.upper()
            template = _path_template(call.args[path_at])
            if template is None or not template.startswith('/'):
                unchecked.append(where)
                continue
            routes.append((method, template.split('?')[0].rstrip('/') or '/', where))
    return routes, unchecked


def _segments(path):
    return [segment for segment in path.strip('/').split('/') if segment]


def _matches(client_path, api_path):
    client, api = _segments(client_path), _segments(api_path)
    if len(client) != len(api):
        return False
    for mine, theirs in zip(client, api):
        if mine == theirs or (theirs.startswith('{') and theirs.endswith('}')) or '{}' in mine:
            continue
        return False
    return True


def load_openapi(source: str) -> dict:
    if source.startswith(('http://', 'https://')):
        with urllib.request.urlopen(source, timeout=30) as response:
            return json.load(response)
    with open(source, encoding='utf-8') as handle:
        return json.load(handle)


def check(document: dict, routes):
    operations = [(method.upper(), path, operation.get('deprecated', False))
                  for path, methods in document.get('paths', {}).items()
                  for method, operation in methods.items() if isinstance(operation, dict)]
    unknown, deprecated = [], []
    for method, template, where in routes:
        found = [op for op in operations if op[0] == method and _matches(template, op[1])]
        if not found:
            unknown.append((method, template, where))
        elif all(op[2] for op in found):
            deprecated.append((method, found[0][1], where))
    return unknown, deprecated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('openapi', help='URL or path of the API openapi.json')
    parser.add_argument('--strict', action='store_true', help='Fail on deprecated routes too')
    args = parser.parse_args(argv)
    document = load_openapi(args.openapi)
    routes, unchecked = client_routes()
    unknown, deprecated = check(document, routes)
    version = document.get('info', {}).get('version', '?')
    print(f'{len(routes)} client calls checked against API {version}; {len(unchecked)} unchecked.')
    for title, rows in (('Not in the API', unknown), ('Deprecated in the API', deprecated)):
        if rows:
            print(f'\n{title} ({len(rows)}):')
            for method, path, where in rows:
                print(f'  {method:6} {path}  ({where})')
    if unchecked:
        print('\nUnchecked (path built at run time): ' + ', '.join(unchecked))
    return 1 if unknown or (args.strict and deprecated) else 0


if __name__ == '__main__':
    sys.exit(main())
