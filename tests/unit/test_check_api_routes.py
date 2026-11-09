import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'check_api_routes.py'
spec = importlib.util.spec_from_file_location('check_api_routes', SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_client_calls_are_extracted_with_methods_and_templates():
    routes, _ = checker.client_routes()

    found = {(method, path) for method, path, _ in routes}
    assert ('POST', '/account/apikeys') in found
    assert ('DELETE', '/account/apikeys/{}') in found
    assert ('GET', '/datasets') in found


def test_routes_are_matched_by_shape_and_deprecations_reported():
    document = {'paths': {
        '/datasets/{mfid}': {'get': {}},
        '/account/apikey': {'get': {'deprecated': True}},
    }}
    routes = [('GET', '/datasets/{}', 'a:1'), ('GET', '/account/apikey', 'b:2'),
              ('POST', '/datasets/{}', 'c:3'), ('GET', '/nowhere', 'd:4')]

    unknown, deprecated = checker.check(document, routes)

    assert [row[2] for row in unknown] == ['c:3', 'd:4']
    assert [row[2] for row in deprecated] == ['b:2']
