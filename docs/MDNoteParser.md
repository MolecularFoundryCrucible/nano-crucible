# MDNoteParser Documentation

The `MDNoteParser` is designed to parse markdown notes and their associated linked images for upload to Crucible.

## Features

1. **Automatic MFID Management**: Parses YAML frontmatter and adds a unique `mfid` identifier if one doesn't exist
2. **Metadata Extraction**: Extracts document structure including:
   - First H1 heading as the dataset title
   - All headings for document structure
   - YAML frontmatter fields
3. **Image Collection**: Finds and collects all locally referenced images (both markdown and HTML syntax)
4. **File Updates**: Updates the markdown file with the mfid in YAML frontmatter
5. **Keyword Management**: Automatically adds keywords from frontmatter tags

## Usage

### Basic Example

```python
from pycrucible.parsers import MDNoteParser

# Parse a markdown file
parser = MDNoteParser('path/to/note.md', project_id='your-project-id')

# Upload to Crucible
result = parser.upload_dataset(owner_orcid='0000-0000-0000-0000')
```

### Using the Parser Registry

```python
from pycrucible.parsers import get_parser

# Get the parser class
ParserClass = get_parser('mdnote')  # or 'markdown', 'note', 'MDNote'
parser = ParserClass('note.md', project_id='project-123')
```

## Input Format

### Markdown File Structure

The parser expects a markdown file with optional YAML frontmatter:

```markdown
---
author: Your Name
date: 2026-02-17
tags: tag1, tag2, tag3
mfid: optional-existing-mfid
---

# Main Title

Content here...

![Image](./images/figure.png)
```

### YAML Frontmatter Fields

- `mfid` (optional): Unique identifier - will be auto-generated if missing
- `tags` (optional): Keywords for the dataset (can be comma-separated string or list)
- Any other custom fields are preserved and stored in scientific_metadata

## Image Linking

The parser supports multiple image reference formats:

### Markdown Syntax
```markdown
![Alt text](./images/figure.png)
![](relative/path/image.jpg)
```

### HTML Syntax
```html
<img src="./images/figure.png" alt="Figure" />
```

### Important Notes

- **Local images only**: URLs (http://, https://) are ignored
- **Relative paths**: Images are resolved relative to the markdown file location
- **Missing images**: A warning is printed if a referenced image is not found
- **Duplicates**: Duplicate image references are automatically deduplicated

## Extracted Metadata

The parser stores the following in `scientific_metadata`:

```python
{
    'mfid': 'mdnote-uuid',
    'markdown_file': 'note.md',
    'title': 'First H1 Heading',
    'headings': [
        {'level': 1, 'text': 'Main Title'},
        {'level': 2, 'text': 'Section'},
        ...
    ],
    'frontmatter': {...},  # All YAML frontmatter
    'num_images': 3,
    'image_files': ['image1.png', 'image2.jpg', ...]
}
```

## Upload Behavior

When uploading:
- The markdown file is uploaded as the primary file
- All linked images are uploaded as associated files
- The `measurement` type is automatically set to "MDNote"
- The dataset name defaults to the first H1 heading if not specified
- The mfid from frontmatter is used as the unique_id

## Dependencies

Optional (recommended):
- `PyYAML`: For robust YAML frontmatter parsing

If PyYAML is not installed, a simple fallback parser is used.

## Examples

See `examples/mdnote_example.py` for detailed usage examples.
See `examples/sample_note.md` for a sample markdown file format.
