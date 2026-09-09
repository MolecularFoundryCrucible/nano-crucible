# Repository guide for coding agents

This file is the canonical repository guidance for any coding agent. Tool-specific instruction files should point here instead of duplicating it.

## Project overview

`nano-crucible` is the Python client library and command-line interface for Crucible, the Molecular Foundry's scientific data platform.

- Distribution: `nano-crucible`
- Import package: `crucible`
- CLI entry point: `crucible.cli:main`
- Supported Python: 3.9 and newer
- Default API: `https://crucible.lbl.gov/api/v3`
- Documentation: MkDocs Material, configured in `mkdocs.yml`

The companion server and ingestion repositories are useful references when they are available, but they are separate projects. Do not edit them as part of a client task unless the user explicitly expands the scope.

## Repository map

- `crucible/client.py`: HTTP session, authentication, retries, generic operations, and resource namespace construction.
- `crucible/models.py`: Pydantic request and response models.
- `crucible/resources/`: namespaced Python API (`client.datasets`, `client.samples`, `client.projects`, and peers).
- `crucible/resources/gcs/`: upload and download implementation.
- `crucible/cli/`: argparse command modules and terminal display helpers.
- `crucible/config/`: config-file and environment-variable handling.
- `crucible/parsers/`: file parsers that prepare datasets for upload.
- `crucible/cast/`: declarative `.crux` recipe loading, building, and execution.
- `tests/unit/`: mocked, local tests.
- `tests/integration/`: live-API tests that create real records.
- `docs/`: published user and API documentation.
- `skills/nano-crucible/`: compatibility shim for discovering shared operational guidance and retaining a safe fallback.
- `skills/nano-crucible-*-development/`: subsystem-specific guidance for agents developing the package.

## Skill routing

Use the smallest relevant development skill and combine skills only when a change crosses subsystem boundaries:

- Python models, transport, or resource methods: `skills/nano-crucible-api-development/SKILL.md`
- CLI commands, help, display, or completion: `skills/nano-crucible-cli-development/SKILL.md`
- Client-side dataset parsers or parser discovery: `skills/nano-crucible-parser-development/SKILL.md`
- `.crux` recipes, builders, lock files, execution, or resume behavior: `skills/nano-crucible-cast-development/SKILL.md`
- Configuring or operating Crucible on a user's behalf: use the authoritative [`nano-crucible` ecosystem skill](https://github.com/MolecularFoundryCrucible/crucible-ecosystem/blob/main/skills/nano-crucible/SKILL.md); if it is not installed, check a sibling `crucible-ecosystem` checkout, then use `skills/nano-crucible/SKILL.md` as the discovery and safety fallback

This file remains authoritative for shared repository rules. Skills add conditional subsystem guidance and do not expand permission to mutate the live API.

## Documentation authority and synchronization

Assign each fact one authority and update its consumers by reference instead of copying detailed inventories between repositories.

| Scope | Authority |
|---|---|
| Supported Nano behavior and user workflows | `README.md`, `docs/`, public docstrings, and installed CLI help |
| Human contribution workflow | `CONTRIBUTING.md` |
| Repository rules and agent routing | `AGENTS.md` and the repository-local development skills |
| HTTP paths, schemas, and compatibility classification | Deterministic OpenAPI produced by `crucible-api` |
| Ecosystem ownership, lifecycle, compatibility policy, and cross-repository coordination | [`crucible-ecosystem`](https://github.com/MolecularFoundryCrucible/crucible-ecosystem) decisions, standards, and workstreams |
| Shared operational agent guidance | [`crucible-ecosystem`](https://github.com/MolecularFoundryCrucible/crucible-ecosystem/blob/main/skills/nano-crucible/SKILL.md); `skills/nano-crucible/` is the local discovery and safety shim |

Agents use human documentation as the authority for supported package behavior. Agent guidance adds implementation workflow, routing, invariants, and safety boundaries; it must not become a second user manual or a manually maintained copy of the HTTP contract.

Update Nano documentation, docstrings, CLI help, tests, and changelog in the same change as the behavior they describe. Update a local development skill only when its repeatable workflow or architectural invariants change. Update ecosystem documentation only when topology, ownership, compatibility, lifecycle, safety, or a shared workflow changes.

Changes spanning repositories cannot land atomically. Link the coordinated issues, pull requests, or commits; land the authoritative producer before or together with its consumers; and record any temporary compatibility window explicitly.

## Development workflow

Install an editable development environment with:

```bash
python -m pip install -e ".[dev,docs]"
```

Run local validation with:

```bash
pytest tests/unit -q
mkdocs build
```

Use the smallest relevant test set while iterating, then run all unit tests. Treat warnings from a strict documentation build as useful cleanup signals, but do not assume all pre-existing annotation warnings belong to the current change.

Do not run `tests/integration/` merely as routine validation. Those tests require credentials, call a live API, create persistent records, and do not clean them up. Run them only when the task needs live verification and the user has authorized that side effect. Use the `crucible-test` project, never a production project.

`crucible/parsers/` and `crucible/cast/` have little dedicated coverage. Changes there need a mocked smoke test or a new unit test. Exercise all stateful paths affected by the change, including resumption paths in `cast`, and search every call site of renamed or removed symbols.

## Implementation conventions

- Public operations belong under a resource namespace rather than on the root client unless they genuinely span resources.
- Resource methods returning dataset, sample, or file records should validate raw API dictionaries through their Pydantic model (`_parse`) so aliases are normalized and extra server fields are preserved.
- Most resource models use `extra="allow"`. Removing a field from a model does not prove callers stopped sending it; search all model constructors and API payload builders for stale fields.
- `AVAILABLE_INGESTORS` is a client-side completion list, not an authoritative statement of what the server currently supports.
- `ingestor=None` means server-side auto-detection. The generic `ApiUploadIngestor` is not currently a fallback for unknown formats.
- Preserve supported Python 3.9 syntax unless the project explicitly raises its minimum version.
- Keep the library quiet by default. Use package logging rather than unconditional prints; CLI presentation belongs in `crucible/cli/`.
- Never log, print, commit, or place real API keys in examples.

## Documentation and compatibility

Update documentation in the same change as public behavior. Prefer examples that use the current namespaced API (`client.datasets.get`, not removed flat methods) and verify CLI examples against `crucible <command> --help`.

`docs/cli/reference.md` is the canonical CLI command inventory. Keep `crucible/cli/README.md` as a contributor pointer and do not duplicate command tables there.

For a user-visible change, add one short line under `## Unreleased` in `docs/changelog.md`, using only the relevant `Added`, `Changed`, or `Fixed` section. Describe what changed for users, not its implementation. Pure internal refactoring does not need a changelog entry.

When changing a public signature, consider deprecation compatibility and update docstrings, API docs, CLI help, examples, and tests together. Do not silently invent server behavior to compensate for a client/server mismatch.

## Git safety

The shared development branch is `dev`; the release branch is `main`. Prefer creating a focused commit after finishing and verifying each coherent subtask so the working history records stable checkpoints. Before committing, review the diff, exclude unrelated working-tree changes, and use a concise message describing that subtask. Do not switch branches, push, publish, or modify companion repositories unless the user explicitly asks. If the user asks to leave changes uncommitted, follow that instruction. Preserve unrelated working-tree changes, including local agent settings and installed skills.
