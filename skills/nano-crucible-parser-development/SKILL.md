---
name: nano-crucible-parser-development
description: Create, modify, or review nano-crucible dataset parsers and parser discovery. Use for work under crucible/parsers/ or third-party crucible.parsers entry points; do not use for server-side ingestion plugins.
---

# nano-crucible parser development

Follow [`nano-crucible-development`](../nano-crucible-development/SKILL.md) and consult [`crucible/parsers/README.md`](../../crucible/parsers/README.md) for the public parser interface. Verify that guide against `BaseParser` when behavior matters because parser documentation may lag implementation.

## Respect the parser lifecycle

`BaseParser.__init__()` initializes fields and then calls `self.parse()`. A subclass must be ready to parse before its constructor returns and should keep extraction logic separate enough to test without a client.

- Read input from `self.files_to_upload` and append generated or related files there when they should also be uploaded.
- Set shared dataset fields through the initialized instance attributes and use `add_thumbnail()` for generated previews.
- `add_metadata()` currently updates the existing dictionary, so later values replace existing keys. Make metadata precedence explicit in tests when combining user input and extracted values.
- `add_keywords()` preserves existing order and adds only unseen values.
- A hostname is added after `parse()` unless the parser already supplied one.
- `upload_dataset()` delegates to `client.datasets.create()` and leaves `ingestor=None` for server auto-detection unless the parser has a justified format-specific default.

Built-in parsers belong in `PARSER_REGISTRY` and the module exports. Third-party parsers should use the `crucible.parsers` package entry-point group rather than patching the built-in registry.

Keep client-side parsing distinct from server-side ingestion. A parser prepares dataset fields, metadata, keywords, files, and thumbnails before upload; an ingestor processes an uploaded file on the server.

## Test parsing and upload boundaries

Add deterministic unit tests for valid input, malformed input, missing files, metadata precedence, related-file discovery, and thumbnail behavior that the change affects. Use temporary files and a mocked client for `upload_dataset()`. Do not require credentials or a live API.

When changing registration or discovery, test built-in lookup, case normalization, third-party entry-point loading, and a broken third-party plugin that must warn without hiding built-ins. Run the focused tests and `pytest tests/unit -q`.
