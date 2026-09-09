# CLI Known Limitations

## Compatibility aliases

The CLI uses conventional long options and one-letter aliases in new documentation:

| Canonical option | Short alias | Deprecated compatibility aliases |
|---|---|---|
| `--project-id` | `-p` | `-pid`; `--project` on dataset and sample search |
| `--project-id` for project creation | `-i` | `-id` |
| `--type` for sample creation | `-t` | `--sample-type` |

Deprecated aliases remain accepted with a warning so existing scripts continue to work. Remove them only through the package's normal compatibility process.

Short options may have different meanings under unrelated subcommands. This is normal argparse scoping and is not considered a conflict.

## JSON output

Machine-readable output is not yet available for every command. Relationship and membership listings, ingestion records, ACL models, deletion workflows, signed file links, local status, and mutation responses need an explicit output contract before receiving `--json`. See `DISPLAY_GUIDE.md` for the implementation rules.
