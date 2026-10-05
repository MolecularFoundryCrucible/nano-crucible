---
name: nano-crucible-release
description: Prepare and publish a nano-crucible release to PyPI, including version bump, changelog consolidation, merge to main, and GitHub release. Use only when the user asks to cut or prepare a release.
---

# nano-crucible release

Each step after preparation is outward-facing. Confirm with the user before merging, tagging, or publishing.

## Prepare on `dev`

1. Pick the version with the user (semver: breaking change bumps major, new feature bumps minor).
2. Set `__version__` in `crucible/__init__.py`; `pyproject.toml` reads it dynamically.
3. In `docs/changelog.md`, rename `## Unreleased` to `## X.Y.Z` and add a fresh empty `## Unreleased` above it. Consolidate entries: merge duplicates and follow-ups to the same feature, keep one short line each, and drop entries for changes reverted within the cycle.
4. Run `pytest tests/unit -q` and `mkdocs build`.
5. Commit as `Prepare X.Y.Z release`.

## Publish

1. Open a PR from `dev` to `main` and merge it once CI passes.
2. Create a GitHub release on `main` with tag `vX.Y.Z` and the changelog section as notes: `gh release create vX.Y.Z --target main --title vX.Y.Z --notes-file <notes>`.
3. Publishing the release triggers `.github/workflows/publish-to-pypi.yml`, which fails if the tag does not match `__version__`. Docs redeploy on push to `main`.

For a build-only dry run, dispatch `publish-to-pypi.yml` manually with `publish` unchecked.
