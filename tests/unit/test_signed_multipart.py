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
        if path.startswith('/files/') and path.endswith('/initiate'):
            return {'upload_id': 'u1', 'state': 'uploading', 'part_size': 4, 'part_count': 3,
                    'parts': [], 'existing_file': None}
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


@pytest.mark.parametrize('error', [http_error(503, 'New multipart uploads are disabled', '60')])
def test_auto_falls_back_to_the_legacy_route(source, monkeypatch, error):
    api = FakeApi()
    api.fail('post', f'{BASE}/initiate', error)
    legacy = MagicMock(return_value=(RECORD, False))
    monkeypatch.setattr(dispatch, 'upload_file_gcs_multipart', legacy)

    assert dispatch.upload_file_gcs(api, DSID, source) == (RECORD, False)
    assert dispatch.upload_file_gcs(api, DSID, source) == (RECORD, False)

    assert legacy.call_count == 2
    assert api.paths('post').count(f'{BASE}/initiate') == 1


def test_missing_route_is_an_error_not_a_fallback(source, monkeypatch):
    api = FakeApi()
    api.fail('post', f'{BASE}/initiate', http_error(404, 'Not Found'))
    monkeypatch.setattr(dispatch, 'upload_file_gcs_multipart',
                        lambda *a, **k: pytest.fail('fell back'))

    with pytest.raises(requests.HTTPError):
        dispatch.upload_file_gcs(api, DSID, source)


def test_signed_protocol_does_not_fall_back(source, monkeypatch):
    api = FakeApi()
    api.fail('post', f'{BASE}/initiate', http_error(503, 'New multipart uploads are disabled', '60'))
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


def test_client_upload_protocol_overrides_the_setting(source, monkeypatch):
    api = FakeApi()
    api.upload_protocol = 'legacy'
    legacy = MagicMock(return_value=(RECORD, False))
    monkeypatch.setattr(dispatch, 'upload_file_gcs_multipart', legacy)

    dispatch.upload_file_gcs(api, DSID, source)

    assert legacy.called and api.calls == []


def test_client_request_ingestion_false_skips_ingestion(monkeypatch):
    from crucible.resources.datasets import DatasetOperations
    seen = []
    monkeypatch.setattr('crucible.resources.datasets.upload_file_gcs',
                        lambda client, dsid, path, **kw: (seen.append(kw)
                                                          or ({'mfid': 'f1', 'filename': 'x'}, False)))
    client = MagicMock(request_ingestion=False)
    client.files._parse = lambda record: record
    client.files._skip_ingestion = MagicMock(return_value=None)

    DatasetOperations(client).add_file(DSID, "x")

    assert len(seen) == 1
    client.files._skip_ingestion.assert_called_once()
    assert not client.files.request_ingestion.called


def test_upload_session_applies_and_restores_options():
    from crucible.cli.helpers import upload_session

    client = SimpleNamespace()
    args = SimpleNamespace(upload_protocol='signed', no_ingest=True)
    with upload_session(client, args):
        assert (client.upload_protocol, client.request_ingestion) == ('signed', False)
        assert client.upload_progress is not None

    assert (client.upload_protocol, client.request_ingestion, client.upload_progress) == (
        None, True, None)


def test_add_file_cli_rejects_no_ingest_with_wait(tmp_path, monkeypatch, capsys):
    import argparse
    from crucible.cli import dataset as dataset_cli

    path = tmp_path / 'a.bin'
    path.write_bytes(b'x')
    parser = argparse.ArgumentParser()
    dataset_cli.register_subcommand(parser.add_subparsers(dest='command'))
    args = parser.parse_args(['dataset', 'add-file', DSID, '-i', str(path), '--no-ingest', '--wait'])
    monkeypatch.setattr('crucible.config.get_client', lambda: MagicMock())

    with pytest.raises(SystemExit):
        args.func(args)


def _structured_conflict(api, sha, etag='"e1"'):
    api.fail('post', f'{BASE}/initiate', http_error(409, None))
    api.errors[('post', f'{BASE}/initiate')][0].response.json = lambda: {'detail': {
        'code': 'filename_exists', 'message': 'Filename already exists',
        'file_mfid': 'old', 'etag': etag}}
    api.files = SimpleNamespace(get=MagicMock(return_value={
        'mfid': 'old', 'filename': 'data.bin', 'size': len(DATA), 'sha256_hash': sha,
        'etag': etag, 'dataset_mfid': DSID, 'storage_backend': 'gcs'}))
    api.datasets = SimpleNamespace(list_files=lambda dsid: pytest.fail('listed the dataset'))


def test_structured_conflict_with_same_content_reads_only_that_file(source, storage):
    import hashlib
    api = FakeApi()
    _structured_conflict(api, hashlib.sha256(DATA).hexdigest())

    record, existing = sm.upload_file_signed_multipart(api, DSID, source)

    assert existing is True and record['mfid'] == 'old'
    api.files.get.assert_called_once_with('old')


def test_conflict_carries_what_a_replace_needs(source, storage):
    api = FakeApi()
    _structured_conflict(api, 'f' * 64)

    with pytest.raises(sm.FileExistsWithDifferentContent) as caught:
        sm.upload_file_signed_multipart(api, DSID, source)

    assert (caught.value.file_mfid, caught.value.etag) == ('old', '"e1"')
    assert isinstance(caught.value, RuntimeError)


def test_replace_true_replaces_with_the_conflict_etag(source, storage):
    api = FakeApi()
    _structured_conflict(api, 'f' * 64)

    record, existing = sm.upload_file_signed_multipart(api, DSID, source, replace=True)

    assert (record, existing) == (RECORD, False)
    replace_call = next(kw for m, path, kw in api.calls if path == '/files/old/upload/multipart/initiate')
    assert replace_call['headers']['If-Match'] == '"e1"'
    assert replace_call['json'] == {'size': len(DATA), 'sha256_hash': __import__('hashlib').sha256(DATA).hexdigest()}
    assert sorted(p['body'] for p in storage.puts) == [b'abcd', b'efgh', b'ij']


@pytest.mark.parametrize('etag, expected', [(None, '*'), ('"e9"', '"e9"')])
def test_replace_by_file_mfid(source, storage, etag, expected):
    api = FakeApi()
    _structured_conflict(api, 'f' * 64)

    sm.replace_file_signed_multipart(api, 'old', source, etag=etag)

    replace_call = next(kw for m, path, kw in api.calls if path == '/files/old/upload/multipart/initiate')
    assert replace_call['headers']['If-Match'] == expected


def test_replace_refuses_a_changed_file(source, storage):
    api = FakeApi()
    _structured_conflict(api, 'f' * 64)
    error = http_error(412, None)
    error.response.json = lambda: {'detail': {'code': 'etag_mismatch', 'etag': '"new"'}}
    api.fail('post', '/files/old/upload/multipart/initiate', error)

    with pytest.raises(RuntimeError, match='changed since'):
        sm.replace_file_signed_multipart(api, 'old', source, etag='"e1"')
    assert storage.puts == []


def test_replace_needs_signed_uploads(source, monkeypatch):
    with pytest.raises(ValueError, match='legacy'):
        dispatch.upload_file_gcs(FakeApi(), DSID, source, protocol='legacy', replace=True)

    api = FakeApi()
    api.fail('post', f'{BASE}/initiate', http_error(503, 'New multipart uploads are disabled', '60'))
    monkeypatch.setattr(dispatch, 'upload_file_gcs_multipart', lambda *a, **k: pytest.fail('legacy'))
    with pytest.raises(RuntimeError, match='switched off'):
        dispatch.upload_file_gcs(api, DSID, source, replace=True)


@pytest.mark.parametrize('unchanged, skip, ingests', [
    (False, False, True), (False, True, False), (True, False, False)])
def test_files_replace_requests_ingestion_only_for_new_content(monkeypatch, unchanged, skip, ingests):
    from crucible.resources.files import FileOperations

    monkeypatch.setattr('crucible.resources.gcs.signed_multipart.replace_file_signed_multipart',
                        lambda *a, **k: ({'mfid': 'old', 'filename': 'data.bin'}, unchanged))
    client = MagicMock(request_ingestion=True, upload_progress=None)
    files = FileOperations(client)
    files.request_ingestion = MagicMock(return_value={'status': 'pending'})
    files._skip_ingestion = MagicMock(return_value=None)

    files.replace('old', 'x', skip_ingestion=skip)

    assert files.request_ingestion.called is ingests


def _add_file_args(tmp_path, extra=()):
    import argparse
    from crucible.cli import dataset as dataset_cli
    path = tmp_path / 'data.bin'
    path.write_bytes(DATA)
    parser = argparse.ArgumentParser()
    dataset_cli.register_subcommand(parser.add_subparsers(dest='command'))
    return parser.parse_args(['dataset', 'add-file', DSID, '-i', str(path), *extra])


def _conflicting_client():
    calls = []

    def add_file(dsid, path, replace=False, **kwargs):
        calls.append(replace)
        if not replace:
            raise sm.FileExistsWithDifferentContent('data.bin', 'old', '"e1"')
        return {'associated_file': RECORD}

    return SimpleNamespace(datasets=SimpleNamespace(add_file=add_file)), calls


@pytest.mark.parametrize('answer, expected', [(True, [False, True]), (False, [False])])
def test_add_file_asks_before_replacing(tmp_path, monkeypatch, answer, expected):
    client, calls = _conflicting_client()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers._interactive_stdin', lambda: True)
    monkeypatch.setattr('crucible.cli.helpers.prompt_confirm', lambda *a, **k: answer)
    args = _add_file_args(tmp_path)

    args.func(args)

    assert calls == expected


def test_add_file_without_a_terminal_does_not_replace(tmp_path, monkeypatch):
    client, calls = _conflicting_client()
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    monkeypatch.setattr('crucible.cli.helpers._interactive_stdin', lambda: False)
    args = _add_file_args(tmp_path)

    with pytest.raises(SystemExit):
        args.func(args)
    assert calls == [False]


def test_shell_completes_input_paths(tmp_path, monkeypatch):
    import argparse
    from prompt_toolkit.document import Document
    from crucible.cli import dataset as dataset_cli
    from crucible.cli.shell.completer import CrucibleCompleter

    (tmp_path / 'results.dat').write_text('x')
    (tmp_path / 'raw').mkdir()
    monkeypatch.chdir(tmp_path)
    parser = argparse.ArgumentParser()
    dataset_cli.register_subcommand(parser.add_subparsers(dest='resource'))
    completer = CrucibleCompleter(parser, client=MagicMock(), state={})

    options = [c.text for c in completer.get_completions(Document('dataset add-file X -i r'), None)]

    assert options == ['aw/', 'esults.dat ']


def test_auto_uses_signed_uploads_when_ingestion_is_requested(source, storage):
    from crucible.resources.datasets import DatasetOperations

    api = FakeApi()
    api.files = SimpleNamespace(_parse=lambda record: record,
                                request_ingestion=MagicMock(return_value={'status': 'requested'}))
    DatasetOperations(api).add_file(DSID, source)

    assert f'{BASE}/initiate' in api.paths('post')
    api.files.request_ingestion.assert_called_once()


def test_replace_with_identical_content_uploads_nothing(source, storage):
    import hashlib
    api = FakeApi()
    _structured_conflict(api, hashlib.sha256(DATA).hexdigest())

    record, unchanged = sm.replace_file_signed_multipart(api, 'old', source)

    assert unchanged is True and record['mfid'] == 'old'
    assert storage.puts == [] and api.calls == []
