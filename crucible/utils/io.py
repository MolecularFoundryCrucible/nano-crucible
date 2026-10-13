#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File I/O, hashing, time, and image utilities.
"""

import base64
import os
import pytz
import subprocess as sp
import hashlib
from datetime import datetime, timezone


def run_shell(cmd, checkflag=True, background=False):
    """Execute a shell command and return the result.

    SECURITY NOTE: Prefer passing cmd as a list rather than a string to avoid shell injection.

    Args:
        cmd (str or list): The shell command to execute.
                          - str: Executed via shell (DEPRECATED - security risk)
                          - list: Executed directly (RECOMMENDED - secure)
        checkflag (bool): Whether to check return code and raise exception on failure. Defaults to True.
        background (bool): Whether to run the command in background. Defaults to False.

    Returns:
        subprocess.Popen or subprocess.CompletedProcess: Popen object if background=True,
        CompletedProcess object otherwise

    Examples:
        # Secure (recommended):
        run_shell(['rclone', 'copy', file_path, 'remote:/path'])

        # Insecure (deprecated):
        run_shell(f"rclone copy '{file_path}' remote:/path")  # DO NOT USE
    """
    use_shell = isinstance(cmd, str)

    if background:
        return sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, shell=use_shell,
                        universal_newlines=True)
    return sp.run(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, shell=use_shell,
                  universal_newlines=True, check=checkflag)


def checkhash(file):
    """Calculate SHA256 hash of a file.

    Args:
        file (str): Path to the file to hash

    Returns:
        str: Hexadecimal SHA256 hash of the file
    """
    with open(file, "rb") as f:
        fdata = f.read()
        readable_hash = hashlib.sha256(fdata).hexdigest()
    return readable_hash


def get_tz_isoformat(timezone="America/Los_Angeles"):
    """Get current time in ISO format for a specific timezone.

    Args:
        timezone (str): Timezone name (default: "America/Los_Angeles")

    Returns:
        str: Current time in ISO format for the specified timezone
    """
    pst = pytz.timezone(timezone)
    curr_pct_time = datetime.now(pst).isoformat()
    return curr_pct_time


def hash_file(file_path: str, block_size: int = 32 * 1024 * 1024):
    """Compute SHA256 and CRC32C of a file in a single pass.

    Args:
        file_path: Path to the file.
        block_size: Read block size in bytes (default 32 MiB).

    Returns:
        Tuple[str, str]: (sha256_hex, crc32c_base64)
    """
    import google_crc32c
    sha = hashlib.sha256()
    crc = google_crc32c.Checksum()
    with open(file_path, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            sha.update(block)
            crc.update(block)
    return sha.hexdigest(), base64.b64encode(crc.digest()).decode()


def parse_timestamp(value: str) -> str:
    """Parse a human-readable date/time string and return an ISO 8601 string.

    Accepts flexible input:
      - Keywords:   "now", "today", "yesterday"
      - ISO dates:  "2024-01-15", "2024-01-15T10:30:00"
      - Common:     "2024-01-15 10:30", "Jan 15 2024", "15/01/2024"

    Args:
        value (str): Date/time string to parse.

    Returns:
        str: ISO 8601 formatted string (e.g. "2024-01-15T10:30:00").

    Raises:
        ValueError: If the string cannot be parsed as a date.
    """
    from dateutil import parser as _duparser
    from datetime import timedelta

    v = value.strip().lower()
    now = datetime.now(timezone.utc)

    if v in ("now", "today"):
        return now.replace(microsecond=0).isoformat()
    if v == "yesterday":
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    try:
        dt = _duparser.parse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.replace(microsecond=0).isoformat()
    except (ValueError, OverflowError):
        raise ValueError(
            f"Cannot parse timestamp: {value!r}\n"
            "Accepted formats: ISO date (2024-01-15), ISO datetime (2024-01-15T10:30:00),\n"
            "                  'today', 'now', 'yesterday', or most common date strings."
        )


def check_small_files(filelist):
    """Check whether all files in a list are under the HTTP upload size threshold (100 MB).

    Args:
        filelist (list): List of file paths to check

    Returns:
        bool: True if all files are small enough for HTTP upload, False otherwise
    """
    for f in filelist:
        if os.path.getsize(f) < 1e8:
            continue
        else:
            return False
    return True

def is_base64(s):
      try:
          base64.b64decode(s, validate=True)
          return True
      except Exception:
          return False

def data2thumbnail(image) -> str:
    """Convert an image object to a path to a PNG file.

    For file paths the input is returned as-is. For in-memory objects
    (PIL, matplotlib, numpy) the image is written to a temporary file.

    Args:
        image: Image source. Accepts:
            - str or os.PathLike: path to an existing image file
            - PIL.Image.Image: PIL image object
            - matplotlib.figure.Figure: matplotlib figure
            - numpy.ndarray: array of shape (H, W) or (H, W, C)

    Returns:
        str: Absolute path to a PNG file

    Raises:
        FileNotFoundError: If image is a path but the file does not exist
        TypeError: If image type is not supported
    """
    import tempfile
    import uuid

    # Case 1: file path — return as-is after validating existence
    if isinstance(image, (str, os.PathLike)):
        path = os.path.abspath(image)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Thumbnail image not found: {path}")
        return path

    # In-memory objects: write to a temp PNG file
    thumbnail_dir = os.path.join(tempfile.gettempdir(), 'crucible_thumbnails')
    os.makedirs(thumbnail_dir, exist_ok=True)
    thumbnail_path = os.path.join(thumbnail_dir, f'{uuid.uuid4().hex}.png')

    # Case 2: PIL Image
    try:
        from PIL import Image as PILImage
        if isinstance(image, PILImage.Image):
            image.save(thumbnail_path, format='PNG')
            return thumbnail_path
    except ImportError:
        pass

    # Case 3: matplotlib Figure
    try:
        from matplotlib.figure import Figure
        if isinstance(image, Figure):
            image.savefig(thumbnail_path, format='png', bbox_inches='tight', dpi=150)
            return thumbnail_path
    except ImportError:
        pass

    # Case 4: numpy array — convert via PIL
    try:
        import numpy as np
        if isinstance(image, np.ndarray):
            from PIL import Image as PILImage
            PILImage.fromarray(image).save(thumbnail_path, format='PNG')
            return thumbnail_path
    except ImportError:
        pass

    raise TypeError(
        f"Unsupported thumbnail type: {type(image)}. "
        f"Supported types: str, Path, PIL.Image, matplotlib.Figure, numpy.ndarray"
    )


def gcs_object_parts(file_record: dict):
    """Split a GCS record's storage_path into (bucket, dataset_mfid, object name).

    Works for any bucket. Returns None for records that are not on GCS, have
    no storage path yet, or whose path is not bucket/dataset/object.
    """
    if (file_record.get('storage_backend') or 'gcs') != 'gcs':
        return None
    parts = (file_record.get('storage_path') or '').split('/', 2)
    if len(parts) < 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def storage_display_name(file_record: dict, dataset_mfid: str = None) -> str:
    """Return the display filename for a file record.

    GCS records are named by their ``filename``, which carries any relative
    folders; the object path is a server detail that differs between upload
    flows. Legacy objects stored directly below the dataset folder keep their
    object path when it extends the filename with folders. Other records fall
    back to the basename of their storage path or filename.
    """
    filename = file_record.get('filename') or ''
    parts = gcs_object_parts(file_record)
    if parts is not None:
        _bucket, owner_dataset, object_name = parts
        dataset_mfid = dataset_mfid or file_record.get('dataset_mfid')
        legacy = owner_dataset == dataset_mfid and not object_name.startswith('_files/')
        if legacy and (not filename or object_name.endswith(filename)):
            return object_name
        return filename or object_name
    storage_path = file_record.get('storage_path') or ''
    if storage_path:
        return os.path.basename(storage_path)
    return os.path.basename(filename)


def safe_output_path(output_dir: str, name: str) -> str:
    """Join name onto output_dir, refusing names that would land outside it."""
    root = os.path.abspath(output_dir)
    target = os.path.abspath(os.path.join(root, name))
    if os.path.isabs(name) or os.path.commonpath([root, target]) != root:
        raise ValueError(f"Refusing to write '{name}' outside {root}.")
    return target