from __future__ import annotations
from typing import Dict, Any, List

# Ordered list of module slugs to show on the entry screen
MODULES_ORDER: List[str] = [
    "nationalities",
]

# Metadata per module (title/description can be extended later)
MODULES_META: Dict[str, Dict[str, Any]] = {
    "nationalities": {
        "title": "Nationalities",
        "description": "Назови национальность по стране",
    }
}
