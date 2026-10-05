---
name: nano-crucible-cast-development
description: Implement or review nano-crucible cast recipe loading, building, validation, lock files, execution, and resumability. Use for work under crucible/cast/ or the crucible cast command.
---

# nano-crucible cast development

Follow [`nano-crucible-development`](../nano-crucible-development/SKILL.md). Cast is a stateful workflow, so preserve behavior across loading, validation, entity creation, file upload, linking, lock persistence, resumption, builder output, and CLI presentation.

## Preserve execution invariants

- Resolve recipe-relative files and metadata against the `.crux` file directory.
- Validate references, relationship types, duplicate identifiers, and parent-child cycles before live mutations begin.
- Preserve relationship direction: dataset parent to child, sample parent to child, and dataset to associated sample.
- Mark a newly created entity in the lock before uploading its files so a partial upload failure does not create a duplicate record on retry.
- Track each file independently with its relative path, content hash, and ingestion request ID. A resumed run must skip completed files and retry pending work.
- Parser-based resume must reconstruct parser-derived assets; direct datasets can reuse the resolved recipe file list.
- Entity hashes detect recipe changes after creation. Do not silently overwrite or recreate a changed server record.
- Keep dry-run behavior free of API mutations and avoid writing state that makes a later real run skip work.
- Preserve exclusive `.lck` protection and clean it up after normal completion or handled failure.

Changes to cast models, loader output, builder serialization, executor state, and CLI status often affect one another. Search all call sites and lock-field readers before renaming or removing anything. Treat existing lock files as a compatibility surface.

Load [`nano-crucible-parser-development`](../nano-crucible-parser-development/SKILL.md) when changing parser-backed recipes, and load [`nano-crucible-api-development`](../nano-crucible-api-development/SKILL.md) when cast requires a new client operation.

## Test every affected state path

Use `tmp_path` and a mocked client. Cover fresh creation, dry run, resume after entity creation, resume after a partial file failure, parser-backed resume, changed entity hashes, already-applied links, unresolved references, cycles, lock exclusion, and CLI status or reset behavior as applicable to the change.

Assert both client calls and lock contents. A happy-path smoke test is insufficient because signature and lock-format changes can fail only during resumption. Do not use a live API for routine cast validation.
