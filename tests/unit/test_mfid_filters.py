"""Unit coverage for the repeatable mfid list filter and user search envelope."""

from unittest.mock import MagicMock

import pytest

from crucible.resources.datasets import DatasetOperations
from crucible.resources.instruments import InstrumentOperations
from crucible.resources.projects import ProjectOperations
from crucible.resources.samples import SampleOperations
from crucible.resources.users import UserOperations


MFIDS = ['0tkn2knjast3h0008nyq9zps2c', '0tf7evvtg5wb90005k1j97ak94']


def make(cls):
    operations = cls(MagicMock())
    operations._paginate = MagicMock(return_value=[])
    operations._request = MagicMock(return_value={'items': [], 'total': 0})
    return operations


def sent(operations):
    return operations._paginate.call_args.args[1]


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations,
                                 ProjectOperations, InstrumentOperations])
def test_list_sends_repeatable_mfid(cls):
    operations = make(cls)

    operations.list(mfid=MFIDS)
    assert sent(operations)['mfid'] == MFIDS

    operations.list(mfid=MFIDS[0])
    assert sent(operations)['mfid'] == [MFIDS[0]]






@pytest.mark.parametrize('values', [[], [f'v{i}' for i in range(101)]])
def test_mfid_filter_takes_1_to_100_values(values):
    operations = make(DatasetOperations)

    with pytest.raises(ValueError, match='mfid takes 1 to 100'):
        operations.list(mfid=values)


@pytest.mark.parametrize('cls', [DatasetOperations, SampleOperations])
def test_count_accepts_mfid(cls):
    operations = make(cls)

    operations.count(mfid=MFIDS)

    assert operations._request.call_args.kwargs['params']['mfid'] == MFIDS


def test_sample_children_listing_rejects_mfid():
    operations = make(SampleOperations)

    with pytest.raises(ValueError, match='top-level sample list'):
        operations.list(parent_mfid=MFIDS[0], mfid=MFIDS[1])


def test_project_mfid_filter_does_not_combine_with_orcid():
    operations = make(ProjectOperations)

    with pytest.raises(ValueError, match='mfid'):
        operations.list(orcid='0000-0002-1825-0097', mfid=MFIDS)


def test_user_search_reads_items():
    operations = UserOperations(MagicMock())
    operations._request = MagicMock(return_value={'limit': 20, 'items': [{'username': 'ron'}]})

    assert operations.search('ron') == [{'username': 'ron'}]
    operations._request.assert_called_once_with(
        'get', '/users/search', params={'q': 'ron', 'limit': 20})
