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
crucible link -p PARENT_ID -c CHILD_ID
crucible open RESOURCE_ID
```

## Interactive shell

Running `crucible` with no arguments starts an interactive shell with tab-completion, command history, and a status bar:

```bash
crucible
```

The shell opens with a compact 16×16 Crucible mark, combining two vertical pixels in one terminal cell to preserve its proportions. Beside it, a session summary shows the Nano version, the signed-in user and platform role, the API (production, staging, or its host), its full URL and version, whether you use an API key or a sign-in and where it is kept, the current project, the access mode (normal or elevated), and any pending reviews. When PyPI has a newer stable release, the summary names it and the command to upgrade; the shell asks PyPI at most once a day, never for editable or pre-release installs, and `config set update_check false` (or `CRUCIBLE_UPDATE_CHECK=false`) turns the check off. Narrower terminals show the summary below the mark, and very narrow ones show the summary alone. Startup fetches projects, reviews, and the API version in parallel. If the API is unreachable, the shell says so and exits. Without a credential, or when the server refuses it, the shell opens signed out: it runs only `login`, `config`, `status`, `help`, and `exit`, and connects as soon as `login` or `config` provides a working credential.

The status bar shows a microscope for the effective project (`[env]` when it comes from the environment), a bear for the user with `signed in`, `key`, or `key [env]` when `CRUCIBLE_API_KEY` is set, and a link for the API by name. The API version appears there only when it deserves a look: a pre-release, or a server older than the client's major version. On narrow terminals the bar drops the credential and then the user, and shortens the project, but always keeps the API and the `ELEVATED` and `DEBUG` badges. Its dark-blue and light-blue blocks use orange separators, while staging, custom endpoints, a noteworthy API version, and debug mode use orange as an attention color. The shell uses exact 24-bit colors when the terminal advertises true color (`COLORTERM=truecolor`, iTerm2, VS Code, WezTerm, Windows Terminal, or a `TERM` ending in `-direct`), and hand-picked 256- or 16-color equivalents otherwise. SSH does not forward `COLORTERM` by default, so a true-color terminal falls back to 256 colors on a remote host; set `PROMPT_TOOLKIT_COLOR_DEPTH=DEPTH_24_BIT` there, or forward the variable with `SendEnv COLORTERM` on the client and `AcceptEnv COLORTERM` on the server. `PROMPT_TOOLKIT_COLOR_DEPTH` also accepts `DEPTH_8_BIT`, `DEPTH_4_BIT`, and `DEPTH_1_BIT`.

Tab-completion searches the API as you type: resource names complete to MFIDs, projects and instruments to their slugs, users to usernames, and filter values such as measurement or sample type to the values that exist in the current or typed project. Commands and flags you cannot use, such as service-account administration, are not suggested.

An explicit `--project-id` applies only to that command. Inside the interactive shell, `use PROJECT_ID` validates and saves the current project for future commands and shell sessions. `unuse` clears the saved project.

Shell-specific commands:

| Command | Description |
|---|---|
| `use PROJECT_ID` | Validate and save the current project (tab-completes project IDs) |
| `unuse` | Clear the saved current project |
| `refresh` | Re-read config, permissions, projects, and pending reviews |
| `reload` | Re-exec the process (picks up code changes) |
| `debug on` / `debug off` | Toggle debug logging |
| `elevate on` / `elevate off` | Toggle platform-administrator elevation; an `ELEVATED` badge appears in the toolbar while it is on. It starts on when the API runs you elevated by default (an administrator's API key, unless `privilege_mode` is `normal`), and switches off after 15 idle minutes at the prompt (`elevation_timeout`, `CRUCIBLE_ELEVATION_TIMEOUT`; `0` keeps it on) |
| `elevate COMMAND` | Run one command with platform-administrator elevation, like `--elevate COMMAND` |
| `more` | Show the next page of the last listing, continuing from where it stopped with the same filters and limit |
| `help` | List commands, shell commands, and keyboard shortcuts |
| `help COMMAND [SUBCOMMAND]` | Show a command's options, like `crucible COMMAND --help` |
| `exit` / `quit` | Exit the shell |

Commands that take longer than two seconds print how long they took; those that wait on an editor, a browser, or a shell command do not. Creating or updating a project refreshes project completion right away.

## Global flags

| Flag | Effect |
|---|---|
| `--debug` | Print HTTP calls, raw responses, and tracebacks. Must come **before** the resource name. |
| `-E`, `--elevate` | Run one command with platform-administrator elevation. Must come **before** the resource name. |
| `--no-color` | Disable ANSI colors while retaining interactive terminal hyperlinks. Must come **before** the resource name. |
| `--no-pager` | Print a long listing directly even when the `pager` setting is `auto`. Must come **before** the resource name. |
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

`config init` offers to create an API key after a browser sign-in, and hides a pasted key. It also warns when an active environment variable will override a value saved by the wizard.

Destructive commands default confirmation to no and accept `yes`, `y`, `no`, or `n`. When stdin is not interactive, supply the command's explicit `--yes` option. Ownership transfers and project reassignments use a different safety model: they preview by default and execute only with `--confirm`.

## Editing in your editor

`edit` commands (`crucible edit MFID`, `dataset edit`, `instrument edit`, `config edit`, ...) open the record as JSON in a text editor and apply your changes when the editor closes. The editor comes from the `editor` config key, `CRUCIBLE_EDITOR`, `VISUAL`, or `EDITOR`; otherwise the first available of VS Code, Notepad++, and Notepad on Windows, VS Code, nano, and vim on macOS, or VS Code, nano, vim, vi, gedit, and kate on Linux.

The editor must keep the command waiting until you close the file. Editors that open in an existing window get their wait flag added automatically, so `code` becomes `code --wait`:

| Editor | Setting | Notes |
|---|---|---|
| Notepad | `notepad` | Windows default; waits on its own |
| VS Code | `code` | `--wait` added automatically; close the tab to finish |
| Notepad++ | `notepad++` | `-multiInst -nosession` added automatically |
| Sublime Text | `subl` | `--wait` added automatically |
| vim, nano | `vim`, `nano` | Terminal editors wait on their own |

Quote paths that contain spaces, for example `crucible config set editor "\"C:\Program Files\Notepad++\notepad++.exe\""`.

## Tab completion

Install shell tab-completion once:

```bash
crucible completion bash    # bash
crucible completion zsh     # zsh
crucible completion fish    # fish
```

Follow the printed instructions to activate it in your shell.

The interactive Crucible shell completes command flags and fixed choices. It searches users, projects, instruments, datasets, and samples after three typed characters, returning canonical usernames, project or instrument IDs, and resource MFIDs as appropriate. Searches are scoped to the active project for dataset and sample suggestions. A search waits until typing pauses for a moment, so fast typing does not send a request per keystroke.

## First-time setup

```bash
crucible login            # sign in with a browser
crucible login --device   # over SSH or without a browser
crucible login --paste    # when the browser cannot reach this terminal: paste a code
```

For scripts, CI, and batch jobs, use an API key instead: `crucible config init` walks through setting it and optional local defaults, or set `CRUCIBLE_API_KEY`. See [Installation → Configuration](../installation.md#configuration) for details.

## Full command reference

See the [Command Reference](reference.md) for all commands, options, and examples.
