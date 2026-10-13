"""Unit coverage for the signed multipart upload flow and its fallback."""

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

import google_crc32c
import pytest
import requests

from crucible.resources.gcs import signed_multipart as sm
from crucible.resources.gcs import upload as dispatch

DSID = '0tkn2knjast3h0008nyq9zps2c'
BASE = f'/datasets/{DSID}/upload/multipart'
DATA = b'abcdefghij'
RECORD = {'mfid': 'f1', 'filename': 'data.bin'}


def crc(data):
    return base64.b64encode(google_crc32c.Checksum(data).digest()).decode()


def http_error(status, detail='', retry_after=None):
    response = SimpleNamespace(status_code=status, reason='Reason', text=detail,
                               headers={'Retry-After': retry_after} if retry_after else {},
                               json=lambda: {'detail': detail})
    return requests.HTTPError(f'{status}', response=response)


class FakeApi:
    """Routes CrucibleClient._request calls; errors queue per (method, path)."""

    def __init__(self, acknowledged=(), existing=None):
        self.calls = []
        self.errors = {}
        self.acknowledged = list(acknowledged)
        self.existing = existing
        self._config = SimpleNamespace(connect_timeout=5, read_timeout=30, upload_protocol='auto')

    def fail(self, method, path, *errors):
        self.errors.setdefault((method, path), []).extend(errors)

    def _request(self, method, path, retry=True, log_body=True, **kwargs):
        self.calls.append((method, path, kwargs))
        queued = self.errors.get((method, path))
        if queued:
            raise queued.pop(0)
        if path.endswith('/initiate'):
            if self.existing:
                return {'state': 'completed', 'existing_file': self.existing}
            return {'upload_id': 'u1', 'state': 'uploading', 'part_size': 4, 'part_count': 3,
                    'parts': [], 'existing_file': None}
        if method == 'get':
            return {'parts': [{'part_number': n} for n in self.acknowledged],
                    'next_part_number_marker': None}
        if path.endswith('/parts'):
            return {'parts': [{'part_number': p['part_number'], 'url': f"https://storage/{p['part_number']}",
                               'headers': {'x-goog-hash': f"crc32c={p['crc32c']}", 'Content-Length': '4'},
                               'offset': (p['part_number'] - 1) * 4,
                               'size': min(4, len(DATA) - (p['part_number'] - 1) * 4)}
                              for p in kwargs['json']['parts']]}
        if path.endswith('/complete'):
            return RECORD
        if method == 'delete':
            return None
        raise AssertionError(f'unexpected call {method} {path}')

    def paths(self, method=None):
        return [path for m, path, _ in self.calls if method in (None, m)]


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(sm, 'PART_SIZE', 4)
    monkeypatch.setattr(sm.time, 'sleep', lambda seconds: None)
    path = tmp_path / 'data.bin'
    path.write_bytes(DATA)
    return str(path)


@pytest.fixture
def storage(monkeypatch):
    puts = []
    responses = []

    def put(url, data, headers, timeout, allow_redirects):
        body = b''.join(iter(lambda: data.read(3), b''))
        puts.append({'url': url, 'body': body, 'headers': headers})
        status = responses.pop(0) if responses else 200
        return SimpleNamespace(status_code=status)

    monkeypatch.setattr(sm.requests, 'put', put)
    return SimpleNamespace(puts=puts, responses=responses)


def test_upload_sends_every_part_and_completes(source, storage):
    api = FakeApi()
    seen = []

    record, existing = sm.upload_file_signed_multipart(
        api, DSID, source, progress=lambda name, done, total: seen.append((name, done, total)))

    assert (record, existing) == (RECORD, False)
    assert sorted(p['body'] for p in storage.puts) == [b'abcd', b'efgh', b'ij']
    assert all('Content-Length' not in p['headers'] for p in storage.puts)
    assert all(p['headers']['x-goog-hash'].startswith('crc32c=') for p in storage.puts)
    initiate = next(kw for m, path, kw in api.calls if path.endswith('/initiate'))
    assert initiate['headers']['Idempotency-Key']
    complete = next(kw for m, path, kw in api.calls if path.endswith('/complete'))
    assert complete['json'] == {'upload_id': 'u1', 'sha256_hash': __import__('hashlib').sha256(DATA).hexdigest(),
                                'crc32c': crc(DATA)}
    assert complete['timeout'][1] == 120
    assert seen[-1] == ('data.bin', len(DATA), len(DATA))


def test_existing_file_skips_the_upload(source, storage):
    api = FakeApi(existing=RECORD)

    assert sm.upload_file_signed_multipart(api, DSID, source) == (RECORD, True)
    assert storage.puts == []


def test_acknowledged_parts_are_not_sent_again(source, storage):
    api = FakeApi(acknowledged=[1])

    sm.upload_file_signed_multipart(api, DSID, source)

    signed = next(kw for m, path, kw in api.calls if path.endswith('/parts'))
    assert [p['part_number'] for p in signed['json']['parts']] == [2, 3]


def test_signing_waits_out_the_interval(source, storage):
    api = FakeApi()
    api.fail('post', f'{BASE}/u1/parts', http_error(429, retry_after='5'))

    sm.upload_file_signed_multipart(api, DSID, source)

    assert api.paths('post').count(f'{BASE}/u1/parts') == 2


def test_failed_part_is_retried(source, storage):
    storage.responses.extend([503])

    sm.upload_file_signed_multipart(FakeApi(), DSID, source)

    assert len(storage.puts) == 4


def test_rejected_part_aborts_the_upload(source, storage):
    storage.responses.extend([400, 400, 400])
    api = FakeApi()

    with pytest.raises(RuntimeError, match='rejected part'):
        sm.upload_file_signed_multipart(api, DSID, source)

    assert f'{BASE}/u1' in api.paths('delete')
    assert f'{BASE}/complete' not in api.paths('post')


@pytest.mark.parametrize('error', [http_error(404, 'Not Found'),
                                   http_error(503, 'New multipart uploads are disabled', '60')])
def test_auto_falls_back_to_the_legacy_route(source, monkeypatch, error):
    api = FakeApi()
    api.fail('post', f'{BASE}/initiate', error)
    legacy = MagicMock(return_value=(RECORD, False))
    monkeypatch.setattr(dispatch, 'upload_file_gcs_multipart', legacy)

    assert dispatch.upload_file_gcs(api, DSID, source) == (RECORD, False)
    assert dispatch.upload_file_gcs(api, DSID, source) == (RECORD, False)

    assert legacy.call_count == 2
    assert api.paths('post').count(f'{BASE}/initiate') == 1


def test_signed_protocol_does_not_fall_back(source, monkeypatch):
    api = FakeApi()
    api.fail('post', f'{BASE}/initiate', http_error(404, 'Not Found'))
    monkeypatch.setattr(dispatch, 'upload_file_gcs_multipart',
                        lambda *a, **k: pytest.fail('fell back'))

    with pytest.raises(sm.SignedMultipartUnavailable):
        dispatch.upload_file_gcs(api, DSID, source, protocol='signed')


def test_dataset_not_found_is_not_a_fallback(source, monkeypatch):
    api = FakeApi()
    api.fail('post', f'{BASE}/initiate', http_error(404, 'Dataset not found'))
    monkeypatch.setattr(dispatch, 'upload_file_gcs_multipart',
                        lambda *a, **k: pytest.fail('fell back'))

    with pytest.raises(requests.HTTPError):
        dispatch.upload_file_gcs(api, DSID, source)


def test_legacy_protocol_skips_signed_uploads(source, monkeypatch):
    api = FakeApi()
    legacy = MagicMock(return_value=(RECORD, False))
    monkeypatch.setattr(dispatch, 'upload_file_gcs_multipart', legacy)

    dispatch.upload_file_gcs(api, DSID, source, protocol='legacy')

    assert api.calls == [] and legacy.called


def test_empty_files_use_the_legacy_route(tmp_path, monkeypatch):
    path = tmp_path / 'empty.bin'
    path.write_bytes(b'')
    api = FakeApi()
    legacy = MagicMock(return_value=(RECORD, False))
    monkeypatch.setattr(dispatch, 'upload_file_gcs_multipart', legacy)

    dispatch.upload_file_gcs(api, DSID, str(path))

    assert legacy.called and not getattr(api, '_signed_uploads_unavailable', False)


def test_client_upload_progress_is_used_by_default(source, storage):
    api = FakeApi()
    seen = []
    api.upload_progress = lambda name, done, total: seen.append(done)

    dispatch.upload_file_gcs(api, DSID, source)

    assert seen[-1] == len(DATA)


def test_progress_line_renders_only_on_a_terminal():
    import io
    from crucible.cli.helpers import UploadProgress

    quiet = io.StringIO()
    UploadProgress(stream=quiet)('data.bin', 5, 10)
    assert quiet.getvalue() == ''

    tty = io.StringIO()
    tty.isatty = lambda: True
    progress = UploadProgress(stream=tty, interval=0)
    progress('data.bin', 512, 1024)
    progress('data.bin', 1024, 1024)
    out = tty.getvalue()
    assert 'data.bin' in out and ' 50%' in out and '100%' in out
    assert out.endswith('\n') and out.count('\n') == 1
