"""Unit coverage for --json on relationship listings, file, ingestion, join-request,
deletion, whoami, and status commands."""

import argparse
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crucible.cli import access_group as ag_cli
from crucible.cli import dataset as dataset_cli
from crucible.cli import deletion as deletion_cli
from crucible.cli import file as file_cli
from crucible.cli import ingestion as ingestion_cli
from crucible.cli import instrument as instrument_cli
from crucible.cli import project as project_cli
from crucible.cli import sample as sample_cli
from crucible.cli import status as status_cli
from crucible.cli import user as user_cli
from crucible.cli import whoami as whoami_cli
from crucible.config import config
from crucible.models import (AccessGrant, AccountAuthorization, AccountCapabilities,
                             ProjectMember)


MFID = '0tkn2knjast3h0008nyq9zps2c'
OTHER_MFID = '0tkn2knjast3h0008nyq9zps2d'
ORCID = '0000-0001-6402-3752'


def parse(register, *argv):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')
    register(subparsers)
    args = parser.parse_args(list(argv))
    args.debug = False
    return args


def use_client(monkeypatch, **resources):
    client = SimpleNamespace(**resources)
    monkeypatch.setattr('crucible.config.get_client', lambda: client)
    return client


def json_output(capsys):
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(('register', 'argv'), [
    (dataset_cli._register_list_parents, ('list-parents', MFID, '--json')),
    (dataset_cli._register_list_children, ('list-children', MFID, '--json')),
    (dataset_cli._register_list_samples, ('list-samples', MFID, '--json')),
    (dataset_cli._register_list_files, ('list-files', MFID, '--json')),
    (dataset_cli._register_list_keywords, ('list-keywords', MFID, '--json')),
    (sample_cli._register_list_parents, ('list-parents', MFID, '--json')),
    (sample_cli._register_list_children, ('list-children', MFID, '--json')),
    (sample_cli._register_list_datasets, ('list-datasets', MFID, '--json')),
    (project_cli._register_list_users, ('list-users', 'my-project', '--json')),
    (instrument_cli._register_member_commands, ('list-users', 'titan', '--json')),
    (user_cli._register_list_projects, ('list-projects', 'fabrice', '--json')),
    (user_cli._register_list_datasets, ('list-datasets', 'fabrice', '--json')),
    (user_cli._register_list_access_groups, ('list-access-groups', 'fabrice', '--json')),
    (file_cli._register_list, ('list', '--json')),
    (file_cli._register_get, ('get', MFID, '--json')),
    (ingestion_cli._register_list, ('list', '--json')),
    (ingestion_cli._register_get, ('get', '42', '--json')),
    (ag_cli._register_list, ('list', '--json')),
    (ag_cli._register_get, ('get', '42', '--json')),
    (deletion_cli._register_list, ('list', '--json')),
    (deletion_cli._register_get, ('get', '42', '--json')),
])
def test_parsers_expose_json(register, argv):
    assert parse(register, *argv).json is True
    assert parse(register, *[a for a in argv if a != '--json']).json is False


def test_top_level_parsers_expose_json():
    for module in (whoami_cli, status_cli):
        parser = argparse.ArgumentParser()
        module.register_subcommand(parser.add_subparsers(dest='command'))
        name = 'whoami' if module is whoami_cli else 'status'
        assert parser.parse_args([name, '--json']).json is True


# ── dataset ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('as_json', [False, True])
def test_dataset_list_parents(monkeypatch, capsys, as_json):
    parents = [{'unique_id': OTHER_MFID, 'dataset_name': 'parent', 'measurement': 'XRD'}]
    datasets = SimpleNamespace(list_parents=MagicMock(return_value=parents))
    use_client(monkeypatch, datasets=datasets)
    argv = ['list-parents', MFID] + (['--json'] if as_json else [])

    dataset_cli._execute_list_parents(parse(dataset_cli._register_list_parents, *argv))

    if as_json:
        assert json_output(capsys) == parents
    else:
        out = capsys.readouterr().out
        assert 'Parent Datasets' in out and 'parent' in out and OTHER_MFID in out


def test_dataset_list_files_json_includes_download_links(monkeypatch, capsys):
    files = [{'mfid': OTHER_MFID, 'filename': 'a.csv', 'size': 3}]
    datasets = SimpleNamespace(
        list_files=MagicMock(return_value=files),
        get_download_links=MagicMock(return_value={OTHER_MFID: 'https://signed'}),
    )
    use_client(monkeypatch, datasets=datasets)

    dataset_cli._execute_list_files(parse(dataset_cli._register_list_files,
                                          'list-files', MFID, '--json'))

    assert json_output(capsys) == [{**files[0], 'download_url': 'https://signed'}]


@pytest.mark.parametrize('as_json', [False, True])
def test_dataset_list_keywords(monkeypatch, capsys, as_json):
    keywords = [{'keyword': 'perovskite', 'num_datasets': 4}]
    use_client(monkeypatch, datasets=SimpleNamespace(
        list_keywords=MagicMock(return_value=keywords)))
    argv = ['list-keywords', MFID] + (['--json'] if as_json else [])

    dataset_cli._execute_list_keywords(parse(dataset_cli._register_list_keywords, *argv))

    if as_json:
        assert json_output(capsys) == keywords
    else:
        assert 'perovskite' in capsys.readouterr().out


# ── sample ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('as_json', [False, True])
def test_sample_list_datasets(monkeypatch, capsys, as_json):
    datasets = [{'unique_id': OTHER_MFID, 'dataset_name': 'scan', 'measurement': 'XRD'}]
    use_client(monkeypatch, datasets=SimpleNamespace(list=MagicMock(return_value=datasets)))
    argv = ['list-datasets', MFID] + (['--json'] if as_json else [])

    sample_cli._execute_list_datasets(parse(sample_cli._register_list_datasets, *argv))

    if as_json:
        assert json_output(capsys) == datasets
    else:
        out = capsys.readouterr().out
        assert 'scan' in out and OTHER_MFID in out


def test_sample_list_children_json(monkeypatch, capsys):
    children = [{'unique_id': OTHER_MFID, 'sample_name': 'child'}]
    use_client(monkeypatch, samples=SimpleNamespace(
        list_children=MagicMock(return_value=children)))

    sample_cli._execute_list_children(parse(sample_cli._register_list_children,
                                            'list-children', MFID, '--json'))

    assert json_output(capsys) == children


# ── project / instrument members ─────────────────────────────────────────────

@pytest.mark.parametrize('as_json', [False, True])
def test_project_list_users(monkeypatch, capsys, as_json):
    member = ProjectMember(unique_id=ORCID, username='jdoe', first_name='Jane',
                           last_name='Doe', role='editor')
    use_client(monkeypatch, projects=SimpleNamespace(list_users=MagicMock(return_value=[member])))
    argv = ['list-users', 'my-project'] + (['--json'] if as_json else [])

    project_cli._execute_list_users(parse(project_cli._register_list_users, *argv))

    if as_json:
        data = json_output(capsys)
        assert data[0]['username'] == 'jdoe'
        assert data[0]['role'] == 'editor'
        assert data[0]['unique_id'] == ORCID
    else:
        out = capsys.readouterr().out
        assert 'jdoe' in out and 'Users' in out


@pytest.mark.parametrize('as_json', [False, True])
def test_instrument_list_users(monkeypatch, capsys, as_json):
    grant = AccessGrant(principal_id=ORCID, principal_type='user', permission='admin',
                        slug='jdoe', display_name='Jane Doe')
    use_client(monkeypatch, instruments=SimpleNamespace(
        list_users=MagicMock(return_value=[grant])))
    argv = ['list-users', 'titan'] + (['--json'] if as_json else [])

    instrument_cli._execute_list_users(parse(instrument_cli._register_member_commands, *argv))

    if as_json:
        assert json_output(capsys) == [grant.model_dump(mode='json')]
    else:
        out = capsys.readouterr().out
        assert 'Members' in out and 'Jane Doe' in out


# ── user ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('as_json', [False, True])
def test_user_list_projects(monkeypatch, capsys, as_json):
    projects = [{'project_id': 'my-project', 'title': 'Mine', 'organization': 'LBL',
                 'role': 'owner'}]
    use_client(monkeypatch, users=SimpleNamespace(list_projects=MagicMock(return_value=projects)))
    argv = ['list-projects', ORCID] + (['--json'] if as_json else [])

    user_cli._execute_list_projects(parse(user_cli._register_list_projects, *argv))

    if as_json:
        assert json_output(capsys) == projects
    else:
        out = capsys.readouterr().out
        assert 'my-project' in out and 'LBL' in out


def test_user_list_access_groups_and_datasets_json(monkeypatch, capsys):
    datasets = [{'unique_id': OTHER_MFID}]
    use_client(
        monkeypatch,
        users=SimpleNamespace(list_access_groups=MagicMock(return_value=['group-a'])),
        datasets=SimpleNamespace(list=MagicMock(return_value=datasets)),
    )

    user_cli._execute_list_access_groups(parse(user_cli._register_list_access_groups,
                                               'list-access-groups', ORCID, '--json'))
    assert json_output(capsys) == ['group-a']

    user_cli._execute_list_datasets(parse(user_cli._register_list_datasets,
                                          'list-datasets', ORCID, '--json'))
    assert json_output(capsys) == datasets


# ── file ─────────────────────────────────────────────────────────────────────

FILE_RECORD = {'mfid': OTHER_MFID, 'dataset_mfid': MFID, 'filename': 'a.csv',
               'size': 12, 'storage_backend': 'local', 'storage_path': '/data/a.csv'}


@pytest.mark.parametrize('as_json', [False, True])
def test_file_list(monkeypatch, capsys, as_json):
    use_client(monkeypatch, files=SimpleNamespace(list=MagicMock(return_value=[FILE_RECORD])))
    argv = ['list'] + (['--json'] if as_json else [])

    file_cli._execute_list(parse(file_cli._register_list, *argv))

    if as_json:
        assert json_output(capsys) == [FILE_RECORD]
    else:
        out = capsys.readouterr().out
        assert 'Files' in out and OTHER_MFID in out


@pytest.mark.parametrize('as_json', [False, True])
def test_file_get(monkeypatch, capsys, as_json):
    files = SimpleNamespace(get=MagicMock(return_value=FILE_RECORD),
                            get_download_link=MagicMock())
    use_client(monkeypatch, files=files)
    argv = ['get', OTHER_MFID] + (['--json'] if as_json else [])

    file_cli._execute_get(parse(file_cli._register_get, *argv))

    if as_json:
        assert json_output(capsys) == FILE_RECORD
    else:
        out = capsys.readouterr().out
        assert 'Cataloged (local)' in out and '/data/a.csv' in out
    files.get_download_link.assert_not_called()


# ── ingestion ────────────────────────────────────────────────────────────────

INGESTION = {'id': 42, 'status': 'complete', 'ingestion_class': 'LammpsIngestor',
             'file_mfid': OTHER_MFID, 'dataset_mfid': MFID}


@pytest.mark.parametrize('as_json', [False, True])
def test_ingestion_list(monkeypatch, capsys, as_json):
    use_client(monkeypatch, ingestions=SimpleNamespace(list=MagicMock(return_value=[INGESTION])))
    argv = ['list'] + (['--json'] if as_json else [])

    ingestion_cli._execute_list(parse(ingestion_cli._register_list, *argv))

    if as_json:
        assert json_output(capsys) == [INGESTION]
    else:
        out = capsys.readouterr().out
        assert 'Ingestion Requests' in out and 'LammpsIngestor' in out


@pytest.mark.parametrize('as_json', [False, True])
def test_ingestion_get(monkeypatch, capsys, as_json):
    use_client(monkeypatch, ingestions=SimpleNamespace(get=MagicMock(return_value=INGESTION)))
    argv = ['get', '42'] + (['--json'] if as_json else [])

    ingestion_cli._execute_get(parse(ingestion_cli._register_get, *argv))

    if as_json:
        assert json_output(capsys) == INGESTION
    else:
        assert 'Ingestion Request #42' in capsys.readouterr().out


# ── access group (join requests) ─────────────────────────────────────────────

JOIN_REQUEST = {'id': 7, 'status': 'pending', 'project': {'project_id': 'my-project'},
                'requester': {'username': 'jdoe'}, 'requester_id': ORCID,
                'request_time': '2026-11-01T12:00:00'}


@pytest.mark.parametrize('as_json', [False, True])
def test_ag_list(monkeypatch, capsys, as_json):
    use_client(monkeypatch, access_groups=SimpleNamespace(
        list_join_requests=MagicMock(return_value=[JOIN_REQUEST])))
    argv = ['list'] + (['--json'] if as_json else [])

    ag_cli._execute_list(parse(ag_cli._register_list, *argv))

    if as_json:
        assert json_output(capsys) == [JOIN_REQUEST]
    else:
        out = capsys.readouterr().out
        assert 'Join Requests' in out and 'my-project' in out


@pytest.mark.parametrize('as_json', [False, True])
def test_ag_get(monkeypatch, capsys, as_json):
    use_client(monkeypatch, access_groups=SimpleNamespace(
        get=MagicMock(return_value=JOIN_REQUEST)))
    argv = ['get', '7'] + (['--json'] if as_json else [])

    ag_cli._execute_get(parse(ag_cli._register_get, *argv))

    if as_json:
        assert json_output(capsys) == JOIN_REQUEST
    else:
        out = capsys.readouterr().out
        assert 'Join Request' in out and 'jdoe' in out


# ── deletion ─────────────────────────────────────────────────────────────────

DELETION = {'id': 3, 'resource_id': MFID, 'resource_type': 'dataset',
            'resource_name': 'old scan', 'status': 'pending', 'requester_id': ORCID}


@pytest.mark.parametrize('as_json', [False, True])
def test_deletion_list(monkeypatch, capsys, as_json):
    use_client(monkeypatch, deletions=SimpleNamespace(list=MagicMock(return_value=[DELETION])),
               users=SimpleNamespace(resolve=MagicMock(return_value={})), can_elevate=False)
    argv = ['list'] + (['--json'] if as_json else [])

    deletion_cli._execute_list(parse(deletion_cli._register_list, *argv))

    if as_json:
        assert json_output(capsys) == [DELETION]
    else:
        out = capsys.readouterr().out
        assert 'Deletion Requests' in out and 'old scan' in out


@pytest.mark.parametrize('as_json', [False, True])
def test_deletion_get(monkeypatch, capsys, as_json):
    use_client(monkeypatch, deletions=SimpleNamespace(get=MagicMock(return_value=DELETION)),
               users=SimpleNamespace(resolve=MagicMock(return_value={})))
    argv = ['get', '3'] + (['--json'] if as_json else [])

    deletion_cli._execute_get(parse(deletion_cli._register_get, *argv))

    if as_json:
        assert json_output(capsys) == DELETION
    else:
        out = capsys.readouterr().out
        assert 'Deletion Request' in out and 'old scan' in out


# ── whoami / status ──────────────────────────────────────────────────────────

def _whoami_client():
    client = MagicMock(
        privilege_mode=None,
        is_elevated=True,
        credential_source='config file',
        authorization=AccountAuthorization(platform_role='admin', can_elevate=True),
        capabilities=AccountCapabilities(can_create_project=True),
    )
    client.whoami.return_value = {
        'user_unique_id': ORCID,
        'access_group_ids': ['group-a'],
        'user_info': {'unique_id': ORCID, 'username': 'jdoe',
                      'first_name': 'Jane', 'last_name': 'Doe'},
    }
    return client


@pytest.mark.parametrize('as_json', [False, True])
def test_whoami(monkeypatch, capsys, as_json):
    monkeypatch.setattr(config, '_client', _whoami_client())

    whoami_cli.execute(SimpleNamespace(verbose=False, debug=False, json=as_json))

    if as_json:
        data = json_output(capsys)
        assert data['user_info']['username'] == 'jdoe'
        assert data['access_group_ids'] == ['group-a']
        assert data['signed_in_with'] == 'API key (config file)'
        assert data['authorization'] == {
            'platform_role': 'admin', 'privilege_mode': 'elevated',
            'privilege_mode_is_default': True, 'can_elevate': True}
        assert data['capabilities']['can_create_project'] is True
    else:
        out = capsys.readouterr().out
        assert 'jdoe' in out and 'admin' in out and 'API key (config file)' in out


class _Response:
    status_code = 200

    def json(self):
        return {
            'status': 'ok',
            'build': {'api_version': '3.0.0', 'git_commit': 'a' * 40, 'branch': 'staging'},
            'database': {'status': 'ok', 'latency_ms': 6.1, 'schema_revisions': ['rev']},
        }


def test_status_json(monkeypatch, capsys):
    monkeypatch.setattr(config, '_data', {
        'api_url': 'https://crucible.lbl.gov/testapi-staging',
        'api_key': 'test-key',
    })
    monkeypatch.setattr('requests.get', lambda url, timeout: _Response())
    use_client(monkeypatch, whoami=lambda: {'user_info': {
        'unique_id': ORCID, 'username': 'jdoe', 'first_name': 'Jane', 'last_name': 'Doe'}})

    with pytest.raises(SystemExit) as exited:
        status_cli.execute(SimpleNamespace(json=True))

    assert exited.value.code == 0
    data = json_output(capsys)
    assert data['endpoint']['url'] == 'https://crucible.lbl.gov/testapi-staging'
    assert data['reachability']['reachable'] is True
    assert data['readiness'] == {'status': 'ready', 'ok': True, 'http_status': 200}
    assert data['deployment']['api_version'] == '3.0.0'
    assert data['deployment']['git_commit'] == 'a' * 40
    assert data['database'] == {'status': 'available', 'ok': True,
                                'latency_ms': 6.1, 'schema_revisions': ['rev']}
    assert data['authentication']['status'] == 'authenticated'
    assert data['authentication']['user']['username'] == 'jdoe'


def test_status_json_without_credential(monkeypatch, capsys):
    monkeypatch.setattr(config, '_data', {'api_url': 'https://crucible.lbl.gov/testapi-staging'})
    monkeypatch.setattr('requests.get', lambda url, timeout: _Response())

    with pytest.raises(SystemExit) as exited:
        status_cli.execute(SimpleNamespace(json=True))

    assert exited.value.code == 0
    assert json_output(capsys)['authentication'] == {'status': 'not configured'}


JOIN = [{'id': 3, 'status': 'pending', 'project': {'project_id': 'demo'}}]
AUDIT = {'id': 42, 'resource_id': MFID, 'resource_type': 'dataset', 'deleted_at': '2026-11-01T10:00:00Z'}
REQUESTS = [{'id': 7, 'status': 'complete', 'ingestion_class': 'XRDIngestor', 'file_mfid': MFID}]


@pytest.mark.parametrize(('register', 'argv', 'resources', 'expected'), [
    (ag_cli._register_mine, ('mine', '--json'),
     {'account': SimpleNamespace(join_requests=MagicMock(return_value=JOIN))}, JOIN),
    (deletion_cli._register_list_deleted, ('list-deleted', '--resource', MFID, '--json'),
     {'deletions': SimpleNamespace(list_deleted=MagicMock(return_value=[AUDIT]))}, [AUDIT]),
    (deletion_cli._register_get_deleted, ('get-deleted', '42', '--json'),
     {'deletions': SimpleNamespace(get_deleted=MagicMock(return_value=AUDIT))}, AUDIT),
    (file_cli._register_ingestion, ('ingestion', MFID, '--json'),
     {'ingestions': SimpleNamespace(list=MagicMock(return_value=REQUESTS))}, REQUESTS),
    (ingestion_cli._register_list_ingestors, ('list-ingestors', '--filter', 'xrd', '--json'),
     {'ingestions': SimpleNamespace(list_ingestors=MagicMock(return_value=['XRDIngestor', 'TEMIngestor']))},
     ['XRDIngestor']),
])
def test_remaining_commands_print_json(monkeypatch, capsys, register, argv, resources, expected):
    use_client(monkeypatch, **resources)
    args = parse(register, *argv)

    args.func(args)

    assert json_output(capsys) == expected


def test_list_deleted_uses_the_current_resource_keyword(monkeypatch, capsys):
    deletions = SimpleNamespace(list_deleted=MagicMock(return_value=[]))
    use_client(monkeypatch, deletions=deletions)
    args = parse(deletion_cli._register_list_deleted, 'list-deleted', '--resource', MFID, '--json')

    args.func(args)

    assert deletions.list_deleted.call_args.kwargs['resource_mfid'] == MFID
