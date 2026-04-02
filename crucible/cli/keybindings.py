#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Key bindings for the Crucible interactive shell.

Call register(kb, shell) once after creating a KeyBindings instance.
shell is a CrucibleShell instance; bindings access shell.client,
shell.state, and shell.completer directly.

Shortcuts:
    Ctrl+L    clear screen
    Alt+V     toggle verbose view for last fetched resource (no API call)
    Alt+G     toggle graph view for last fetched resource
    Alt+R     refresh projects, user info, and pending deletions
    Alt+P     interactive project picker
    Alt+O     open last fetched resource in Graph Explorer
"""

import logging

logger = logging.getLogger(__name__)


def register(kb, shell):
    """Register all interactive shell key bindings onto kb."""
    from prompt_toolkit.application import run_in_terminal
    from prompt_toolkit.filters    import completion_is_selected

    @kb.add('enter', filter=completion_is_selected)
    def _accept_completion(event):
        buff = event.app.current_buffer
        buff.apply_completion(buff.complete_state.current_completion)

    @kb.add('c-l')
    def _ctrl_l(event):
        event.app.renderer.clear()

    @kb.add('escape', 'v')
    def _alt_v(event):
        last = shell.state.get('last_resource')
        if not last:
            return
        last['verbose'] = not last['verbose']
        run_in_terminal(lambda: shell._render_resource(last))

    @kb.add('escape', 'g')
    def _alt_g(event):
        last = shell.state.get('last_resource')
        if not last:
            return
        last['graph'] = not last.get('graph', False)
        run_in_terminal(lambda: shell._render_resource(last))

    @kb.add('escape', 'r')
    def _alt_r(event):
        run_in_terminal(shell.refresh)

    @kb.add('escape', 'p')
    def _alt_p(event):
        projects = shell.state.get('projects') or []
        if not projects:
            return
        current = shell.state.get('project', '')

        def _pick():
            print()
            for i, (pid, title) in enumerate(projects, 1):
                marker = ' ◀' if pid == current else ''
                print(f"  {i:2}.  {pid}  {title}{marker}")
            print()
            try:
                raw = input(f"  Project [1-{len(projects)}, Enter to cancel]: ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                return
            if not raw:
                return
            try:
                idx = int(raw) - 1
            except ValueError:
                print("  Invalid choice.")
                return
            if not (0 <= idx < len(projects)):
                print("  Invalid choice.")
                return
            pid, title = projects[idx]
            try:
                from crucible.cli.config import set_config_value
                set_config_value('current_project', pid)
                set_config_value('current_session', '')
                shell.state['project'] = pid
                shell.state['session'] = ''
                print(f"  Switched to: {title}  ({pid})")
            except Exception as e:
                logger.error(f"Error switching project: {e}")

        run_in_terminal(_pick)

    @kb.add('escape', 'o')
    def _alt_o(event):
        last = shell.state.get('last_resource')
        if not last:
            return
        uid = last['data'].get('unique_id') or last['data'].get('sample_id')
        if not uid:
            return

        def _open():
            try:
                import webbrowser
                from crucible.config import config as _cfg
                dtype = 'sample-graph' if last['type'] == 'sample' else 'dataset'
                pid   = last['data'].get('project_id', '')
                url   = f"{_cfg.graph_explorer_url.rstrip('/')}/{pid}/{dtype}/{uid}"
                webbrowser.open(url)
            except Exception as e:
                logger.error(f"Could not open resource: {e}")

        run_in_terminal(_open)
