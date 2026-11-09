"""Everything removed in 4.0.0 raises RemovedError naming its replacement."""

import inspect
from unittest.mock import MagicMock

import pytest

import crucible
from crucible import RemovedError
from crucible.client import CrucibleClient
from crucible.resources.base import BaseResource


def _owners():
    import crucible.resources as resources
    classes = {CrucibleClient}
    for _, obj in inspect.getmembers(resources, inspect.isclass):
        if issubclass(obj, BaseResource):
            classes.add(obj)
    return sorted(classes, key=lambda cls: cls.__name__)


def _removed_methods():
    seen = set()
    for cls in _owners():
        for klass in cls.__mro__:
            for name, member in vars(klass).items():
                if getattr(member, '__removed__', None) and (klass, name) not in seen:
                    seen.add((klass, name))
                    yield pytest.param(cls, name, id=f'{cls.__name__}.{name}')


def _removed_parameters():
    seen = set()
    for cls in _owners():
        for klass in cls.__mro__:
            for name, member in vars(klass).items():
                for old, new in getattr(member, '__removed_parameters__', ()):
                    key = (cls, name, old)
                    if key not in seen:
                        seen.add(key)
                        yield pytest.param(cls, name, old, new, id=f'{cls.__name__}.{name}-{old}')


def _instance(cls):
    if cls is CrucibleClient:
        return CrucibleClient('https://crucible.example.test/api/v3', 'key')
    return cls(MagicMock())


@pytest.mark.parametrize('cls, name', list(_removed_methods()))
def test_removed_methods_raise_with_the_replacement(cls, name):
    with pytest.raises(RemovedError, match=r'removed in nano-crucible 4\.0\.0; use '):
        getattr(_instance(cls), name)('x', 'y')


@pytest.mark.parametrize('cls, name, old, new', list(_removed_parameters()))
def test_removed_keywords_raise_with_the_new_name(cls, name, old, new):
    with pytest.raises(RemovedError, match=f"'{old}' keyword .*use '{new}'"):
        getattr(_instance(cls), name)(**{old: 'x'})


def test_removed_error_is_exported_and_a_type_error():
    assert issubclass(crucible.RemovedError, TypeError)


def test_there_is_something_to_check():
    assert len(list(_removed_methods())) >= 30
    assert len(list(_removed_parameters())) >= 60


def _datasets():
    from crucible.resources.datasets import DatasetOperations
    operations = DatasetOperations(MagicMock())
    operations._request = MagicMock(return_value={'unique_id': 'D' * 26})
    operations._paginate = MagicMock(return_value=[])
    return operations


@pytest.mark.parametrize('call, message', [
    (lambda ops: ops.list(instrument_name='Titan'), 'instrument_name'),
    (lambda ops: ops.list(offset=10), "'offset'"),
    (lambda ops: ops.list(unique_id='D' * 26), "'unique_id' list filter"),
    (lambda ops: ops.update('D' * 26, public=True), "'public' field"),
    (lambda ops: ops.download('D' * 26, file_name='x'), "'file_name'"),
    (lambda ops: ops.add_file('D' * 26, 'x', multipart=False), "'multipart'"),
    (lambda ops: ops.add_file('D' * 26, 'x', upload_protocol='legacy'), "'upload_protocol'"),
])
def test_removed_dataset_arguments_raise(call, message):
    with pytest.raises(RemovedError, match=message):
        call(_datasets())


@pytest.mark.parametrize('dataset, message', [
    ({'files_to_upload': ['a.dat']}, "'files_to_upload'"),
])
def test_removed_create_keywords_raise(dataset, message):
    from crucible.models import Dataset
    with pytest.raises(RemovedError, match=message):
        _datasets().create(Dataset(dataset_name='t'), **dataset)


@pytest.mark.parametrize('fields, message', [
    ({'owner_orcid': '0000-0001-6402-3752'}, 'owner_orcid'),
    ({'instrument_name': 'Titan'}, 'instrument_name'),
])
def test_removed_dataset_fields_raise_on_create(fields, message):
    from crucible.models import Dataset
    operations = _datasets()

    with pytest.raises(RemovedError, match=message):
        operations.create(Dataset(dataset_name='t', **fields))
    operations._request.assert_not_called()


def test_instrument_name_alongside_an_instrument_id_is_still_fine():
    from crucible.models import Dataset
    _datasets().create(Dataset(dataset_name='t', instrument_name='Titan', instrument_id='titan'))


def test_join_request_group_name_raises():
    from crucible.resources.access_groups import AccessGroupOperations
    with pytest.raises(RemovedError, match="'project_mfid'"):
        AccessGroupOperations(MagicMock()).list_join_requests(group_name='thin-films')


def _ops(module, name):
    import importlib
    cls = getattr(importlib.import_module(f'crucible.resources.{module}'), name)
    operations = cls(MagicMock())
    operations._request = MagicMock(return_value={'unique_id': 'S' * 26})
    operations._paginate = MagicMock(return_value=[])
    return operations


@pytest.mark.parametrize('keyword', ['owner_orcid', 'project_id', 'public', 'date_created',
                                     'creation_date', 'owner_id', 'owner_user_id'])
def test_removed_sample_update_arguments_raise(keyword):
    operations = _ops('samples', 'SampleOperations')

    with pytest.raises(RemovedError, match=f"'{keyword}'"):
        operations.update('S' * 26, **{keyword: 'x'})
    operations._request.assert_not_called()


def test_sample_update_rejects_unknown_keywords_plainly():
    with pytest.raises(TypeError, match="unexpected keyword argument 'colour'") as caught:
        _ops('samples', 'SampleOperations').update('S' * 26, colour='blue')
    assert not isinstance(caught.value, RemovedError)


def test_sample_update_keeps_its_first_positional_arguments():
    operations = _ops('samples', 'SampleOperations')

    operations.update('S' * 26, 'name', 'description', '2026-01-01')

    assert operations._request.call_args.kwargs['json'] == {
        'sample_name': 'name', 'description': 'description', 'timestamp': '2026-01-01'}


@pytest.mark.parametrize('call, message', [
    (lambda ops: ops.list(offset=5), "'offset'"),
    (lambda ops: ops.create(sample_name='x'), 'keyword arguments to samples.create'),
])
def test_removed_sample_calls_raise(call, message):
    with pytest.raises(RemovedError, match=message):
        call(_ops('samples', 'SampleOperations'))


def test_sample_owner_orcid_on_create_raises():
    from crucible.models import Sample
    with pytest.raises(RemovedError, match='owner_orcid'):
        _ops('samples', 'SampleOperations').create(Sample(sample_name='x', owner_orcid='0000-0001-6402-3752'))


@pytest.mark.parametrize('call, message', [
    (lambda ops: ops.get(instrument_name='Titan'), 'instrument_name'),
    (lambda ops: ops.get(instrument_id='0tkvpezyz1zzf00076nahf85j4'), 'instrument_mfid'),
])
def test_removed_instrument_lookups_raise(call, message):
    with pytest.raises(RemovedError, match=message):
        call(_ops('instruments', 'InstrumentOperations'))


def test_instrument_owner_orcid_on_create_raises():
    from crucible.models import Instrument
    instrument = Instrument(instrument_name='Titan', instrument_id='titan', owner_orcid='0000-0001-6402-3752')
    with pytest.raises(RemovedError, match='owner_orcid'):
        _ops('instruments', 'InstrumentOperations').create(instrument)


@pytest.mark.parametrize('name', ['graph_explorer_url', 'current_session', 'upload_protocol',
                                  'upload_chunk_size_mb'])
def test_removed_settings_raise_and_old_files_still_load(name, tmp_path, monkeypatch):
    from crucible.config.config import Config
    config_file = tmp_path / 'config.ini'
    config_file.write_text("[crucible]\napi_key = k\ngraph_explorer_url = https://x/explore\n"
                           "[upload]\nprotocol = legacy\n")
    monkeypatch.setattr(Config, 'config_file_path', property(lambda self: config_file))
    config = Config()

    with pytest.raises(RemovedError, match=f"'{name}' setting"):
        getattr(config, name)
    leftovers = {name for _, name, _ in config.removed_in_use()}
    assert {'graph_explorer_url', 'upload_protocol'} <= leftovers


def test_get_graph_explorer_url_is_removed():
    from crucible.config import get_graph_explorer_url
    with pytest.raises(RemovedError, match='get_hub_url'):
        get_graph_explorer_url()


def test_create_config_file_refuses_removed_settings():
    from crucible.config import create_config_file
    with pytest.raises(RemovedError, match='hub_url'):
        create_config_file('key', graph_explorer_url='https://x/explore')
