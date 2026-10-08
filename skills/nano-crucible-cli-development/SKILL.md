---
name: nano-crucible-cli-development
description: Implement or review nano-crucible CLI commands, help, terminal output, interactive completion, and command documentation. Use for work under crucible/cli/; combine with the API development skill when a command changes resource behavior.
---

# nano-crucible CLI development

Follow [`nano-crucible-development`](../nano-crucible-development/SKILL.md), then inspect the target command module and neighboring commands before editing. Load [`nano-crucible-api-development`](../nano-crucible-api-development/SKILL.md) when the task also changes Python resource behavior.

## Keep command wiring complete

- Define or update the command in its resource module and confirm that `crucible/cli/__init__.py` imports and registers the module.
- Search `_DEPRECATED_SUBCOMMANDS`, shell completion, keybindings, aliases, and generic commands such as `get`, `edit`, and `download` when names or arguments change.
- Prefer one canonical flag spelling with compatibility warnings for supported old forms. Check [`crucible/cli/KNOWN_ISSUES.md`](../../crucible/cli/KNOWN_ISSUES.md) before introducing a short flag.
- Get the client with `get_client()` from `crucible.config`, never `CrucibleClient()`: the shell shares one client across commands so its session, privilege mode, and cached profile carry over. Tests patch `crucible.config.get_client`.
- Keep API work in `crucible/resources/`. CLI modules should parse input, call the client, present results, and translate expected failures into useful command errors.
- Make destructive or access-changing commands identify their target and retain the established confirmation behavior.
- Gate a command that needs an account capability with `require_capability()` from `helpers.py` so it fails before the request; it defers to the API when the capability is unknown.

## Match terminal conventions

For tables, detail views, colors, timestamps, and interactive completion metadata, read and follow [`crucible/cli/DISPLAY_GUIDE.md`](../../crucible/cli/DISPLAY_GUIDE.md). Reuse `term` and `helpers` functions rather than recreating formatting. Follow nearby commands for stdout, stderr, JSON output, and exit status behavior.

Treat `--help` as a public interface. Keep the parser description, option help, examples, aliases, and `docs/cli/reference.md` consistent with the actual implementation. The published reference is the canonical command inventory; do not recreate it in `crucible/cli/README.md`.

## Verify command behavior

Exercise parser construction and dispatch with a mocked client or focused unit test. Cover successful parsing, required arguments, relevant aliases or deprecations, JSON output when supported, and nonzero exit behavior for failures. Do not use the live API merely to test argument handling or display.

Run `python -m crucible.cli <resource> <command> --help` for every changed command.
