# CLI Known Limitations

## Compatibility aliases

The CLI uses conventional long options and one-letter aliases in new documentation:

| Canonical option | Short alias | Removed aliases |
|---|---|---|
| `--project-id` | `-p` | `-pid`; `--project` on dataset and sample search |
| `--project-id` for project creation | `-i` | `-id` |
| `--type` for sample creation | `-t` | `--sample-type` |

The removed aliases were dropped in 4.0.0. Using one stops the command with an error naming the option to use instead (`RemovedOptionAction` in `helpers.py`).

Short options may have different meanings under unrelated subcommands. This is normal argparse scoping and is not considered a conflict.

## JSON output

Machine-readable output is not yet available for every command. Relationship and membership listings, ingestion records, ACL models, deletion workflows, signed file links, local status, and mutation responses need an explicit output contract before receiving `--json`. See `DISPLAY_GUIDE.md` for the implementation rules.
