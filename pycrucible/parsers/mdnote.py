#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MDNote Parser for Crucible

Parses markdown notes and their associated linked images for upload to Crucible.
Extracts metadata from YAML frontmatter and document structure.
"""

from .base import BaseParser
import os
import re
from pathlib import Path
from typing import List, Dict, Optional
import mfid


def parse_yaml_frontmatter(content: str) -> tuple[Optional[Dict], str]:
    """
    Parse YAML frontmatter from markdown content.

    Args:
        content: The full markdown file content

    Returns:
        tuple: (frontmatter_dict or None, content_without_frontmatter)
    """
    # Check if content starts with YAML frontmatter (---\n...---\n)
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.match(frontmatter_pattern, content, re.DOTALL)

    if not match:
        return None, content

    yaml_content = match.group(1)
    content_without_frontmatter = content[match.end():]

    # Parse YAML
    try:
        import yaml
        frontmatter = yaml.safe_load(yaml_content)
        return frontmatter or {}, content_without_frontmatter
    except ImportError:
        # If PyYAML not available, do simple key:value parsing
        frontmatter = {}
        for line in yaml_content.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter[key.strip()] = value.strip()
        return frontmatter, content_without_frontmatter
    except Exception as e:
        print(f"Warning: Could not parse YAML frontmatter: {e}")
        return {}, content_without_frontmatter


def create_yaml_frontmatter(frontmatter: Dict) -> str:
    """
    Create YAML frontmatter string from dictionary.

    Args:
        frontmatter: Dictionary of frontmatter fields

    Returns:
        str: YAML frontmatter formatted string
    """
    try:
        import yaml
        yaml_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
        return f"---\n{yaml_str}---\n"
    except ImportError:
        # Simple fallback without PyYAML
        lines = ["---"]
        for key, value in frontmatter.items():
            lines.append(f"{key}: {value}")
        lines.append("---\n")
        return '\n'.join(lines)


def extract_headings(content: str) -> List[Dict[str, str]]:
    """
    Extract all markdown headings from content.

    Args:
        content: Markdown content (without frontmatter)

    Returns:
        List of dicts with 'level' and 'text' for each heading
    """
    headings = []
    heading_pattern = r'^(#{1,6})\s+(.+)$'

    for line in content.split('\n'):
        match = re.match(heading_pattern, line)
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            headings.append({'level': level, 'text': text})

    return headings


def find_linked_images(content: str, markdown_dir: Path) -> List[str]:
    """
    Find all locally referenced images in markdown content.

    Args:
        content: Markdown content
        markdown_dir: Directory containing the markdown file

    Returns:
        List of absolute paths to image files
    """
    image_files = []

    # Pattern for markdown images: ![alt text](path)
    md_image_pattern = r'!\[.*?\]\(([^)]+)\)'

    # Pattern for HTML images: <img src="path">
    html_image_pattern = r'<img[^>]+src=["\'](.*?)["\']'

    # Find all image references
    image_refs = []
    image_refs.extend(re.findall(md_image_pattern, content))
    image_refs.extend(re.findall(html_image_pattern, content))

    for img_ref in image_refs:
        # Skip URLs (http://, https://, etc.)
        if img_ref.startswith(('http://', 'https://', '//', 'data:')):
            continue

        # Resolve relative path
        img_path = markdown_dir / img_ref

        # Check if file exists
        if img_path.exists() and img_path.is_file():
            image_files.append(str(img_path.resolve()))
        else:
            print(f"Warning: Referenced image not found: {img_ref}")

    return list(set(image_files))  # Remove duplicates


class MDNoteParser(BaseParser):
    """
    Parser for markdown notes with associated images.

    Extracts metadata from YAML frontmatter and document structure,
    and collects all locally referenced images for upload.
    """

    _measurement = "MDNote"

    def __init__(self, markdown_file: str, project_id: Optional[str] = None):
        """
        Parse a markdown note file and find associated images.

        Args:
            markdown_file: Path to the markdown file
            project_id: Optional project ID for upload
        """
        # Resolve file path
        markdown_file = os.path.abspath(markdown_file)

        if not os.path.exists(markdown_file):
            raise FileNotFoundError(f"Markdown file not found: {markdown_file}")

        markdown_dir = Path(markdown_file).parent

        # Read the markdown file
        with open(markdown_file, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # Parse frontmatter
        frontmatter, content = parse_yaml_frontmatter(original_content)
        if frontmatter is None:
            frontmatter = {}

        # Check for mfid, generate if missing
        dataset_mfid = frontmatter.get('mfid')
        file_was_updated = False

        if not dataset_mfid:
            # Generate new mfid using mfid package
            dataset_mfid = mfid.mfid()[0]
            frontmatter['mfid'] = dataset_mfid
            file_was_updated = True

        # Store the mfid
        self.mfid = dataset_mfid

        # Extract headings
        headings = extract_headings(content)

        # Get first H1 heading as title
        title = None
        for heading in headings:
            if heading['level'] == 1:
                title = heading['text']
                break

        # Find linked images
        image_files = find_linked_images(content, markdown_dir)

        # Update file with mfid if it was added
        if file_was_updated:
            new_frontmatter_str = create_yaml_frontmatter(frontmatter)
            updated_content = new_frontmatter_str + content

            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            print(f"Updated {markdown_file} with mfid: {dataset_mfid}")

        # Build files to upload (markdown + images)
        files_to_upload = [markdown_file] + image_files

        # Initialize parent class
        super().__init__(files_to_upload=files_to_upload, project_id=project_id)

        # Build scientific metadata
        self.scientific_metadata = {
            'mfid': dataset_mfid,
            'markdown_file': os.path.basename(markdown_file),
            'title': title,
            'headings': headings,
            'frontmatter': frontmatter,
            'num_images': len(image_files),
            'image_files': [os.path.basename(img) for img in image_files]
        }

        # Set keywords
        self.keywords = ["markdown", "note", "MDNote"]

        # Add tags from frontmatter if available
        if 'tags' in frontmatter:
            tags = frontmatter['tags']
            if isinstance(tags, list):
                self.keywords.extend(tags)
            elif isinstance(tags, str):
                # Handle comma-separated or space-separated tags
                self.keywords.extend([t.strip() for t in re.split(r'[,\s]+', tags) if t.strip()])

        # Store title for later use
        self.title = title

    def to_dataset(self, mfid=None, measurement=None, project_id=None,
                   owner_orcid=None, dataset_name=None):
        """
        Convert parsed data to Crucible dataset.

        Uses the extracted title as dataset_name if not provided.
        Uses the parsed mfid if not provided.

        Note: measurement parameter is ignored; uses self._measurement instead.
        """
        # Use parsed mfid if not provided
        if mfid is None:
            mfid = self.mfid

        # Use extracted title if dataset_name not provided
        if dataset_name is None and self.title:
            dataset_name = self.title

        dst = super().to_dataset(
            mfid=mfid,
            measurement=self._measurement,
            project_id=project_id,
            owner_orcid=owner_orcid,
            dataset_name=dataset_name
        )

        return dst

    def upload_dataset(self, mfid=None, project_id=None, owner_orcid=None,
                       dataset_name=None, get_user_info_function=None,
                       ingestor='ApiUploadIngestor', verbose=False,
                       wait_for_ingestion_response=True):
        """
        Upload MDNote dataset to Crucible.

        Automatically sets measurement type to "MDNote".
        Uses parsed mfid and title if not provided.

        Args:
            mfid (str, optional): Unique dataset identifier. Uses parsed mfid if not provided.
            project_id (str, optional): Project ID. Uses self.project_id if not provided.
            owner_orcid (str, optional): Owner's ORCID ID
            dataset_name (str, optional): Human-readable dataset name. Uses title if not provided.
            get_user_info_function (callable, optional): Function to get user info if needed
            ingestor (str, optional): Ingestion class. Defaults to 'ApiUploadIngestor'
            verbose (bool, optional): Print detailed progress. Defaults to False.
            wait_for_ingestion_response (bool, optional): Wait for ingestion. Defaults to True.

        Returns:
            dict: Dictionary containing upload results
        """
        # Use parsed mfid if not provided
        if mfid is None:
            mfid = self.mfid

        # Use extracted title if dataset_name not provided
        if dataset_name is None and self.title:
            dataset_name = self.title

        return super().upload_dataset(
            mfid=mfid,
            measurement=self._measurement,
            project_id=project_id,
            owner_orcid=owner_orcid,
            dataset_name=dataset_name,
            get_user_info_function=get_user_info_function,
            ingestor=ingestor,
            verbose=verbose,
            wait_for_ingestion_response=wait_for_ingestion_response
        )
