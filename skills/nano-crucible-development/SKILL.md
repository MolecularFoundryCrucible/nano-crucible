---
name: nano-crucible-development
description: Shared workflow and invariants for changing nano-crucible source, tests, or docs, with routing to the API, CLI, parser, and cast subsystem skills. Use for any development task in this repository; do not use for operating Crucible on a user's behalf.
---

# nano-crucible development

## Route to a subsystem skill

Load the smallest relevant skill; combine only when a change crosses subsystems.

- Models, transport, resource methods: [`nano-crucible-api-development`](../nano-crucible-api-development/SKILL.md)
- CLI commands, help, display, completion: [`nano-crucible-cli-development`](../nano-crucible-cli-development/SKILL.md)
- Client-side parsers and parser discovery: [`nano-crucible-parser-development`](../nano-crucible-parser-development/SKILL.md)
- `.crux` recipes, lock files, execution, resume: [`nano-crucible-cast-development`](../nano-crucible-cast-development/SKILL.md)
- Cutting a release: [`nano-crucible-release`](../nano-crucible-release/SKILL.md)

## Validate

```bash
python -m pip install -e ".[dev,docs]"
pytest tests/unit -q
mkdocs build
```

Iterate on the smallest relevant test set, then run all unit tests. Run `tests/integration/` only when the user authorizes live writes, and only against the `crucible-test` project. `crucible/parsers/` and `crucible/cast/` have little coverage: changes there need a mocked unit test, and a rename or removal needs a search of every call site.

## Invariants

- `AVAILABLE_INGESTORS` is a client-side completion list, not what the server supports. `ingestor=None` means server auto-detection; `ApiUploadIngestor` is not a fallback for unknown formats.
- Most models use `extra="allow"`, so removing a field does not stop callers from sending it. Search constructors and payload builders for the old name.
- Keep Python 3.10 syntax. Keep the library quiet: use package logging, and put terminal output in `crucible/cli/`.
- Do not paper over a client/server mismatch by inventing server behavior. The server's generated OpenAPI is authoritative for the HTTP contract; `crucible-api` is read-only reference.

## Ship a change

- Update docstrings, `docs/`, CLI help, examples, and tests in the same change as public behavior. `docs/cli/reference.md` is the canonical CLI inventory.
- For a user-visible change, add one short line under `## Unreleased` in `docs/changelog.md` (`Added`, `Changed`, or `Fixed`), describing the user-facing result. Internal refactors need no entry.
- Changing a public signature needs a deprecation path (`crucible/utils/deprecation.py`), not a silent alias or break.
- Shared branch is `dev`, release branch is `main`. Commit each verified subtask separately, excluding unrelated working-tree changes. Do not switch branches or push unless asked.
- Cross-repository changes cannot land atomically: link the coordinated issues or PRs and land the producer (usually `crucible-api`) first.
