import warnings
from unittest.mock import MagicMock

import pytest
import requests

import crucible.client as client_module
from crucible import CrucibleAPIError
from crucible.client import CrucibleClient

API = 'https://crucible.example.test/api/v3'


def response(status=200, body=b'{}', headers=None):
    reply = requests.Response()
    reply.status_code = status
    reply.reason = {200: 'OK', 403: 'Forbidden', 404: 'Not Found'}.get(status, '')
    reply._content = body
    reply.headers.update(headers or {})
    return reply


@pytest.fixture
def client(monkeypatch):
    instance = CrucibleClient(API, 'the-key')
    monkeypatch.setattr(instance._session, 'request', MagicMock(return_value=response()))
    monkeypatch.setattr(instance._no_retry_session, 'request', MagicMock(return_value=response()))
    monkeypatch.setattr(client_module, '_deprecations_seen', set())
    return instance


@pytest.mark.parametrize('method', ['get', 'put', 'delete'])
def test_repeatable_methods_use_the_retrying_session(client, method):
    client._request(method, '/datasets')

    client._session.request.assert_called_once()
    client._no_retry_session.request.assert_not_called()


@pytest.mark.parametrize('method', ['post', 'patch'])
def test_writes_without_a_key_never_repeat_after_a_lost_response(client, method):
    client._request(method, '/datasets', json={})

    client._no_retry_session.request.assert_called_once()
    client._session.request.assert_not_called()


def test_a_keyed_post_may_be_retried(client):
    client._request('post', '/datasets/x/postprocess', headers={'Idempotency-Key': 'k1'})

    client._session.request.assert_called_once()


def test_the_no_retry_session_retries_only_what_never_reached_the_server():
    instance = CrucibleClient(API, 'the-key')
    retry = instance._no_retry_session.get_adapter('https://x').max_retries

    assert retry.status_forcelist == {429}
    assert retry.read == 0
    assert retry.other == 0
    assert retry.connect == 3


def test_requests_identify_the_client(client):
    for session in (client._session, client._no_retry_session):
        prepared = session.prepare_request(requests.Request('GET', f'{API}/account'))
        assert prepared.headers['User-Agent'].startswith('nano-crucible/')


def test_api_errors_carry_status_code_detail_and_request_id(client):
    client._session.request.return_value = response(
        403, b'{"detail": {"code": "hub_session_required", "message": "needs a session"}}',
        {'X-Request-ID': 'req-123'})

    with pytest.raises(CrucibleAPIError) as caught:
        client._request('get', '/account/apikeys')

    error = caught.value
    assert isinstance(error, requests.HTTPError)
    assert (error.status, error.code, error.request_id) == (403, 'hub_session_required', 'req-123')
    assert error.detail['message'] == 'needs a session'
    assert str(error).startswith('403 Forbidden: ')


def test_an_error_without_a_body_still_raises_the_typed_error(client):
    client._session.request.return_value = response(404, b'')

    with pytest.raises(CrucibleAPIError) as caught:
        client._request('get', '/datasets/missing')

    assert caught.value.status == 404
    assert caught.value.code is None


def test_deprecated_routes_warn_once_with_the_date_sunset_and_link(client):
    client._session.request.return_value = response(headers={
        'Deprecation': '@1791763200',
        'Sunset': 'Wed, 30 Jun 2027 00:00:00 GMT',
        'Link': '<https://docs.example.test/keys>; rel="deprecation"'})

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        client._request('get', '/datasets/0tkvpezyz1zzf00076nahf85j4/relationships')
        client._request('get', '/datasets/0tcbwt4cp9x1z000bazhkv5gkg/relationships')

    messages = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(messages) == 1
    assert 'GET /datasets/{id}/relationships' in messages[0]
    assert 'since 2026-10-12' in messages[0]
    assert 'removed after Wed, 30 Jun 2027' in messages[0]
    assert 'https://docs.example.test/keys' in messages[0]


def test_cli_errors_show_the_request_id(capsys):
    from crucible.cli.helpers import format_cli_error, print_cli_error
    error = CrucibleAPIError.from_response(response(404, b'{"detail": "Not found"}', {'X-Request-ID': 'req-9'}))

    data = format_cli_error('reading the dataset', error)
    print_cli_error(data)

    assert data['request_id'] == 'req-9'
    assert 'Request ID: req-9' in capsys.readouterr().err
