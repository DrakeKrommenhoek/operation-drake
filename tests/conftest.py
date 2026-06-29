import os
from pathlib import Path

# Ensure the working directory is always the project root so file-based
# configs (data/project_registry.json, prompts/*.md) resolve correctly.
_PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(_PROJECT_ROOT)
