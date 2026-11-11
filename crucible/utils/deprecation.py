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


def _deprecated_parameter(old_name: str, new_name: str):
    """Map a deprecated keyword to its replacement while preserving positional calls."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if old_name in kwargs:
                if new_name in kwargs:
                    raise TypeError(
                        f"Pass either '{new_name}' or deprecated '{old_name}', not both."
                    )
                warnings.warn(
                    f"The '{old_name}' keyword is deprecated; use '{new_name}' instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                kwargs[new_name] = kwargs.pop(old_name)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def removed_message(old: str, replacement: str, version: str = '4.0.0') -> str:
    return f"{old} was removed in nano-crucible {version}; {replacement}"


def _removed(replacement: str, version: str = '4.0.0'):
    """Decorator for a removed method: calling it raises RemovedError naming the replacement.

    replacement is a sentence fragment, such as "use client.account.profile() instead."
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from ..errors import RemovedError
            raise RemovedError(removed_message(f"{func.__qualname__}()", replacement, version))
        wrapper.__removed__ = replacement
        return wrapper
    return decorator


def _removed_parameter(old_name: str, new_name: str, version: str = '4.0.0'):
    """Decorator for a renamed keyword whose old name was removed: passing it raises
    RemovedError naming the new one."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if old_name in kwargs:
                from ..errors import RemovedError
                raise RemovedError(removed_message(
                    f"The '{old_name}' keyword of {func.__qualname__}()",
                    f"use '{new_name}' instead.", version))
            return func(*args, **kwargs)
        wrapper.__removed_parameters__ = getattr(func, '__removed_parameters__', ()) + ((old_name, new_name),)
        return wrapper
    return decorator
