# Crucible Parsers

This directory contains parsers for different dataset types that can be uploaded to Crucible. Parsers extract metadata from domain-specific file formats and prepare datasets for upload.

## Architecture

Parsers use the **Template Method Pattern**:

1. **BaseParser** handles all common initialization and dataset creation
2. Subclasses override the `parse()` method to implement domain-specific logic
3. The `parse()` method is automatically called during initialization

```python
BaseParser.__init__()
    ↓
    1. Set instance variables (mfid, project_id, etc.)
    2. Initialize metadata/keywords from user input
    3. Call self.parse() ← Subclasses override this
    ↓
SubclassParser.parse()
    ↓
    - Read domain-specific files
    - Extract metadata
    - Add keywords
    - Generate thumbnails
    - Update files list
```

## Creating a New Parser

### Step 1: Create Your Parser Class

Create a new file in `pycrucible/parsers/` (e.g., `xrd.py`):

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""XRD Parser for X-ray diffraction data."""

import os
import logging
from .base import BaseParser

logger = logging.getLogger(__name__)


class XRDParser(BaseParser):
    """Parser for X-ray diffraction (XRD) data files."""

    # Define parser defaults (optional)
    _measurement = "XRD"
    _data_format = "XRD"
    _instrument_name = None  # Or set a default instrument

    def parse(self):
        """
        Parse XRD data files and extract metadata.

        This method is automatically called during initialization.
        All instance variables (self.mfid, self.files_to_upload, etc.)
        are already set and can be accessed.
        """
        # 1. Validate input
        if not self.files_to_upload:
            raise ValueError("No input files provided")

        # 2. Get primary input file
        xrd_file = self.files_to_upload[0]
        logger.debug(f"Parsing XRD file: {xrd_file}")

        # 3. Parse file and extract metadata
        xrd_metadata = self._read_xrd_file(xrd_file)

        # 4. Add extracted metadata (merges with user-provided metadata)
        self.add_metadata(xrd_metadata)

        # 5. Add domain-specific keywords (merges with user-provided keywords)
        self.add_keywords(["XRD", "diffraction", "crystallography"])

        # 6. (Optional) Add related files to upload
        # config_file = xrd_file.replace('.xrd', '.cfg')
        # if os.path.exists(config_file):
        #     self.files_to_upload.append(config_file)

        # 7. (Optional) Generate thumbnail visualization
        # self.thumbnail = self._generate_plot(xrd_metadata)

    @staticmethod
    def _read_xrd_file(filepath):
        """Read XRD file and extract metadata."""
        metadata = {}

        # Your parsing logic here
        with open(filepath, 'r') as f:
            # Extract 2-theta range, peaks, etc.
            metadata['two_theta_start'] = 10.0
            metadata['two_theta_end'] = 90.0
            metadata['wavelength'] = 1.54  # Cu K-alpha
            # ... more extraction ...

        return metadata

    @staticmethod
    def _generate_plot(metadata):
        """Generate XRD pattern plot (optional)."""
        # Generate visualization and return file path
        # return '/path/to/plot.png'
        pass
```

### Step 2: Register Your Parser

Edit `pycrucible/parsers/__init__.py`:

```python
from .base import BaseParser
from .lammps import LAMMPSParser
from .xrd import XRDParser  # Add your import

# Add to registry (keys should be lowercase)
PARSER_REGISTRY = {
    'base': BaseParser,
    'lammps': LAMMPSParser,
    'xrd': XRDParser,  # Add your parser
}

__all__ = ['BaseParser', 'LAMMPSParser', 'XRDParser', 'PARSER_REGISTRY', 'get_parser']
```

### Step 3: Test Your Parser

```python
from pycrucible.parsers import XRDParser

# Create parser instance
parser = XRDParser(
    files_to_upload=['sample.xrd'],
    project_id='my-project',
    mfid='abc123',
    metadata={'sample_id': 'XRD-001'},  # User metadata
    keywords=['test']  # User keywords
)

# Parser automatically called parse() during __init__
# Check results
print(f"Metadata: {parser.scientific_metadata}")
print(f"Keywords: {parser.keywords}")
print(f"Files: {parser.files_to_upload}")

# Upload to Crucible
result = parser.upload_dataset(verbose=True)
```

## Available Instance Variables

Inside your `parse()` method, you have access to all instance variables:

**Dataset Properties:**
- `self.project_id` - Crucible project ID
- `self.mfid` - Unique dataset identifier
- `self.measurement` - Measurement type (defaults to `_measurement`)
- `self.dataset_name` - Human-readable dataset name
- `self.session_name` - Session name for grouping
- `self.public` - Whether dataset is public (bool)
- `self.instrument_name` - Instrument name
- `self.data_format` - Data format type
- `self.source_folder` - Directory where parser was called

**Data:**
- `self.files_to_upload` - List of file paths to upload (can be modified)
- `self.scientific_metadata` - Dict of metadata (user + extracted)
- `self.keywords` - List of keywords (user + extracted)
- `self.thumbnail` - Path to thumbnail image (set if generated)

**Utility:**
- `self._client` - CrucibleClient instance (lazy loaded)
- `self.client` - Property to access client

## Helper Methods

### `add_metadata(metadata_dict)`

Merge additional metadata into existing metadata. User-provided metadata takes precedence.

```python
def parse(self):
    extracted = {'temperature': 300, 'pressure': 1.0}
    self.add_metadata(extracted)
```

### `add_keywords(keywords_list)`

Add unique keywords to existing keywords. Duplicates are automatically filtered.

```python
def parse(self):
    self.add_keywords(['XRD', 'powder diffraction'])
    # Only adds keywords that aren't already present
```

## Best Practices

### 1. Use Static Methods for Parsing Logic

Keep parsing logic in static methods for clarity and testability:

```python
def parse(self):
    metadata = self._parse_header(self.files_to_upload[0])
    self.add_metadata(metadata)

@staticmethod
def _parse_header(filepath):
    """Parse file header and return metadata dict."""
    # Pure function - easier to test
    return {'key': 'value'}
```

### 2. Handle Errors Gracefully

```python
def parse(self):
    try:
        metadata = self._parse_file(self.files_to_upload[0])
    except Exception as e:
        logger.error(f"Failed to parse file: {e}")
        raise ValueError(f"Invalid file format: {e}")
```

### 3. Use Logging

```python
import logging
logger = logging.getLogger(__name__)

def parse(self):
    logger.debug(f"Parsing {len(self.files_to_upload)} files")
    logger.info(f"Extracted {len(metadata)} metadata fields")
```

### 4. Validate Input Files

```python
def parse(self):
    if not self.files_to_upload:
        raise ValueError("No input files provided")

    filepath = self.files_to_upload[0]
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
```

### 5. Set Meaningful Keywords

```python
def parse(self):
    # Add general keywords
    self.add_keywords(['domain', 'technique'])

    # Add data-specific keywords
    if 'material' in metadata:
        self.add_keywords([metadata['material']])
```

### 6. Generate Thumbnails When Useful

```python
def parse(self):
    # Only if visualization adds value
    if self._should_generate_thumbnail():
        self.thumbnail = self._create_visualization()

@staticmethod
def _create_visualization():
    """Generate thumbnail and return file path."""
    # Use cache directory
    from pycrucible.config import get_cache_dir
    cache_dir = get_cache_dir()
    thumbnail_dir = os.path.join(cache_dir, 'thumbnails_upload')
    os.makedirs(thumbnail_dir, exist_ok=True)

    # Generate plot
    filepath = os.path.join(thumbnail_dir, 'plot.png')
    # ... create plot ...
    return filepath
```

## Example: Simple CSV Parser

```python
import csv
from .base import BaseParser

class CSVParser(BaseParser):
    """Parser for CSV tabular data."""

    _measurement = "CSV"
    _data_format = "CSV"

    def parse(self):
        """Parse CSV and extract basic statistics."""
        csv_file = self.files_to_upload[0]

        # Read CSV
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # Extract metadata
        metadata = {
            'num_rows': len(rows),
            'num_columns': len(rows[0]) if rows else 0,
            'columns': list(rows[0].keys()) if rows else []
        }

        self.add_metadata(metadata)
        self.add_keywords(['CSV', 'tabular data'])
```

## CLI Integration

Once registered, your parser is automatically available in the CLI:

```bash
# Upload XRD data
crucible upload -i sample.xrd -t xrd -pid my-project -u

# Add user metadata/keywords
crucible upload -i sample.xrd -t xrd -pid my-project -u \
    --metadata '{"sample_id": "XRD-001"}' \
    --keywords "validated,published"

# Make it public
crucible upload -i sample.xrd -t xrd -pid my-project -u --public
```

## Available Parsers

- **BaseParser** (`base`) - Generic upload, no parsing
- **LAMMPSParser** (`lammps`) - LAMMPS molecular dynamics simulations

## References

- **BaseParser API**: See `base.py` for full API documentation
- **LAMMPS Example**: See `lammps.py` for a complete implementation
- **Upload CLI**: See `cli/upload.py` for CLI integration
