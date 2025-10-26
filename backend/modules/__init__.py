from __future__ import annotations
from importlib import import_module
from typing import Any, Dict, List


def get_router_for(slug: str):
    """Return an APIRouter for given module slug.
    Currently supports 'nationalities'. Extend by adding new modules package.
    """
    if slug == "nationalities":
        # Local import to avoid importing heavy dependencies at package import time
        from .nationalities.router import router as nationalities_router
        return nationalities_router
    raise ValueError(f"Unknown module slug: {slug}")


def list_modules(order: List[str], meta: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return ordered list of module metadata for UI entry screen."""
    items: List[Dict[str, Any]] = []
    for slug in order:
        m = dict(meta.get(slug, {}))
        m.setdefault("slug", slug)
        items.append(m)
    return items
