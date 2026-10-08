---
name: nano-crucible-api-development
description: Implement or review nano-crucible Python API changes across client transport, Pydantic models, and resource namespaces. Use for work in crucible/client.py, crucible/models.py, or crucible/resources/; do not use for server implementation or CLI-only presentation changes.
---

# nano-crucible API development

Follow [`nano-crucible-development`](../nano-crucible-development/SKILL.md), then use this skill for the Python client API portion of a change.

## Trace the complete contract

Inspect the target resource method, its Pydantic model, neighboring methods, unit tests, API documentation, and any CLI caller before editing. Treat the server repository as read-only evidence when it is available. Do not infer an endpoint contract solely from a stale client example.

When adding a new resource namespace, export the operations class from `crucible/resources/__init__.py` and construct it in `CrucibleClient.__init__`. Keep operations on the narrowest resource namespace; add a root-client method only when the behavior genuinely spans resources.

## Preserve response and payload behavior

- Filter `None` values from request payloads unless the endpoint distinguishes an explicit null from an omitted field.
- Use `BaseResource._paginate()` for paginated envelopes. Datasets and samples use cursor pagination; other current resources use offsets.
- When a response has the shape of an existing dataset, sample, or file model, pass it through the resource's `_parse()` method before returning it.
- Most resource models allow extra fields. Removing a declared field does not prevent callers from sending it, so search model constructors, payload builders, CLI code, parsers, cast, tests, and docs for the old field.
- Preserve intentional compatibility with `_deprecated` or `_removed` helpers when changing a public method or parameter. Do not retain an alias silently.
- Keep endpoint-specific handling narrow. Do not hide authorization, schema, or server errors behind broad exception handling.

## Name identifiers precisely

- Preserve `unique_id` as the canonical identifier field serialized by the API. Store and send MFIDs; `project_id` and `instrument_id` slugs are for human lookup and match case-insensitively. Never use `instrument_name` to identify an instrument: it is free-text display and may repeat.
- Resolve project and instrument slugs through `BaseResource._resource_mfid()`, which their operations override using the exact `?project_id=` / `?instrument_id=` list lookup. Generic `/resources/{mfid}/...` routes accept only MFIDs.
- Name a parameter `dataset_mfid`, `sample_mfid`, `project_mfid`, `instrument_mfid`, or `resource_mfid` when it accepts only an MFID.
- Reserve `project_id` and `instrument_id` for their unique, human-readable API identifiers. Dataset and sample names are display values, not identifiers.
- Use `project_ref`, `instrument_ref`, or `user_ref` only when the client deliberately accepts multiple identifier formats and dispatches them.
- Use `user_unique_id` for an ORCID-or-MFID parameter because a canonical human identifier may now have either shape; an MFID does not imply a service account.
- When replacing an ambiguous public keyword such as `dsid`, preserve it temporarily as an explicit deprecated alias. Positional compatibility should remain intact where practical.
- Keep canonical and exact-filter request methods private. Extract shared request behavior only when validation, request shape, response handling, and error semantics are genuinely identical across resources.
- Dataset and sample route positions, including nested relationship, file, keyword, thumbnail, graph, and download routes, accept MFIDs only. Name their client parameters with `_mfid` even when the server's Python route variable still says `dataset_id`, `sample_id`, or `dsid`.
- Do not rename serialized wire fields. Some link responses use `dataset_id` and `sample_id` for MFID values, while database link models use those names for integer foreign keys; preserve the response contract and clarify only the client parameter names.

## Respect privilege mode and capabilities

- The client sends no `Crucible-Privilege-Mode` header unless one is configured, which the server treats as elevated for platform administrators. Do not change this default without a deprecation cycle.
- An operation that needs elevation requests it per call: `privilege_mode='elevated'` when only administrators can use it, `self._client._admin_mode()` when ordinary callers can also use it (the server rejects `elevated` from an ineligible caller with a 403).
- Use `client.capabilities` (an `AccountCapabilities` model) and the `capabilities` block on resource responses to decide what a caller may do. Refuse only on an explicit `False`; `None` means unknown, so let the API decide. Do not hard-code role assumptions. Capability fields are response-only: strip them from update payloads.

If the change also adds or alters a command, load [`nano-crucible-cli-development`](../nano-crucible-cli-development/SKILL.md).

## Test at the request boundary

Add or update unit tests with a mocked client request boundary. Cover the HTTP method, endpoint, parameters or JSON payload, response-envelope handling, model normalization, and compatibility warning when relevant.
