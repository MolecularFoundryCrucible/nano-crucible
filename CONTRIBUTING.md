# Contributing to nano-crucible

Thank you for helping improve the Crucible Python client and CLI. Bug fixes, documentation, tests, and new parsers are all welcome.

## Set up a development environment

Clone the repository and install the package in editable mode:

```bash
git clone https://github.com/MolecularFoundryCrucible/nano-crucible.git
cd nano-crucible
python -m pip install -e ".[dev,docs]"
```

The package supports Python 3.10 and newer.

## Make and verify a change

Run the local unit tests:

```bash
pytest tests/unit -q
```

Build the documentation when changing Markdown, docstrings, or public APIs:

```bash
mkdocs build
```

Integration tests call a live Crucible API, require credentials, create records, and do not remove those records afterward. If live verification is necessary, configure a non-production account and run only the relevant module against the `crucible-test` project:

```bash
pytest tests/integration/test_datasets.py -v
```

Please never put an API key in source code, test output, notebooks, or commits.

## Keep public interfaces documented

The public Python interface is organized into resource namespaces such as `client.datasets`, `client.samples`, and `client.projects`. Update docstrings, the relevant page under `docs/`, CLI help, examples, and tests when changing a public operation.

Add a concise entry under `## Unreleased` in `docs/changelog.md` for user-visible changes. Use the existing `Added`, `Changed`, or `Fixed` headings and describe the user-facing result in one short line. Internal refactors need no entry.

CLI examples should be checked against the installed development version:

```bash
crucible --help
crucible dataset --help
```

## Keep documentation authorities synchronized

Nano's `README.md`, published documentation, public docstrings, and CLI help describe supported package behavior for users. `CONTRIBUTING.md` defines the human contribution workflow. `AGENTS.md` and the skills under `skills/` add agent-specific routing, implementation invariants, and safety rules without replacing the user documentation.

The generated OpenAPI document from `crucible-api` is authoritative for the HTTP contract. Ecosystem ownership, compatibility policy, lifecycle decisions, and cross-repository workstreams belong in [`crucible-ecosystem`](https://github.com/MolecularFoundryCrucible/crucible-ecosystem). Link to those authorities instead of copying complete endpoint, schema, command, or policy inventories into Nano.

When a change spans repositories, identify the authoritative producer and link the coordinated issues, pull requests, or commits. Update Nano-owned behavior and documentation together, and record temporary compatibility behavior when producer and consumer changes cannot land simultaneously.

## Coding agents

[`AGENTS.md`](AGENTS.md) is a short entry point that most agent tools load automatically. It routes to skills under [`skills/`](skills/): [`nano-crucible`](skills/nano-crucible/SKILL.md) for using Crucible through the client, and [`nano-crucible-development`](skills/nano-crucible-development/SKILL.md) for changing this package.

If you prefer your own agent context, opt out locally without editing the committed file (both paths are gitignored):

- Codex: create an `AGENTS.override.md` at the repository root; it replaces `AGENTS.md`.
- Claude Code: add `"claudeMdExcludes": ["**/nano-crucible/AGENTS.md", "**/nano-crucible/CLAUDE.md"]` to `.claude/settings.local.json`.
