import json
from functools import lru_cache
from pathlib import Path

_REGISTRY_PATH = Path("data/project_registry.json")


@lru_cache
def load_registry() -> tuple[dict, ...]:
    if not _REGISTRY_PATH.exists():
        return ()
    return tuple(json.loads(_REGISTRY_PATH.read_text()))


def get_registry() -> list[dict]:
    return list(load_registry())


def classify_project(text: str) -> str | None:
    text_lower = text.lower()
    for project in load_registry():
        for alias in project.get("aliases", []):
            if alias.lower() in text_lower:
                return project["id"]
    return None
