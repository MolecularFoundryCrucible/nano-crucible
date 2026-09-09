import json
import logging
from types import SimpleNamespace

import pytest
import requests

from crucible.cli import term
from crucible.cli import _CliFormatter
from crucible.cli.helpers import fail, format_cli_error, print_cli_error, show_warning


def http_error(status, reason, payload):
    response = requests.Response()
    response.status_code = status
    response.reason = reason
    response._content = json.dumps(payload).encode()
    response.headers['Content-Type'] = 'application/json'
    return requests.HTTPError(
        '{} {}'.format(status, reason),
        response=response,
    )


def test_validation_error_preserves_status_and_field_details(capsys):
    error = http_error(422, 'Unprocessable Entity', {
        'detail': [{
            'type': 'extra_forbidden',
            'loc': ['body', 'public'],
            'msg': 'Extra inputs are not permitted',
            'input': False,
        }],
    })

    with pytest.raises(SystemExit) as raised:
        fail(
            'creating instrument',
            error,
            SimpleNamespace(debug=False, json=False),
        )

    assert raised.value.code == 1
    output = capsys.readouterr().err
    assert 'Error 422 Unprocessable Entity' in output
    assert 'Failed while creating instrument.' in output
    assert 'public' in output
    assert 'Extra inputs are not permitted' in output
    assert 'extra_forbidden' not in output


@pytest.mark.parametrize(
    ('status', 'reason', 'detail'),
    [
        (401, 'Unauthorized', 'Invalid API key'),
        (403, 'Forbidden', 'Not authorized'),
        (404, 'Not Found', 'Instrument not found'),
        (409, 'Conflict', 'Ownership requires transfer_ownership'),
        (429, 'Too Many Requests', 'Rate limit exceeded'),
        (500, 'Internal Server Error', 'Unexpected server failure'),
    ],
)
def test_http_error_contract_preserves_status(status, reason, detail):
    data = format_cli_error('', http_error(status, reason, {'detail': detail}))

    assert data['status'] == status
    assert data['reason'] == reason
    assert data['details'] == [{'message': detail}]


def test_connection_error_is_classified_without_http_status():
    data = format_cli_error(
        'connecting',
        requests.ConnectionError('Name resolution failed'),
    )

    assert data == {
        'type': 'connection_error',
        'message': 'Failed while connecting.',
        'details': [{'message': 'Name resolution failed'}],
        'reason': 'Connection failed',
    }


def test_json_error_is_structured_and_uncolored(capsys):
    error = http_error(403, 'Forbidden', {'detail': 'Not authorized'})

    with pytest.raises(SystemExit):
        fail('', error, SimpleNamespace(debug=False, json=True))

    payload = json.loads(capsys.readouterr().err)
    assert payload['error']['status'] == 403
    assert payload['error']['details'] == [{'message': 'Not authorized'}]


def test_error_and_warning_colors_use_stderr_tty(monkeypatch, capsys):
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)

    print_cli_error({
        'type': 'http_error',
        'status': 422,
        'reason': 'Unprocessable Entity',
        'message': 'Command failed.',
        'details': [{'field': 'public', 'message': 'Not permitted'}],
    })
    show_warning('Configured API is deprecated.')

    output = capsys.readouterr().err
    assert '\033[31mError 422 Unprocessable Entity\033[0m' in output
    assert '\033[1mpublic\033[0m' in output
    assert '\033[33mWarning:\033[0m Configured API is deprecated.' in output


@pytest.mark.parametrize(('level', 'message', 'styled_prefix'), [
    (logging.ERROR, 'Request failed', '\033[31mError:\033[0m'),
    (logging.WARNING, 'Retrying request', '\033[33mWarning:\033[0m'),
])
def test_cli_logging_uses_semantic_prefixes(level, message, styled_prefix, monkeypatch):
    monkeypatch.setattr(term, '_tty', lambda stream=None: True)
    record = logging.LogRecord('crucible', level, '', 0, message, (), None)

    rendered = _CliFormatter('%(message)s').format(record)

    assert rendered == f'{styled_prefix} {message}'


def test_no_color_environment_disables_ansi(monkeypatch):
    class Tty:
        def isatty(self):
            return True

    original = term._COLOR_ENABLED
    monkeypatch.setenv('NO_COLOR', '1')
    monkeypatch.setattr(term, '_interactive', lambda stream=None: True)
    term.configure_color(True)

    try:
        assert term.red('Error', stream=Tty()) == 'Error'
        rendered = term.navigation_link('MFID', 'https://example.invalid')
        assert '\033[36m' not in rendered
        assert '\033[4m' not in rendered
        assert '\033]8;;https://example.invalid\007MFID\033]8;;\007' == rendered
    finally:
        term._COLOR_ENABLED = original
