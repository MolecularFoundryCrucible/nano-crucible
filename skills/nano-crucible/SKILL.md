---
name: nano-crucible
description: Locate the authoritative shared skill for operating the nano-crucible Python client or CLI, with a minimal safety fallback when the ecosystem skill is unavailable. Use for Crucible client workflows; do not use for Nano development or direct server implementation.
---

# nano-crucible compatibility shim

The authoritative operational skill is [`crucible-ecosystem/skills/nano-crucible`](https://github.com/MolecularFoundryCrucible/crucible-ecosystem/blob/main/skills/nano-crucible/SKILL.md). If it is not already installed, look for `skills/nano-crucible/SKILL.md` in a sibling `crucible-ecosystem` checkout and read it completely. Do not expand this shim into a second maintained copy.

If the ecosystem skill is unavailable, use Nano's [published documentation](https://molecularfoundrycrucible.github.io/nano-crucible/) and the installed `crucible --help` hierarchy for exact behavior. Establish the API URL, project, and identity before any network operation. Never expose credentials or full configuration. Treat create, update, upload, link, permission, publication, ownership, ingestion, and deletion operations as live mutations requiring the user's requested outcome and a clear target. Platform administrators run elevated by default, so a mutation can reach records outside the user's own access; confirm the target, and do not add `--elevated` or `privilege_mode='elevated'` unless the user asks. Do not run Nano integration tests as routine validation because they create persistent records.

For changes to Nano source code, stop using this operational shim and follow [`nano-crucible-development`](../nano-crucible-development/SKILL.md).
