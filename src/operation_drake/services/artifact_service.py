import re
from pathlib import Path

from operation_drake.observability.logging import get_logger

logger = get_logger(__name__)


class ArtifactService:
    def __init__(self, artifacts_dir: str):
        self._base = Path(artifacts_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def save(self, title: str, content: str, task_id: str, artifact_type: str) -> str:
        safe_title = re.sub(r"[^\w\-]", "_", title)[:60]
        filename = f"{task_id[:8]}_{safe_title}.md"
        path = self._base / filename
        path.write_text(content, encoding="utf-8")
        logger.info(
            {
                "action": "artifact_saved",
                "path": str(path),
                "task_id": task_id,
                "type": artifact_type,
            }
        )
        return str(path)
