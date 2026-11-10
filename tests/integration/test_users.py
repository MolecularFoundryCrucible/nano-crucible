"""Integration tests for client.users.*"""

import pytest


def test_user_search(client):
    results = client.users.search('fab', limit=5)
    assert isinstance(results, list)


def test_user_get_self(client):
    profile = client.account.profile()
    uid = profile.get('unique_id') or profile.get('orcid')
    u = client.users.get(uid)
    assert u.get('unique_id') == uid


def test_user_resolve(client):
    profile = client.account.profile()
    uid = profile.get('unique_id') or profile.get('orcid')
    try:
        result = client.users.resolve(user_unique_ids=[uid])
        assert isinstance(result, dict)
    except Exception as e:
        if '403' in str(e):
            pytest.skip("admin required")
        raise
