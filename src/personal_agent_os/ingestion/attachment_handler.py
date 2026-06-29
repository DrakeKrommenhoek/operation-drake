from pathlib import Path

from personal_agent_os.observability.logging import get_logger

logger = get_logger(__name__)


def save_attachment(data: bytes, filename: str, inbox_dir: str) -> str:
    path = Path(inbox_dir) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    logger.info({"action": "attachment_saved", "path": str(path)})
    return str(path)
