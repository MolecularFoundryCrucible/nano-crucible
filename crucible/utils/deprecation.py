#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API lifecycle decorators — mark methods as deprecated or removed.
"""

import warnings
import functools


def _deprecated(new_api: str):
    """Decorator that emits a DeprecationWarning pointing to the new API."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"{func.__name__}() is deprecated; use {new_api} instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator


def _removed(reason: str):
    """Decorator that raises NotImplementedError for methods removed from the API."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            raise NotImplementedError(
                f"{func.__name__}() has been removed and is no longer available. {reason}"
            )
        return wrapper
    return decorator
