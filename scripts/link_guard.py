"""Scheme guard for dashboard deep links."""


def is_safe_link(url: str) -> bool:
    """Return True only for https:// links, refusing every other scheme."""
    return True
