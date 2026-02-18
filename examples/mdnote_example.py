#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example usage of the MDNoteParser

This demonstrates how to parse and upload a markdown note with linked images.
"""

from pycrucible.parsers import MDNoteParser

# Example 1: Basic parsing
# Parse a markdown file (will automatically find linked images)
parser = MDNoteParser('path/to/your/note.md', project_id='your-project-id')

# The parser automatically:
# - Adds an mfid to the YAML frontmatter if missing
# - Extracts the first H1 heading as the title
# - Finds all locally referenced images
# - Collects metadata about the document structure

# View the extracted metadata
print("Scientific Metadata:", parser.scientific_metadata)
print("Keywords:", parser.keywords)
print("Title:", parser.title)
print("MFID:", parser.mfid)
print("Files to upload:", parser.files_to_upload)
print("Linked datasets:", parser.linked_datasets)
print("Linked samples:", parser.linked_samples)

# Example 2: Upload to Crucible
# Upload the markdown note and all linked images
result = parser.upload_dataset(
    owner_orcid='0000-0000-0000-0000',  # Your ORCID
    verbose=True
)

print("Upload complete!")
print("Created record:", result['created_record'])
print("\nLinked datasets:", result.get('linked_datasets', []))
print("Linked samples:", result.get('linked_samples', []))

# Example 3: Use with get_parser registry
from pycrucible.parsers import get_parser

ParserClass = get_parser('mdnote')  # or 'markdown', 'note', 'MDNote'
parser = ParserClass('path/to/note.md', project_id='project-id')
parser.upload_dataset(owner_orcid='0000-0000-0000-0000')

# Example 4: Convert to dataset without uploading
dataset = parser.to_dataset(
    owner_orcid='0000-0000-0000-0000',
    dataset_name='My Custom Note Name'  # Optional, uses title if not provided
)
print("Dataset:", dataset)
