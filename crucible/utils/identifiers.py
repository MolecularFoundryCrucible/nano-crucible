"""Classification and response helpers for canonical resource identifiers."""

import re
from typing import Dict, Tuple


MFID_PATTERN = re.compile(r'^[0-9a-hjkmnp-tv-z]{26}$')
ORCID_PATTERN = re.compile(r'^\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$')
SLUG_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{2,24}$')
USERNAME_PATTERN = re.compile(r'^[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*$')


class IdentifierNotFoundError(LookupError):
    """Raised when an exact identifier lookup returns no resource."""


class IdentifierIntegrityError(RuntimeError):
    """Raised when an exact identifier lookup violates API uniqueness rules."""


def is_mfid(value: str) -> bool:
    """Return whether a value is an exact 26-character MFID."""
    return isinstance(value, str) and bool(MFID_PATTERN.fullmatch(value))


def is_orcid(value: str) -> bool:
    """Return whether a value has the canonical ORCID shape."""
    return isinstance(value, str) and bool(ORCID_PATTERN.fullmatch(value))


def validate_mfid(value: str) -> str:
    """Validate an exact canonical MFID."""
    if not is_mfid(value):
        raise ValueError("MFID must be exactly 26 lowercase Crockford Base32 characters.")
    return value


def is_slug(value: str) -> bool:
    """Return whether a value is a valid 3-to-25-character resource slug."""
    return isinstance(value, str) and bool(SLUG_PATTERN.fullmatch(value))


def validate_username(value: str) -> str:
    """Normalize and validate a username accepted by the API."""
    if not isinstance(value, str):
        raise ValueError("Username must be a string.")
    username = value.strip().lower()
    if not 3 <= len(username) <= 24 or not USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Username must be 3 to 24 characters, start with a letter, contain "
            "only lowercase letters, digits, underscores, or hyphens, and have "
            "no leading, trailing, or consecutive separators."
        )
    return username


def validate_slug(value: str, resource_name: str) -> str:
    """Validate a newly created or renamed project or instrument slug."""
    if not is_slug(value):
        raise ValueError(
            f"{resource_name}_id must be 3 to 25 characters, start with a letter "
            "or digit, and contain only letters, digits, underscores, or hyphens."
        )
    return value


def classify_slug_reference(value: str, resource_name: str) -> str:
    """Classify a project or instrument reference as ``mfid`` or lookup slug.

    Lookup accepts legacy slugs that predate the current write-time format.
    """
    if is_mfid(value):
        return 'mfid'
    if isinstance(value, str) and value:
        return 'slug'
    raise ValueError(
        f"Invalid {resource_name} reference. Pass a non-empty slug or a "
        "26-character MFID."
    )


def classify_user_reference(value: str) -> Tuple[str, str]:
    """Classify and normalize a user reference for canonical client dispatch."""
    if not isinstance(value, str) or not value:
        raise ValueError("User reference must be a non-empty string.")
    if '@' in value:
        return 'email', value.lower()
    if is_orcid(value) or is_mfid(value):
        return 'unique_id', value

    try:
        return 'username', validate_username(value)
    except ValueError as error:
        raise ValueError(
            "Invalid user reference. Pass an ORCID, user MFID, email, "
            "or a valid 3-to-24-character username."
        ) from error


def require_canonical_identifier(record: Dict, resource_name: str) -> Dict:
    """Require a resource response to carry its canonical ``unique_id``."""
    if not isinstance(record, dict) or not record.get('unique_id'):
        raise IdentifierIntegrityError(
            f"{resource_name.capitalize()} response is missing canonical unique_id."
        )
    return record


def collapse_exact_lookup(payload: Dict, resource_name: str, reference: str) -> Dict:
    """Collapse a paginated exact lookup while enforcing its uniqueness contract."""
    if not isinstance(payload, dict) or not isinstance(payload.get('items'), list):
        raise IdentifierIntegrityError(
            f"Exact {resource_name} lookup returned an invalid collection response."
        )

    items = payload['items']
    total = payload.get('total', len(items))
    if total == 0 and not items:
        raise IdentifierNotFoundError(f"{resource_name.capitalize()} not found: {reference}")
    if total != 1 or len(items) != 1:
        raise IdentifierIntegrityError(
            f"Exact {resource_name} lookup for '{reference}' returned {total} matches."
        )
    return require_canonical_identifier(items[0], resource_name)
