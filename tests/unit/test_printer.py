"""Unit coverage for PrintOperations and the 'crucible print barcode' command."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import printer as print_cli
from crucible.client import CrucibleClient
from crucible.resources.printer import PrintOperations

MFID = '0tkn2knjast3h0008nyq9zps2c'


@pytest.fixture
def real_client(monkeypatch):
    """A CrucibleClient with both sessions mocked, for exercising _request's
    retry= routing directly (not just that PrintOperations passes the kwarg)."""
    from crucible.config import config

    monkeypatch.setitem(config._data, 'api_url', 'https://example.test/api/v3')
    monkeypatch.setitem(config._data, 'api_key', 'test-key')
    config._data.pop('privilege_mode', None)

    client = CrucibleClient()
    client._session = MagicMock()
    client._no_retry_session = MagicMock()
    for session in (client._session, client._no_retry_session):
        session.request.return_value = MagicMock(
            ok=True, status_code=200, content=b'{}', text='{}')
        session.request.return_value.json.return_value = {}
    return client


def test_request_retry_false_uses_the_no_retry_session(real_client):
    """retry=False must bypass the shared retrying adapter entirely, not just
    skip retries after the fact -- a 502/503/504 arriving after a
    non-idempotent server-side effect (e.g. a print already published to
    MQTT) must not be retried."""
    real_client._request('post', '/print/barcode', retry=False, json={})

    real_client._no_retry_session.request.assert_called_once()
    real_client._session.request.assert_not_called()


def test_request_retry_true_by_default(real_client):
    real_client._request('get', '/datasets')

    real_client._session.request.assert_called_once()
    real_client._no_retry_session.request.assert_not_called()


def make():
    client = MagicMock()
    resource = PrintOperations(client)
    return resource, client._request


# ── PrintOperations.barcode() ───────────────────────────────────────────────


def test_barcode_sends_expected_payload():
    resource, request = make()
    request.return_value = {
        'job_id': 'job-1', 'printer_id': 'lab3-zebra', 'mfid': MFID,
        'name': 'Sample A', 'ts': 1700000000.0, 'status': 'ok', 'detail': None,
    }

    result = resource.barcode('lab3-zebra', MFID, 'Sample A')

    request.assert_called_once_with(
        'post', '/print/barcode', retry=False,
        json={'printer_id': 'lab3-zebra', 'mfid': MFID, 'name': 'Sample A'},
    )
    assert result['status'] == 'ok'
    assert result['job_id'] == 'job-1'


def test_barcode_disables_automatic_retry():
    """A lost response after the job already published to MQTT must not
    trigger a client-side retry, since that would risk a second physical
    print. See crucible.client.CrucibleClient._request's retry= kwarg."""
    resource, request = make()
    request.return_value = {
        'job_id': 'job-1', 'printer_id': 'lab3-zebra', 'mfid': MFID,
        'name': 'Sample A', 'ts': 1700000000.0, 'status': 'ok', 'detail': None,
    }

    resource.barcode('lab3-zebra', MFID, 'Sample A')

    assert request.call_args.kwargs['retry'] is False


def test_barcode_rejects_invalid_mfid_without_a_request():
    resource, request = make()

    with pytest.raises(ValueError):
        resource.barcode('lab3-zebra', 'not-an-mfid', 'Sample A')

    request.assert_not_called()


def test_barcode_allows_empty_name():
    resource, request = make()
    request.return_value = {
        'job_id': 'job-1', 'printer_id': 'lab3-zebra', 'mfid': MFID,
        'name': '', 'ts': 1700000000.0, 'status': 'ok', 'detail': None,
    }

    resource.barcode('lab3-zebra', MFID, '')

    assert request.call_args.kwargs['json']['name'] == ''


@pytest.mark.parametrize('status', ['error', 'timeout'])
def test_barcode_logs_a_warning_on_non_ok_status(caplog, status):
    resource, request = make()
    request.return_value = {
        'job_id': 'job-1', 'printer_id': 'lab3-zebra', 'mfid': MFID,
        'name': 'Sample A', 'ts': 1700000000.0, 'status': status,
        'detail': 'printer offline',
    }

    with caplog.at_level(logging.WARNING):
        result = resource.barcode('lab3-zebra', MFID, 'Sample A')

    assert result['status'] == status
    assert any('printer offline' in record.message for record in caplog.records)


def test_barcode_does_not_log_on_ok_status(caplog):
    resource, request = make()
    request.return_value = {
        'job_id': 'job-1', 'printer_id': 'lab3-zebra', 'mfid': MFID,
        'name': 'Sample A', 'ts': 1700000000.0, 'status': 'ok', 'detail': None,
    }

    with caplog.at_level(logging.WARNING):
        resource.barcode('lab3-zebra', MFID, 'Sample A')

    assert not caplog.records


# ── CLI: crucible print barcode ─────────────────────────────────────────────


def _args(**overrides):
    defaults = dict(printer_id='lab3-zebra', mfid=MFID, name='Sample A',
                     json=False, debug=False)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_cli_barcode_exits_zero_on_ok(monkeypatch, capsys):
    client = MagicMock()
    client.print.barcode.return_value = {
        'job_id': 'job-1', 'printer_id': 'lab3-zebra', 'mfid': MFID,
        'name': 'Sample A', 'ts': 1700000000.0, 'status': 'ok', 'detail': None,
    }
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)

    print_cli._execute_barcode(_args())

    output = capsys.readouterr().out
    assert 'job-1' in output
    assert 'ok' in output


def test_cli_barcode_exits_nonzero_on_timeout(monkeypatch, capsys):
    client = MagicMock()
    client.print.barcode.return_value = {
        'job_id': 'job-1', 'printer_id': 'lab3-zebra', 'mfid': MFID,
        'name': 'Sample A', 'ts': 1700000000.0, 'status': 'timeout',
        'detail': 'Requested printer not currently online.',
    }
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)

    with pytest.raises(SystemExit) as raised:
        print_cli._execute_barcode(_args())

    assert raised.value.code == 1
    output = capsys.readouterr().out
    assert 'not currently online' in output


def test_cli_barcode_json_output(monkeypatch, capsys):
    client = MagicMock()
    client.print.barcode.return_value = {
        'job_id': 'job-1', 'printer_id': 'lab3-zebra', 'mfid': MFID,
        'name': 'Sample A', 'ts': 1700000000.0, 'status': 'ok', 'detail': None,
    }
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)

    print_cli._execute_barcode(_args(json=True))

    import json
    output = json.loads(capsys.readouterr().out)
    assert output['status'] == 'ok'


def test_cli_barcode_surfaces_client_error(monkeypatch, capsys):
    client = MagicMock()
    client.print.barcode.side_effect = ValueError('mfid must be an exact 26-character MFID.')
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)

    with pytest.raises(SystemExit) as raised:
        print_cli._execute_barcode(_args(mfid='bad'))

    assert raised.value.code == 1
    output = capsys.readouterr().err
    assert 'mfid must be an exact 26-character MFID' in output
