"""Integration tests for client.account.* and client.whoami()."""


def test_whoami(client):
    info = client.whoami()
    assert info is not None


def test_account_profile(client):
    p = client.account.profile()
    assert p is not None
    assert p.get('unique_id') or p.get('orcid')


def test_account_list_api_keys(client):
    keys = client.account.list_api_keys()
    assert all('id' in key and 'api_key' not in key for key in keys)


def test_account_verify(client):
    info = client.account.verify()
    assert 'valid' in info
    assert info['valid'] is True
