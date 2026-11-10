# Integration Tests

These tests write to a live Crucible API. They run only when both `CRUCIBLE_TEST_API_URL` and `CRUCIBLE_TEST_API_KEY` are set; otherwise every test is skipped. Point them at staging, never production. Your own config, sign-in, and `CRUCIBLE_API_KEY` are not used.

## Setup

```bash
export CRUCIBLE_TEST_API_URL=https://crucible.lbl.gov/testapi-staging
export CRUCIBLE_TEST_API_KEY=...   # a staging key with access to the crucible-test project
```

## Run

```bash
# all integration tests
pytest tests/integration/ -v

# single module
pytest tests/integration/test_datasets.py -v

# stop on first failure
pytest tests/integration/ -x
```

## Notes

- Tests use the `crucible-test` project — do not run against production projects
- Tests create real records; they are not cleaned up automatically
- File upload tests (`test_files.py`) require the `/files/{mfid}/ingest` API endpoint
- Some tests require admin privileges and will be skipped otherwise
