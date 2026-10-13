from typing import Dict, Any


def sort_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sort a dictionary by its keys."""
    return {
        k: (
            sort_dict(v)
            if isinstance(v, dict)
            else sorted(v) if isinstance(v, list) else v
        )
        for k, v in sorted(d.items())
    }
