#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cast subcommand - execute .crux recipe files to create Crucible entities.
"""

import logging
import sys
from . import term

logger = logging.getLogger(__name__)


def register_subcommand(subparsers):
    """Register the cast subcommand."""
    parser = subparsers.add_parser(
        'cast',
        help='Execute a .crux recipe file',
        description='Load a .crux file and create datasets, samples, and links in Crucible.',
        formatter_class=lambda prog: term.ColorHelpFormatter(prog, max_help_position=35),
        epilog="""
Examples:
    crucible cast experiment.crux                 # execute the recipe
    crucible cast experiment.crux --dry-run       # preview without making API calls
    crucible cast experiment.crux --validate      # check file validity only
    crucible cast experiment.crux --show          # print plan and lock status
    crucible cast experiment.crux --force         # clear lock and recreate everything
    crucible cast experiment.crux --reupload      # re-upload files to existing records
"""
    )

    parser.add_argument(
        'crux_file',
        metavar='FILE',
        help='Path to the .crux recipe file'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Preview what would happen without making any API calls'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        default=False,
        help='Validate the .crux file (check refs, cycles) without executing'
    )

    parser.add_argument(
        '--show',
        action='store_true',
        default=False,
        help='Print the plan and current lock status, then exit'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        default=False,
        help='Clear the lock and recreate all entities from scratch'
    )

    parser.add_argument(
        '--reupload',
        action='store_true',
        default=False,
        help='Re-upload files to existing dataset records without recreating them'
    )

    parser.set_defaults(func=_execute_cast)


def _execute_cast(args):
    from crucible.cast import load, CastExecutor

    # --validate: just load and report - suppress info logs for clean output
    if args.validate:
        import logging as _logging
        _cast_logger = _logging.getLogger('crucible.cast')
        _orig_level = _cast_logger.level
        _cast_logger.setLevel(_logging.WARNING)
        try:
            plan = load(args.crux_file)
            print(f"OK  {args.crux_file}  "
                  f"({len(plan.datasets)} dataset(s), {len(plan.samples)} sample(s), "
                  f"{len(plan.links)} link(s))")
        except Exception as e:
            print(f"ERROR  {args.crux_file}: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            _cast_logger.setLevel(_orig_level)
        return

    try:
        plan = load(args.crux_file)
    except Exception as e:
        logger.error(f"Failed to load {args.crux_file}: {e}")
        sys.exit(1)

    executor = CastExecutor(plan)

    # --show: print plan + lock status and exit
    if args.show:
        _show_plan(plan, executor)
        return

    # --force: wipe the lock entirely
    if args.force:
        executor.reset()

    # --reupload: clear file/ingestion tracking, keep server IDs
    if args.reupload:
        executor.reset_files()

    if args.dry_run:
        logger.info("Dry run - no API calls will be made")
        executor.apply(client=None, dry_run=True)
        return

    from crucible.config import get_client
    client = get_client()
    executor.apply(client, dry_run=False)


def _show_plan(plan, executor):
    from . import term

    crux_path = plan.lock_path.with_suffix('').resolve()
    print(f"\n{term.bold(str(crux_path))}")
    print(f"  {len(plan.datasets)} dataset(s)  "
          f"{len(plan.samples)} sample(s)  "
          f"{len(plan.links)} link(s)\n")

    # Datasets
    term.header("Datasets")
    for local_id, ds in plan.datasets.items():
        server_id = executor._server_id(local_id)
        uploaded  = executor._uploaded_files(local_id)
        ing_id    = executor._ingestion_id(local_id)
        n_files   = len(ds.files)

        if server_id:
            status = term.green("created")
            detail = f"{server_id}"
            if n_files:
                detail += f"  files: {len(uploaded)}/{n_files}"
            if ing_id is not None:
                detail += f"  ingestion: #{ing_id}"
        else:
            status = term.dim("pending")
            detail = f"{n_files} file(s)" if n_files else "no files"

        print(f"  [{status}]  {ds.name}  {term.dim(f'({local_id})')}")
        print(f"            {detail}")

    # Samples
    print()
    term.header("Samples")
    for local_id, smp in plan.samples.items():
        server_id = executor._server_id(local_id)
        if server_id:
            status = term.green("created")
            detail = server_id
        else:
            status = term.dim("pending")
            detail = ""
        print(f"  [{status}]  {smp.name}  {term.dim(f'({local_id})')}  {detail}")

    # Links
    print()
    term.header("Links")
    for link in plan.links:
        done = executor._is_linked(link)
        status = term.green("done") if done else term.dim("pending")
        print(f"  [{status}]  {link.kind}: {link.source} -> {link.target}")

    print()
