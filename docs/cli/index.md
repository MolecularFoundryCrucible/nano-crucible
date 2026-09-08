# CLI Overview

nano-crucible ships a full command-line interface under the `crucible` command. All operations available in the Python API are also available from the terminal.

## Structure

Resource commands follow a consistent pattern:

```
crucible [--debug] [--no-color] <resource> <action> [options]
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

The shell opens with a compact 16×16 Crucible mark when the terminal is wide enough to display it. It combines two vertical pixels in one terminal cell to preserve the mark's proportions. The status bar uses a microscope for the effective project, a bear for the authenticated user, and a link for the configured API. Its dark-blue and light-blue blocks use orange separators, while staging, custom endpoints, and debug mode use orange as an attention color. The shell automatically uses exact 24-bit colors when the terminal advertises true-color support.

An explicit `--project-id` applies only to that command. Inside the interactive shell, `use PROJECT_ID` validates and saves the current project for future commands and shell sessions. `unuse` clears the saved project. The deprecated `CRUCIBLE_CURRENT_PROJECT` environment variable temporarily retains precedence, but the CLI displays a warning whenever it supplies project context.

Shell-specific commands:

| Command | Description |
|---|---|
| `use PROJECT_ID` | Validate and save the current project (tab-completes project IDs) |
| `unuse` | Clear the saved current project |
| `refresh` | Re-fetch project list and user info |
| `reload` | Re-exec the process (picks up code changes) |
| `debug on` / `debug off` | Toggle debug logging |
| `help` | List available commands |
| `exit` / `quit` | Exit the shell |

## Global flags

| Flag | Effect |
|---|---|
| `--debug` | Print HTTP calls, raw responses, and tracebacks. Must come **before** the resource name. |
| `--no-color` | Disable ANSI colors while retaining interactive terminal hyperlinks. Must come **before** the resource name. |
| `--version` | Print version and exit. |

```bash
crucible --debug dataset list   # --debug must precede the subcommand
```

Colors are enabled only for interactive terminals. Set the standard `NO_COLOR` environment variable or use `--no-color` to disable them explicitly. Clickable links remain available in interactive terminals and are omitted from redirected output.

Tables adapt to the terminal width. Descriptive columns shrink before protected usernames, resource slugs, and MFIDs whenever space permits. Redirected table output uses a stable 100-column layout.

## Errors and warnings

CLI errors retain the HTTP status and reason while presenting API validation details in a readable form:

```text
Error 422 Unprocessable Entity
Failed while creating instrument.

  public  Extra inputs are not permitted
```

Commands supporting `--json` emit structured errors to stderr when JSON output is selected. `--debug` additionally prints HTTP diagnostics and a traceback. Warnings use the same terminal presentation without Python source locations, while direct Python use of `CrucibleClient` retains standard Python warning behavior.

For machine-readable workflows, supported collection and search commands emit JSON arrays, singleton commands emit JSON objects, and empty collections emit `[]`. JSON contains raw client values without terminal links, relative timestamps, or placeholder text. See the [command reference](reference.md) for the current supported command set.

## Interactive prompts

Creation commands prompt for missing required fields when run in an interactive terminal. Required, optional, and defaulted values are identified consistently. Invalid values show an explanation and prompt again instead of being discarded or submitted to the API.

When stdin is not interactive, optional prompts are skipped and configured defaults remain usable. A missing required value exits with status 2 and identifies the command-line option that must be supplied.

`config init` hides API-key input. It also warns when an active environment variable will override a value saved by the wizard.

Destructive commands default confirmation to no and accept `yes`, `y`, `no`, or `n`. When stdin is not interactive, supply the command's explicit `--yes` option. Ownership transfers and project reassignments use a different safety model: they preview by default and execute only with `--confirm`.

## Tab completion

Install shell tab-completion once:

```bash
crucible completion bash    # bash
crucible completion zsh     # zsh
crucible completion fish    # fish
```

Follow the printed instructions to activate it in your shell.

The interactive Crucible shell completes command flags and fixed choices. It searches users, projects, instruments, datasets, and samples after three typed characters, returning canonical usernames, project or instrument IDs, and resource MFIDs as appropriate. Searches are scoped to the active project for dataset and sample suggestions.

## First-time setup

```bash
crucible config init
```

This walks through setting your API key and optional local defaults. See [Installation → Configuration](../installation.md#configuration) for details.

## Full command reference

See the [Command Reference](reference.md) for all commands, options, and examples.
