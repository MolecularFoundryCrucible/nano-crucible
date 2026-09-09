"""Unit coverage for dataset thumbnail request and response contracts."""

import base64
from unittest.mock import MagicMock

import pytest

from crucible.resources.datasets import DatasetOperations


MFID = '0tkn2knjast3h0008nyq9zps2c'
THUMBNAIL = {
    'id': 12,
    'dataset_id': 345,
    'thumbnail_name': 'preview.png',
    'thumbnail_b64str': '/9j/4AAQSk...',
    'mime_type': 'image/jpeg',
}


def make_operations(response):
    operations = DatasetOperations(MagicMock())
    operations._request = MagicMock(return_value=response)
    return operations


def test_get_thumbnails_preserves_complete_api_records():
    operations = make_operations([THUMBNAIL])

    result = operations.get_thumbnails(MFID)

    assert result == [THUMBNAIL]
    operations._request.assert_called_once_with(
        'get', f'/datasets/{MFID}/thumbnails')


def test_add_thumbnail_encodes_local_file_and_returns_api_record(tmp_path):
    image_path = tmp_path / 'preview.png'
    image_path.write_bytes(b'image bytes')
    operations = make_operations(THUMBNAIL)

    result = operations.add_thumbnail(MFID, image_path)

    assert result == THUMBNAIL
    operations._request.assert_called_once_with(
        'post',
        f'/datasets/{MFID}/thumbnails',
        json={
            'thumbnail_name': 'preview.png',
            'thumbnail_b64str': base64.b64encode(b'image bytes').decode('utf-8'),
        },
    )


def test_update_thumbnail_can_rename_without_replacing_image():
    updated = dict(THUMBNAIL, thumbnail_name='overview.png')
    operations = make_operations(updated)

    result = operations.update_thumbnail(
        MFID, 12, thumbnail_name='overview.png')

    assert result == updated
    operations._request.assert_called_once_with(
        'patch',
        f'/datasets/{MFID}/thumbnails/12',
        json={'thumbnail_name': 'overview.png'},
    )


def test_update_thumbnail_can_replace_image_without_renaming():
    encoded = base64.b64encode(b'replacement').decode('ascii')
    operations = make_operations(THUMBNAIL)

    result = operations.update_thumbnail(MFID, 12, image=encoded)

    assert result == THUMBNAIL
    operations._request.assert_called_once_with(
        'patch',
        f'/datasets/{MFID}/thumbnails/12',
        json={'thumbnail_b64str': encoded},
    )


@pytest.mark.parametrize('thumbnail_name', [None, '', '   '])
def test_update_thumbnail_rejects_empty_updates(thumbnail_name):
    operations = make_operations(THUMBNAIL)

    with pytest.raises(ValueError):
        operations.update_thumbnail(MFID, 12, thumbnail_name=thumbnail_name)

    operations._request.assert_not_called()
