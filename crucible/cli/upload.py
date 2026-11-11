"""`crucible upload`, removed in 4.0.0 in favour of `crucible dataset create`."""


def register_subcommand(subparsers):
    from .helpers import add_removed_command
    add_removed_command(subparsers, 'upload', "'crucible dataset create -i FILE ...'")
