"""Offline localization public API; heavy model imports stay lazy."""
from .translate import LocalizeResult, localize_lesson

__all__ = ["LocalizeResult", "localize_lesson"]
