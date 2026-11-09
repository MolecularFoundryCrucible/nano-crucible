"""`crucible login` and `crucible logout`: sign in with a browser instead of an API key."""

import logging
import sys

from . import term

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    parser = subparsers.add_parser(
        'login',
        help='Sign in to Crucible with a browser',
        description='Sign in with your Crucible account in a browser. On this computer the '
                    'browser opens by itself; over SSH or on a machine without a browser, '
                    'you approve a short code in a browser on any device.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible login
    crucible login --device        # approve a code on another device
    crucible login --no-open       # print the address instead of opening the browser
""",
    )
    method = parser.add_mutually_exclusive_group()
    method.add_argument('--device', dest='method', action='store_const', const='device',
                        help='Approve a code in a browser on any device (for SSH or headless machines)')
    method.add_argument('--browser', dest='method', action='store_const', const='browser',
                        help='Use a browser on this computer')
    parser.add_argument('--no-open', dest='open_browser', action='store_false', default=True,
                        help='Print the sign-in address instead of opening the browser')
    parser.set_defaults(func=execute_login, method='auto')

    logout = subparsers.add_parser(
        'logout',
        help='Sign out of Crucible on this computer',
        description='End the stored sign-in for the configured API and delete its tokens. '
                    'API keys are not affected.',
        formatter_class=term.ColorHelpFormatter,
    )
    logout.set_defaults(func=execute_logout)


def _notify(message, url):
    print(f"  {message}")
    print(f"  {term.cyan(url)}")
    print()


def _key_note(config):
    if config.source('api_key') == 'environment':
        return ("CRUCIBLE_API_KEY is set and takes precedence over the sign-in; "
                "unset it to use the sign-in.")
    return None


def execute_login(args):
    from crucible.config import config
    from ..auth.errors import SignInError
    from ..auth.session import save_sign_in, sign_in
    from ..auth.store import open_store
    from .helpers import show_warning
    try:
        api_url = config.api_url.rstrip('/')
        print(f"Signing in to {api_url}")
        tokens = sign_in(api_url, args.method, open_browser=args.open_browser, notify=_notify)
        store = open_store()
        save_sign_in(tokens, store)
    except KeyboardInterrupt:
        print()
        logger.error("Sign-in cancelled.")
        sys.exit(1)
    except (SignInError, ValueError) as exc:
        logger.error(str(exc))
        sys.exit(1)
    config.reload()
    config._client = None
    where = {'keyring': 'the OS keyring', 'file': store.path if hasattr(store, 'path') else 'a file'}.get(store.name)
    term.success(f"Signed in as {tokens.user_unique_id}; tokens are in {where}.", args)
    note = _key_note(config)
    if note:
        show_warning(note)


def execute_logout(args):
    from crucible.config import config
    from ..auth.session import sign_out
    from ..auth.store import signed_in, store_for
    from .helpers import show_warning
    api_url = config.api_url.rstrip('/')
    entry = signed_in(api_url)
    if entry is None:
        print(f"Not signed in to {api_url}.")
        return
    sign_out(api_url, store_for(entry))
    config._client = None
    term.success(f"Signed out of {api_url}.", args)
    if config._data.get('api_key'):
        show_warning("An API key is still configured, so commands keep working with it.")
