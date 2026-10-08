# nano-crucible

[![PyPI version](https://img.shields.io/pypi/v/nano-crucible.svg)](https://pypi.org/project/nano-crucible/)
[![Python versions](https://img.shields.io/pypi/pyversions/nano-crucible.svg)](https://pypi.org/project/nano-crucible/)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg?logo=github)](https://molecularfoundrycrucible.github.io/nano-crucible/)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-green.svg)](https://github.com/MolecularFoundryCrucible/nano-crucible/blob/main/LICENSE)

The official Python client library and command-line interface for [Crucible](https://crucible.lbl.gov), the Molecular Foundry's scientific data management platform for experimental and computational research.

Using the hosted service requires a Crucible account.

## Capabilities

- Create, search, update, and download scientific datasets through Python or the CLI
- Attach uploaded or externally stored files and manage ingestion requests
- Capture structured fields, flexible scientific metadata, and searchable keywords
- Track samples and parent-child provenance relationships
- Organize resources into projects and manage access

## Install

```bash
pip install nano-crucible
```

## Get started

Configure credentials and verify connectivity:

```bash
crucible config init
crucible status
```

The same configured credentials are available to the Python client:

```python
from crucible import CrucibleClient

client = CrucibleClient()
for dataset in client.datasets.list(limit=5):
    print(dataset["unique_id"], dataset.get("dataset_name"))
```

Continue with the [installation and configuration guide](https://molecularfoundrycrucible.github.io/nano-crucible/installation/) or the [quick start](https://molecularfoundrycrucible.github.io/nano-crucible/quickstart/).

## Documentation

- [Core concepts](https://molecularfoundrycrucible.github.io/nano-crucible/concepts/)
- [User guide](https://molecularfoundrycrucible.github.io/nano-crucible/user-guide/datasets/)
- [CLI overview and reference](https://molecularfoundrycrucible.github.io/nano-crucible/cli/)
- [Python API reference](https://molecularfoundrycrucible.github.io/nano-crucible/api-reference/client/)
- [Changelog and migration notes](https://molecularfoundrycrucible.github.io/nano-crucible/changelog/)

## Contributing

See the [contribution guide](https://github.com/MolecularFoundryCrucible/nano-crucible/blob/main/CONTRIBUTING.md) for development setup, testing, and documentation conventions.

## Support and license

Ask questions on [Discord](https://discord.gg/Wrepphsgbx) or [open a GitHub issue](https://github.com/MolecularFoundryCrucible/nano-crucible/issues). `nano-crucible` is distributed under the [BSD 3-Clause License](https://github.com/MolecularFoundryCrucible/nano-crucible/blob/main/LICENSE).

`nano-crucible` is developed and maintained by the [Data Group](https://foundry.lbl.gov/expertise-instrumentation/#data-and-analytics-expertise) at the Molecular Foundry, Lawrence Berkeley National Laboratory.
