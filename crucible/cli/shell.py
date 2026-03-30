#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interactive shell for the Crucible CLI.

Starts when `crucible` is invoked with no arguments.
Uses prompt_toolkit if available, falls back to readline + input().
"""

import shlex
import logging

logger = logging.getLogger(__name__)

_BANNER = """\
Crucible interactive shell  (type 'help' for commands, 'exit' to quit)"""

_PROMPT = "crucible> "


# ---------------------------------------------------------------------------
# Argparse-backed completer (used by prompt_toolkit)
# ---------------------------------------------------------------------------

def _get_subparser_map(parser):
    """Return {name: subparser} for a parser's subcommands, or {} if none."""
    for action in parser._actions:
        if hasattr(action, 'choices') and isinstance(action.choices, dict):
            return action.choices or {}
    return {}


try:
    from prompt_toolkit.completion import Completer, Completion

    class _CrucibleCompleter(Completer):
        """Three-level argparse completer: resource → subcommand → flags."""

        def __init__(self, parser):
            self._top = _get_subparser_map(parser)

        def get_completions(self, document, complete_event):
            text  = document.text_before_cursor
            words = text.split()
            # Are we in the middle of a word, or just after a space?
            trailing_space = text.endswith(' ')

            # ── level 0: complete top-level resource ──────────────────────
            if not words or (len(words) == 1 and not trailing_space):
                prefix = words[0] if words else ''
                for name in self._top:
                    if name.startswith(prefix):
                        yield Completion(name, start_position=-len(prefix))
                return

            resource = words[0]
            sub_map  = _get_subparser_map(self._top.get(resource)) \
                       if resource in self._top else {}

            # ── level 1: complete subcommand ──────────────────────────────
            if len(words) == 1 or (len(words) == 2 and not trailing_space):
                prefix = words[1] if len(words) == 2 else ''
                for name in sub_map:
                    if name.startswith(prefix):
                        yield Completion(name, start_position=-len(prefix))
                return

            # ── level 2+: complete flags for the chosen subcommand ────────
            subcommand = words[1]
            sub_parser = sub_map.get(subcommand)
            if sub_parser is None:
                return

            current_word = '' if trailing_space else words[-1]
            if not current_word.startswith('-'):
                return  # positional args — too context-specific to complete

            for flag in sub_parser._option_string_actions:
                if flag.startswith(current_word):
                    yield Completion(flag, start_position=-len(current_word))

except ImportError:
    _CrucibleCompleter = None


# ---------------------------------------------------------------------------
# Shell entry point
# ---------------------------------------------------------------------------

def run(parser):
    """Start the interactive shell. Called from main() when no command given."""
    print(_BANNER)
    _run_prompt_toolkit(parser) if _CrucibleCompleter else _run_readline(parser)


def _dispatch(parser, line):
    """Parse and execute one line. Returns False to signal exit."""
    from . import _remap_deprecated, setup_logging

    line = line.strip()
    if not line:
        return True
    if line in ('exit', 'quit'):
        return False
    if line == 'help':
        parser.print_help()
        return True

    try:
        argv = _remap_deprecated(shlex.split(line))
        args = parser.parse_args(argv)
        setup_logging(debug=getattr(args, 'debug', False))
        if hasattr(args, 'func'):
            args.func(args)
        else:
            parser.print_help()
    except SystemExit:
        pass  # subcommands call sys.exit() on error — keep the shell alive
    except Exception as e:
        logger.error(f"Error: {e}")

    return True


def _run_prompt_toolkit(parser):
    from prompt_toolkit         import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.styles import Style
    from platformdirs import user_data_dir
    import os

    history_path = os.path.join(user_data_dir('crucible'), 'shell_history')
    os.makedirs(os.path.dirname(history_path), exist_ok=True)

    # Show current project in the bottom toolbar
    def _toolbar():
        try:
            from crucible.config import config
            proj = config.current_project or '(no project set)'
        except Exception:
            proj = '?'
        return f' project: {proj} '

    session = PromptSession(
        history=FileHistory(history_path),
        auto_suggest=AutoSuggestFromHistory(),
        completer=_CrucibleCompleter(parser),
        complete_while_typing=False,   # only complete on Tab
        bottom_toolbar=_toolbar,
        style=Style.from_dict({'bottom-toolbar': 'bg:#333333 #aaaaaa'}),
    )

    while True:
        try:
            line = session.prompt(_PROMPT)
        except KeyboardInterrupt:
            print()
            continue
        except EOFError:
            break
        if not _dispatch(parser, line):
            break


def _run_readline(parser):
    """Fallback shell using stdlib readline for history."""
    try:
        import readline  # noqa: F401 — activates history/completion automatically
    except ImportError:
        pass

    while True:
        try:
            line = input(_PROMPT)
        except KeyboardInterrupt:
            print()
            continue
        except EOFError:
            break
        if not _dispatch(parser, line):
            break
