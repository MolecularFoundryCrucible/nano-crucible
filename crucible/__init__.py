"""
nano-crucible: National Archive for NSRC Observations - Crucible

Python client library for the Crucible API - the Molecular Foundry data lakehouse.
"""

__version__ = "2.0.0"
__author__ = "mkywall"

import logging
import sys

# Set up logging for the crucible package
# Add NullHandler by default (standard practice for libraries)
# This prevents "No handler found" warnings if user doesn't configure logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.INFO)


def setup_logging(verbose=False):
    """
    Configure logging for crucible package.

    This is a convenience function for users who want to quickly enable
    crucible logging output. For more control, users should configure
    logging directly using the standard logging module.

    Args:
        verbose (bool): If True, set level to DEBUG; otherwise INFO

    Example:
        >>> import crucible
        >>> crucible.setup_logging()  # Enable INFO level logging
        >>> crucible.setup_logging(verbose=True)  # Enable DEBUG level
    """
    crucible_logger = logging.getLogger('crucible')

    # Remove existing handlers
    crucible_logger.handlers = []

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Set format with timestamp and logger name
    formatter = logging.Formatter(
        '%(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    crucible_logger.addHandler(console_handler)
    crucible_logger.setLevel(logging.DEBUG if verbose else logging.INFO)


from .client import CrucibleClient
from .models import BaseDataset, Project
from . import config

__all__ = ['CrucibleClient', 'BaseDataset', 'Project', 'config', 'setup_logging', '__version__', '__author__']
