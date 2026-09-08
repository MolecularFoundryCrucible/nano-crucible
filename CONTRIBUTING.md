# Contributing to nano-crucible

Thank you for helping improve the Crucible Python client and CLI. Bug fixes, documentation, tests, and new parsers are all welcome.

## Set up a development environment

Clone the repository and install the package in editable mode:

```bash
git clone https://github.com/MolecularFoundryCrucible/nano-crucible.git
cd nano-crucible
python -m pip install -e ".[dev,docs]"
```

The package supports Python 3.9 and newer. Avoid syntax that requires a newer version unless the supported-version policy changes in the same contribution.

## Make and verify a change

Run the local unit tests:

```bash
pytest tests/unit -q
```

Build the documentation when changing Markdown, docstrings, or public APIs:

```bash
mkdocs build
```

Integration tests are not ordinary local tests. They call a live Crucible API, require credentials, create records, and do not remove those records afterward. If live verification is necessary, configure a non-production account and run only the relevant module against the `crucible-test` project:

```bash
pytest tests/integration/test_datasets.py -v
```

Never put an API key in source code, test output, notebooks, or commits.

## Keep public interfaces documented

The public Python interface is organized into resource namespaces such as `client.datasets`, `client.samples`, and `client.projects`. Update docstrings, the relevant page under `docs/`, CLI help, examples, and tests when changing a public operation.

Add a concise entry under `## Unreleased` in `docs/changelog.md` for user-visible changes. Use the existing `Added`, `Changed`, or `Fixed` headings and describe the user-facing result in one short line. Internal refactors need no entry.

CLI examples should be checked against the installed development version:

```bash
crucible --help
crucible dataset --help
```

## Keep documentation authorities synchronized

Nano's `README.md`, published documentation, public docstrings, and CLI help describe supported package behavior for users. `CONTRIBUTING.md` defines the human contribution workflow. `AGENTS.md` and repository-local development skills add agent-specific routing, implementation invariants, and safety rules without replacing the user documentation.

The generated OpenAPI document from `crucible-api` is authoritative for the HTTP contract. Ecosystem ownership, compatibility policy, lifecycle decisions, and cross-repository workstreams belong in [`crucible-ecosystem`](https://github.com/MolecularFoundryCrucible/crucible-ecosystem). Link to those authorities instead of copying complete endpoint, schema, command, or policy inventories into Nano.

When a change spans repositories, identify the authoritative producer and link the coordinated issues, pull requests, or commits. Update Nano-owned behavior and documentation together, and record temporary compatibility behavior when producer and consumer changes cannot land simultaneously.

## Add a parser

Parser-specific architecture and registration instructions are in [`crucible/parsers/README.md`](crucible/parsers/README.md). Add focused unit tests for parsing logic and use mocked clients for upload behavior; parser development should not require writing records to the live service.

## Coding-agent guidance

Repository-aware coding agents should read [`AGENTS.md`](AGENTS.md), which routes API, CLI, parser, and cast changes to the relevant development skill under [`skills/`](skills/). The operational [`nano-crucible` ecosystem skill](https://github.com/MolecularFoundryCrucible/crucible-ecosystem/blob/main/skills/nano-crucible/SKILL.md) is authoritative; Nano retains a small [discovery and safety shim](skills/nano-crucible/SKILL.md) for agents that cannot load the shared skill directly.
