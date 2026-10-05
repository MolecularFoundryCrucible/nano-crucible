# nano-crucible agent guide

Agents work in this repository for one of two purposes. Pick the matching skill and read it before acting.

- **Using Crucible** (configuring the client, creating or updating records, uploading files, linking, querying): [`skills/nano-crucible/SKILL.md`](skills/nano-crucible/SKILL.md).
- **Developing nano-crucible** (changing code, tests, or docs in this repository): [`skills/nano-crucible-development/SKILL.md`](skills/nano-crucible-development/SKILL.md), which routes to subsystem skills. For releases: [`skills/nano-crucible-release/SKILL.md`](skills/nano-crucible-release/SKILL.md).

## Always

- Any create, update, upload, link, permission, publication, or deletion call writes to a live Crucible API. Make one only when the user asked for that outcome and the target (API URL, project, record) is clear.
- `tests/integration/` hits a live API and leaves records behind. Do not run it as routine validation; use `pytest tests/unit -q`.
- Never print, log, or commit API keys or the full config file.
- Do not push, publish, tag, or edit companion repositories (`crucible-api`, `crucible-ecosystem`, ingestion) unless asked.

Contributors who prefer their own agent setup can opt out of this file; see "Coding agents" in [`CONTRIBUTING.md`](CONTRIBUTING.md).
