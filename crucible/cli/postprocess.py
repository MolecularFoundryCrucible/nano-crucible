#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dataset postprocessing commands, registered under 'crucible dataset':
postprocess, pipelines, list-runs, and get-run.
"""

import json
import logging

from . import term
from .helpers import add_limit_arguments, count_label, print_more_hint, resolve_limit, page_kwargs
from ..constants import POSTPROCESSING_RUN_STATUSES

logger = logging.getLogger(__name__)


def register(subparsers):
    _register_postprocess(subparsers)
    _register_pipelines(subparsers)
    _register_list_runs(subparsers)
    _register_get_run(subparsers)


def _show_run(run):
    _p = term.field_printer(14)
    term.header("Postprocessing Run")
    _p("Run ID",    run.get('run_id'))
    _p("Dataset",   term.cyan(run.get('dataset_mfid') or '-'))
    _p("Pipeline",  run.get('pipeline'))
    _p("Status",    term.status_label(run.get('status')))
    if run.get('parameters'):
        _p("Parameters", json.dumps(run['parameters']))
    _p("Requested", term.fmt_ts(run.get('requested_at')))
    _p("Requester", term.user_id_link(run.get('requested_by')))
    if run.get('started_at'):
        _p("Started",   term.fmt_ts(run.get('started_at')))
    if run.get('finished_at'):
        _p("Finished",  term.fmt_ts(run.get('finished_at')))
    if run.get('error'):
        _p("Error",     term.red(run['error']))


def _parse_parameters(args):
    parameters = {}
    if args.params:
        parameters = json.loads(args.params)
        if not isinstance(parameters, dict):
            raise ValueError("--params must be a JSON object.")
    for item in args.param or []:
        key, sep, value = item.partition('=')
        if not sep or not key:
            raise ValueError(f"--param requires KEY=VALUE format, got: '{item}'")
        try:
            parameters[key] = json.loads(value)
        except json.JSONDecodeError:
            parameters[key] = value
    return parameters


# ── postprocess ───────────────────────────────────────────────────────────────

def _register_postprocess(subparsers):
    parser = subparsers.add_parser(
        'postprocess',
        help='Run a postprocessing pipeline on a dataset',
        description='Queue a postprocessing pipeline on a dataset. Requires contributor access. '
                    'List pipelines with "crucible dataset pipelines".',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset postprocess DATASET_MFID mosaic_stitch
    crucible dataset postprocess DATASET_MFID rga_analysis --param window=5
    crucible dataset postprocess DATASET_MFID rga_analysis --params '{"window": 5}'
    crucible dataset postprocess DATASET_MFID mosaic_stitch --idempotency-key batch-7

Each call starts a new run unless it repeats an --idempotency-key, which
returns the original run instead.
""",
    )
    parser.add_argument('dataset_mfid', metavar='DATASET_MFID', help='Dataset MFID')
    parser.add_argument('pipeline', metavar='PIPELINE', help='Pipeline name')
    parser.add_argument('--param', action='append', metavar='KEY=VALUE', default=None,
                        help='Pipeline parameter; VALUE is parsed as JSON when possible. Repeatable')
    parser.add_argument('--params', metavar='JSON', default=None,
                        help='Pipeline parameters as a JSON object')
    parser.add_argument('--idempotency-key', metavar='KEY', default=None,
                        help='Return the original run when this key was already used on this dataset')
    parser.set_defaults(func=_execute_postprocess)


def _execute_postprocess(args):
    from crucible.config import get_client
    try:
        parameters = _parse_parameters(args)
        client = get_client()
        run = client.datasets.postprocess(
            args.dataset_mfid, args.pipeline, parameters=parameters,
            idempotency_key=args.idempotency_key)
        term.success(f"Pipeline {args.pipeline} queued", args)
        print()
        _show_run(run)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


# ── pipelines ─────────────────────────────────────────────────────────────────

def _register_pipelines(subparsers):
    parser = subparsers.add_parser(
        'pipelines',
        help='List postprocessing pipelines',
        description='Show the pipelines that can postprocess a dataset and the parameters each accepts.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset pipelines

Run one with:
    crucible dataset postprocess DATASET_MFID PIPELINE
""",
    )
    parser.set_defaults(func=_execute_pipelines)


def _execute_pipelines(args):
    from crucible.config import get_client
    try:
        pipelines = get_client().postprocessing.pipelines()
        term.header(f"Postprocessing Pipelines ({len(pipelines)})")
        if not pipelines:
            print(f"  {term.dim('No pipelines found.')}")
            return
        rows = []
        for p in pipelines:
            props = (p.get('parameters_schema') or {}).get('properties') or {}
            rows.append((p.get('name') or '-', p.get('description') or '-',
                         ', '.join(props) or '-'))
        term.table(rows, ['Pipeline', 'Description', 'Parameters'],
                   max_widths=[24, 70, 30])
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


# ── list-runs ─────────────────────────────────────────────────────────────────

def _register_list_runs(subparsers):
    parser = subparsers.add_parser(
        'list-runs',
        help='List postprocessing runs',
        description='List postprocessing runs on datasets you can read, newest first.',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset list-runs
    crucible dataset list-runs DATASET_MFID
    crucible dataset list-runs --pipeline mosaic_stitch --status failed
""",
    )
    parser.add_argument('dataset_mfid', metavar='DATASET_MFID', nargs='?', default=None,
                        help='Only runs on this dataset')
    parser.add_argument('--pipeline', metavar='PIPELINE', default=None,
                        help='Only runs of this pipeline')
    parser.add_argument('--status', choices=list(POSTPROCESSING_RUN_STATUSES), default=None,
                        help='Filter by status')
    add_limit_arguments(parser, 'runs')
    parser.set_defaults(func=_execute_list_runs)


def _execute_list_runs(args):
    from crucible.config import get_client
    try:
        runs = get_client().postprocessing.list(
            dataset_mfid=args.dataset_mfid, pipeline=args.pipeline, status=args.status,
            limit=resolve_limit(args), **page_kwargs(args))
        term.header(f"Postprocessing Runs ({count_label(runs)})")
        if not runs:
            print(f"  {term.dim('No postprocessing runs found.')}")
            return
        rows = [
            (str(r.get('run_id', '-')), term.cyan(r.get('dataset_mfid') or '-'),
             r.get('pipeline') or '-', term.status_label(r.get('status') or '-'),
             term.fmt_date(r.get('requested_at')))
            for r in runs
        ]
        term.table(rows, ['ID', 'Dataset', 'Pipeline', 'Status', 'Requested'],
                   max_widths=[8, 26, 24, 10, 12])
        print_more_hint(runs, resolve_limit(args), args)
    except Exception as e:
        from .helpers import fail
        fail("", e, args)


# ── get-run ───────────────────────────────────────────────────────────────────

def _register_get_run(subparsers):
    parser = subparsers.add_parser(
        'get-run',
        help='Show a postprocessing run',
        formatter_class=term.ColorHelpFormatter,
        epilog="""
Examples:
    crucible dataset get-run 17
""",
    )
    parser.add_argument('run_id', type=int, metavar='RUN_ID', help='Postprocessing run ID')
    parser.set_defaults(func=_execute_get_run)


def _execute_get_run(args):
    from crucible.config import get_client
    try:
        _show_run(get_client().postprocessing.get(args.run_id))
    except Exception as e:
        from .helpers import fail
        fail("", e, args)
