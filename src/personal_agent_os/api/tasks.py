from fastapi import APIRouter, HTTPException

from personal_agent_os.storage.database import get_session
from personal_agent_os.storage.repositories import ArtifactRepository, TaskRepository

router = APIRouter()


@router.get("/tasks")
def list_tasks(limit: int = 20) -> list[dict]:
    session = get_session()
    tasks = TaskRepository(session).list_recent(limit=limit)
    return [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "task_type": t.task_type,
            "project": t.project,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]


@router.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict:
    session = get_session()
    task = TaskRepository(session).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    artifacts = ArtifactRepository(session).get_by_task(task_id)
    return {
        "id": task.id,
        "title": task.title,
        "status": task.status,
        "task_type": task.task_type,
        "project": task.project,
        "approval_status": task.approval_status,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "artifacts": [
            {"id": a.id, "title": a.title, "file_path": a.file_path, "artifact_type": a.artifact_type}
            for a in artifacts
        ],
    }
