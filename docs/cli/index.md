# CLI Overview

nano-crucible ships a full command-line interface under the `crucible` command. All operations available in the Python API are also available from the terminal.

## Structure

Resource commands follow a consistent pattern:

```
crucible [--debug] <resource> <action> [options]
```

Utility commands operate directly on IDs without a sub-action:

```
crucible download DATASET_ID
crucible link PARENT_ID CHILD_ID
crucible open RESOURCE_ID
```

## Interactive shell

Running `crucible` with no arguments starts an interactive shell with tab-completion, command history, and a status bar:

```bash
crucible
```

Shell-specific commands:

| Command | Description |
|---|---|
| `use PROJECT_ID` | Set the active project (tab-completes project IDs) |
| `unuse` | Clear the active project |
| `refresh` | Re-fetch project list and user info |
| `reload` | Re-exec the process (picks up code changes) |
| `debug on` / `debug off` | Toggle debug logging |
| `help` | List available commands |
| `exit` / `quit` | Exit the shell |

## Global flags

| Flag | Effect |
|---|---|
| `--debug` | Print HTTP calls, raw responses, and tracebacks. Must come **before** the resource name. |
| `--version` | Print version and exit. |

```bash
crucible --debug dataset list   # --debug must precede the subcommand
```

## Tab completion

Install shell tab-completion once:

```bash
crucible completion bash    # bash
crucible completion zsh     # zsh
crucible completion fish    # fish
```

Follow the printed instructions to activate it in your shell.

## First-time setup

```bash
crucible config init
```

This walks through setting your API key and default API URL. See [Installation → Configuration](../installation.md#configuration) for details.

## Full command reference

See the [Command Reference](reference.md) for all commands, options, and examples.
