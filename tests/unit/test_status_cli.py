from types import SimpleNamespace

import pytest

from crucible.cli.status import _readiness_details, _readiness_fields, execute
from crucible.config import config


def test_readiness_fields_parses_nested_provenance():
    health = {
        "status": "ok",
        "build": {
            "api_version": "3.0.0",
            "git_commit": "a" * 40,
            "branch": "staging",
        },
        "database": {
            "status": "ok",
            "latency_ms": 2.5,
            "schema_revisions": ["d6e1f8a2c4b7"],
        },
    }

    assert _readiness_fields(health) == ("3.0.0", "ok", 2.5, True)


def test_readiness_fields_keeps_legacy_flat_compatibility():
    health = {"status": "ok", "db": "ok", "db_ms": 3.0, "version": "2.0.0"}

    assert _readiness_fields(health) == ("2.0.0", "ok", 3.0, True)


def test_readiness_fields_reports_unknown_contract():
    assert _readiness_fields({"status": "ok"}) == (None, None, None, False)


def test_readiness_details_preserves_deployment_and_schema_provenance():
    health = {
        "status": "ok",
        "build": {
            "api_version": "3.0.0",
            "git_commit": "a" * 40,
            "branch": "staging",
        },
        "database": {
            "status": "ok",
            "latency_ms": 2.5,
            "schema_revisions": ["revision-one", "revision-two"],
        },
    }

    assert _readiness_details(health) == {
        'detected': True,
        'status': 'ok',
        'api_version': '3.0.0',
        'git_commit': 'a' * 40,
        'branch': 'staging',
        'database_status': 'ok',
        'database_latency_ms': 2.5,
        'schema_revisions': ['revision-one', 'revision-two'],
    }


class Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        return self.payload


def _configure_status(monkeypatch, health, http_status=200):
    monkeypatch.setattr(config, '_data', {
        'api_url': 'https://crucible.lbl.gov/testapi-staging',
        'api_key': 'test-key',
    })
    monkeypatch.setattr(
        'requests.get',
        lambda url, timeout: Response(http_status, health),
    )
    client = SimpleNamespace(whoami=lambda: {
        'user_info': {
            'unique_id': '0000-0001-6402-3752',
            'username': 'test-user',
            'first_name': 'Test',
            'last_name': 'User',
        },
    })
    monkeypatch.setattr('crucible.client.CrucibleClient', lambda: client)


def test_status_displays_full_nested_readiness_contract(monkeypatch, capsys):
    health = {
        'status': 'ok',
        'build': {
            'api_version': '3.0.0',
            'git_commit': '9e22d69d36e2f44811d468014976622eafd17f89',
            'branch': 'staging',
        },
        'database': {
            'status': 'ok',
            'latency_ms': 6.1,
            'schema_revisions': ['a9f3c2e7b614'],
        },
    }
    _configure_status(monkeypatch, health)

    with pytest.raises(SystemExit) as exited:
        execute(SimpleNamespace())

    assert exited.value.code == 0
    output = capsys.readouterr().out
    assert 'https://crucible.lbl.gov/testapi-staging' in output
    assert 'OK reachable' in output
    assert 'OK ready' in output
    assert '3.0.0' in output
    assert 'staging' in output
    assert '9e22d69d36e2' in output
    assert '6.1 ms' in output
    assert 'a9f3c2e7b614' in output
    assert 'T. User  (@test-user)' in output


def test_status_reports_degraded_readiness_and_still_checks_authentication(monkeypatch, capsys):
    health = {
        'status': 'degraded',
        'build': {
            'api_version': '3.0.0',
            'git_commit': 'a' * 40,
            'branch': 'staging',
        },
        'database': {
            'status': 'error',
            'latency_ms': None,
            'schema_revisions': [],
        },
    }
    _configure_status(monkeypatch, health, http_status=503)

    with pytest.raises(SystemExit) as exited:
        execute(SimpleNamespace())

    assert exited.value.code == 1
    output = capsys.readouterr().out
    assert 'ERROR degraded' in output
    assert 'HTTP 503' in output
    assert 'ERROR unavailable' in output
    assert 'OK authenticated' in output


def test_status_handles_missing_api_key_as_unconfigured(monkeypatch, capsys):
    health = {
        'status': 'ok',
        'build': {'api_version': '3.0.0'},
        'database': {
            'status': 'ok',
            'latency_ms': 1.0,
            'schema_revisions': ['revision-one'],
        },
    }
    monkeypatch.setattr(config, '_data', {
        'api_url': 'https://crucible.lbl.gov/testapi-staging',
    })
    monkeypatch.setattr(
        'requests.get',
        lambda url, timeout: Response(200, health),
    )

    with pytest.raises(SystemExit) as exited:
        execute(SimpleNamespace())

    assert exited.value.code == 0
    output = capsys.readouterr().out
    assert 'INFO not configured' in output
    assert 'crucible config set api_key KEY' in output
