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


def find_crucible_links(content: str) -> Dict[str, List[str]]:
    """
    Find all Crucible dataset and sample references in markdown content.

    Supports two formats:
    1. Wiki-style: [[dataset:mfid-123]] or [[sample:sample-xyz|Display Text]]
    2. Standard markdown: [text](https://crucible.lbl.gov/dataset/mfid-123)

    Args:
        content: Markdown content

    Returns:
        Dict with 'datasets' and 'samples' lists containing referenced IDs
    """
    datasets = []
    samples = []

    # Pattern for wiki-style links: [[dataset:id]] or [[dataset:id|display text]]
    wiki_dataset_pattern = r'\[\[dataset:([^\]|]+)(?:\|[^\]]*)?\]\]'
    wiki_sample_pattern = r'\[\[sample:([^\]|]+)(?:\|[^\]]*)?\]\]'

    # Pattern for standard markdown links to Crucible URLs
    # Matches: [text](https://crucible.lbl.gov/dataset/mfid-123)
    # or: [text](crucible://dataset/mfid-123)
    md_link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'

    # Find wiki-style links
    datasets.extend(re.findall(wiki_dataset_pattern, content))
    samples.extend(re.findall(wiki_sample_pattern, content))

    # Find standard markdown links
    for display_text, url in re.findall(md_link_pattern, content):
        # Match URLs like: https://crucible.lbl.gov/dataset/mfid-123
        # or custom scheme: crucible://dataset/mfid-123
        if '/dataset/' in url or '://dataset/' in url:
            # Extract the dataset ID (everything after /dataset/)
            dataset_id = url.split('/dataset/')[-1].strip('/')
            if dataset_id:
                datasets.append(dataset_id)
        elif '/sample/' in url or '://sample/' in url:
            # Extract the sample ID (everything after /sample/)
            sample_id = url.split('/sample/')[-1].strip('/')
            if sample_id:
                samples.append(sample_id)

    # Remove duplicates while preserving order
    unique_datasets = []
    for d in datasets:
        if d not in unique_datasets:
            unique_datasets.append(d)

    unique_samples = []
    for s in samples:
        if s not in unique_samples:
            unique_samples.append(s)

    return {
        'datasets': unique_datasets,
        'samples': unique_samples
    }


class MDNoteParser(BaseParser):
    """
    Parser for markdown notes with associated images.

    Extracts metadata from YAML frontmatter and document structure,
    and collects all locally referenced images for upload.
    """

    _measurement = "MDNote"

    def parse(self):
        """
        Parse markdown file and extract metadata, images, and links.

        This method is called by BaseParser.__init__() after initialization.
        It extracts:
        - YAML frontmatter (generates mfid if missing)
        - Document title from first H1 heading
        - All headings for structure
        - Linked images
        - Crucible dataset and sample references
        """
        # Get the markdown file from files_to_upload
        if not self.files_to_upload:
            raise ValueError("No markdown file provided")

        markdown_file = self.files_to_upload[0]
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

        # Check for mfid in frontmatter, use parser's mfid if available
        dataset_mfid = frontmatter.get('mfid')
        file_was_updated = False

        if not dataset_mfid:
            # Use parser's mfid if set, otherwise generate new one
            if self.mfid:
                dataset_mfid = self.mfid
            else:
                dataset_mfid = mfid.mfid()[0]
                self.mfid = dataset_mfid

            frontmatter['mfid'] = dataset_mfid
            file_was_updated = True
        else:
            # Use mfid from frontmatter
            self.mfid = dataset_mfid

        # Extract headings
        headings = extract_headings(content)

        # Get first H1 heading as title (if dataset_name not already set)
        title = None
        for heading in headings:
            if heading['level'] == 1:
                title = heading['text']
                break

        if not self.dataset_name and title:
            self.dataset_name = title

        # Find linked images
        image_files = find_linked_images(content, markdown_dir)

        # Find Crucible links (datasets and samples)
        crucible_links = find_crucible_links(content)
        linked_datasets = crucible_links['datasets']
        linked_samples = crucible_links['samples']

        # Update file with mfid if it was added
        if file_was_updated:
            new_frontmatter_str = create_yaml_frontmatter(frontmatter)
            updated_content = new_frontmatter_str + content

            with open(markdown_file, 'w', encoding='utf-8') as f:
                f.write(updated_content)

            print(f"Updated {markdown_file} with mfid: {dataset_mfid}")

        # Update files to upload (markdown + images)
        self.files_to_upload = [markdown_file] + image_files

        # Store linked datasets and samples for upload
        self.linked_datasets = linked_datasets
        self.linked_samples = linked_samples

        # Add extracted metadata
        extracted_metadata = {
            'mfid': dataset_mfid,
            'markdown_file': os.path.basename(markdown_file),
            'title': title,
            'headings': headings,
            'frontmatter': frontmatter,
            'num_images': len(image_files),
            'image_files': [os.path.basename(img) for img in image_files],
            'linked_datasets': linked_datasets,
            'linked_samples': linked_samples
        }
        self.add_metadata(extracted_metadata)

        # Add keywords from parser and frontmatter tags
        self.add_keywords(["markdown", "note", "MDNote"])

        if 'tags' in frontmatter:
            tags = frontmatter['tags']
            if isinstance(tags, list):
                self.add_keywords(tags)
            elif isinstance(tags, str):
                # Handle comma-separated or space-separated tags
                tag_list = [t.strip() for t in re.split(r'[,\s]+', tags) if t.strip()]
                self.add_keywords(tag_list)

    def upload_dataset(self, ingestor='ApiUploadIngestor',
                       verbose=False, wait_for_ingestion_response=True):
        """
        Upload MDNote dataset to Crucible.

        Automatically links referenced datasets as children and samples to the dataset.

        Args:
            ingestor (str, optional): Ingestion class. Defaults to 'ApiUploadIngestor'
            verbose (bool, optional): Print detailed progress. Defaults to False.
            wait_for_ingestion_response (bool, optional): Wait for ingestion. Defaults to True.

        Returns:
            dict: Dictionary containing upload results, including linked_datasets and linked_samples info
        """
        # Upload the dataset using parent method
        result = super().upload_dataset(
            ingestor=ingestor,
            verbose=verbose,
            wait_for_ingestion_response=wait_for_ingestion_response
        )

        # Get the created dataset ID
        created_dataset_id = result.get('created_record', {}).get('unique_id')

        if not created_dataset_id:
            print("Warning: Could not determine created dataset ID, skipping link creation")
            return result

        # Link referenced datasets as children
        linked_dataset_results = []
        if hasattr(self, 'linked_datasets') and self.linked_datasets:
            if verbose:
                print(f"\n=== Linking {len(self.linked_datasets)} child datasets ===")

            for child_dataset_id in self.linked_datasets:
                try:
                    link_result = self.client.link_datasets(
                        parent_dataset_id=created_dataset_id,
                        child_dataset_id=child_dataset_id
                    )
                    linked_dataset_results.append({
                        'child_id': child_dataset_id,
                        'status': 'success',
                        'result': link_result
                    })
                    if verbose:
                        print(f"  ✓ Linked child dataset: {child_dataset_id}")
                except Exception as e:
                    linked_dataset_results.append({
                        'child_id': child_dataset_id,
                        'status': 'error',
                        'error': str(e)
                    })
                    print(f"  ✗ Failed to link dataset {child_dataset_id}: {e}")

        # Link referenced samples
        linked_sample_results = []
        if hasattr(self, 'linked_samples') and self.linked_samples:
            if verbose:
                print(f"\n=== Linking {len(self.linked_samples)} samples ===")

            for sample_id in self.linked_samples:
                try:
                    link_result = self.client.add_sample_to_dataset(
                        dataset_id=created_dataset_id,
                        sample_id=sample_id
                    )
                    linked_sample_results.append({
                        'sample_id': sample_id,
                        'status': 'success',
                        'result': link_result
                    })
                    if verbose:
                        print(f"  ✓ Linked sample: {sample_id}")
                except Exception as e:
                    linked_sample_results.append({
                        'sample_id': sample_id,
                        'status': 'error',
                        'error': str(e)
                    })
                    print(f"  ✗ Failed to link sample {sample_id}: {e}")

        # Add linking results to the return dict
        result['linked_datasets'] = linked_dataset_results
        result['linked_samples'] = linked_sample_results

        return result
