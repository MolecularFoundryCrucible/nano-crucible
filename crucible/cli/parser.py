"""Argument parser that suggests the closest command or flag on a typo."""

import argparse
import difflib
import re

_INVALID_CHOICE = re.compile(r"invalid choice: '([^']*)'")
_UNRECOGNIZED = 'unrecognized arguments: '


class SuggestingArgumentParser(argparse.ArgumentParser):
    """ArgumentParser whose errors end with "Did you mean ...?" when a close match exists.

    Subparsers inherit the class, so one root parser covers every command.
    Unknown flags are reported by the root parser, so it remembers the
    command line and matches against the options of the command reached.
    """

    def parse_known_args(self, args=None, namespace=None):
        if args is not None:
            self._argv = list(args)
        return super().parse_known_args(args, namespace)

    def error(self, message):
        unknown = self._unknown_command(message)
        if unknown is not None:
            suggestion = _closest(unknown, list(self._subcommands().choices))
            tail = (f"Did you mean '{suggestion}'?" if suggestion
                    else f"Run '{self.prog} --help' to see them.")
            self.exit(2, f"{self.prog}: error: '{unknown}' is not a {self.prog} command. {tail}\n")
        suggestion = self._suggestion(message)
        if suggestion:
            message = f"{message}\nDid you mean '{suggestion}'?"
        super().error(message)

    def _subcommands(self):
        return next((action for action in self._actions
                     if isinstance(action, argparse._SubParsersAction)), None)

    def _unknown_command(self, message):
        """The mistyped word when message rejects a subcommand name, else None."""
        subcommands = self._subcommands()
        match = _INVALID_CHOICE.search(message)
        if subcommands is None or match is None:
            return None
        name = argparse._get_action_name(subcommands)
        return match.group(1) if message.startswith(f"argument {name}:") else None

    def _suggestion(self, message):
        match = _INVALID_CHOICE.search(message)
        if match:
            choices = [str(choice) for action in self._actions if action.choices
                       for choice in action.choices]
            return _closest(match.group(1), choices)
        if message.startswith(_UNRECOGNIZED):
            flags = [token for token in message[len(_UNRECOGNIZED):].split()
                     if token.startswith('-')]
            options = list(self._command_parser()._option_string_actions)
            for flag in flags:
                close = _closest(flag.split('=', 1)[0], options)
                if close:
                    return close
        return None

    def _command_parser(self):
        """The deepest subcommand parser reached by the remembered command line."""
        parser = self
        for token in getattr(self, '_argv', []):
            subparsers = parser._subcommands()
            if subparsers is None:
                break
            if token in subparsers.choices:
                parser = subparsers.choices[token]
        return parser


def _closest(word, candidates):
    matches = difflib.get_close_matches(word, candidates, n=1, cutoff=0.6)
    return matches[0] if matches else None
