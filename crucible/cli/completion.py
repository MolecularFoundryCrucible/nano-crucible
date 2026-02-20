#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Completion subcommand for installing shell autocomplete.
"""

import sys
import os


def register_subcommand(subparsers):
    """Register the completion subcommand."""
    parser = subparsers.add_parser(
        'completion',
        help='Install shell completion for the crucible command',
        description='Generate and install shell completion scripts'
    )

    parser.add_argument(
        'shell',
        nargs='?',
        choices=['bash', 'zsh', 'fish', 'tcsh'],
        help='Shell type (bash, zsh, fish, tcsh). Auto-detected if not provided.'
    )

    parser.add_argument(
        '--print',
        action='store_true',
        help='Print completion script instead of installing it'
    )

    parser.set_defaults(func=execute)


def execute(args):
    """Execute the completion installation."""
    try:
        import argcomplete
    except ImportError:
        print("Error: argcomplete is not installed", file=sys.stderr)
        print("Install it with: pip install argcomplete", file=sys.stderr)
        sys.exit(1)

    # Detect shell if not provided
    shell = args.shell
    if shell is None:
        shell_env = os.environ.get('SHELL', '')
        if 'bash' in shell_env:
            shell = 'bash'
        elif 'zsh' in shell_env:
            shell = 'zsh'
        elif 'fish' in shell_env:
            shell = 'fish'
        elif 'tcsh' in shell_env:
            shell = 'tcsh'
        else:
            print("Error: Could not detect shell type. Please specify explicitly.", file=sys.stderr)
            print("Example: crucible completion bash", file=sys.stderr)
            sys.exit(1)

    print(f"Detected shell: {shell}")

    if args.print:
        # Print the completion script
        print_completion_script(shell)
    else:
        # Install the completion
        install_completion(shell)


def print_completion_script(shell):
    """Print the completion script for the given shell."""
    if shell == 'bash':
        print('eval "$(register-python-argcomplete crucible)"')
    elif shell == 'zsh':
        print('autoload -U bashcompinit')
        print('bashcompinit')
        print('eval "$(register-python-argcomplete crucible)"')
    elif shell == 'fish':
        print('# Fish completion requires argcomplete 2.0+')
        print('register-python-argcomplete --shell fish crucible | source')
    elif shell == 'tcsh':
        print('eval `register-python-argcomplete --shell tcsh crucible`')


def install_completion(shell):
    """Install completion for the given shell."""
    import subprocess

    print(f"\nInstalling completion for {shell}...")

    if shell == 'bash':
        rc_file = os.path.expanduser('~/.bashrc')
        completion_line = 'eval "$(register-python-argcomplete crucible)"'

        # Check if already installed
        if os.path.exists(rc_file):
            with open(rc_file, 'r') as f:
                if completion_line in f.read():
                    print(f"✓ Completion already installed in {rc_file}")
                    print("  Run 'source ~/.bashrc' or restart your terminal to activate.")
                    return

        # Add to bashrc
        with open(rc_file, 'a') as f:
            f.write(f'\n# Crucible CLI completion\n{completion_line}\n')

        print(f"✓ Added completion to {rc_file}")
        print("  Run 'source ~/.bashrc' or restart your terminal to activate.")

    elif shell == 'zsh':
        rc_file = os.path.expanduser('~/.zshrc')
        completion_lines = [
            'autoload -U bashcompinit',
            'bashcompinit',
            'eval "$(register-python-argcomplete crucible)"'
        ]

        # Check if already installed
        if os.path.exists(rc_file):
            with open(rc_file, 'r') as f:
                content = f.read()
                if 'register-python-argcomplete crucible' in content:
                    print(f"✓ Completion already installed in {rc_file}")
                    print("  Run 'source ~/.zshrc' or restart your terminal to activate.")
                    return

        # Add to zshrc
        with open(rc_file, 'a') as f:
            f.write('\n# Crucible CLI completion\n')
            for line in completion_lines:
                f.write(f'{line}\n')

        print(f"✓ Added completion to {rc_file}")
        print("  Run 'source ~/.zshrc' or restart your terminal to activate.")

    elif shell == 'fish':
        config_dir = os.path.expanduser('~/.config/fish/completions')
        os.makedirs(config_dir, exist_ok=True)
        completion_file = os.path.join(config_dir, 'crucible.fish')

        # Generate completion file
        try:
            result = subprocess.run(
                ['register-python-argcomplete', '--shell', 'fish', 'crucible'],
                capture_output=True,
                text=True,
                check=True
            )
            with open(completion_file, 'w') as f:
                f.write(result.stdout)
            print(f"✓ Created completion file: {completion_file}")
            print("  Restart your terminal to activate.")
        except subprocess.CalledProcessError as e:
            print(f"Error generating fish completion: {e}", file=sys.stderr)
            sys.exit(1)

    elif shell == 'tcsh':
        rc_file = os.path.expanduser('~/.tcshrc')
        completion_line = 'eval `register-python-argcomplete --shell tcsh crucible`'

        # Check if already installed
        if os.path.exists(rc_file):
            with open(rc_file, 'r') as f:
                if completion_line in f.read():
                    print(f"✓ Completion already installed in {rc_file}")
                    print("  Run 'source ~/.tcshrc' or restart your terminal to activate.")
                    return

        # Add to tcshrc
        with open(rc_file, 'a') as f:
            f.write(f'\n# Crucible CLI completion\n{completion_line}\n')

        print(f"✓ Added completion to {rc_file}")
        print("  Run 'source ~/.tcshrc' or restart your terminal to activate.")

    print("\n✓ Installation complete!")
