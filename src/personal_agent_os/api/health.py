from fastapi import APIRouter

from personal_agent_os.storage.database import check_db

router = APIRouter()


@router.get("/health")
def health() -> dict:
    db_ok = check_db()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "service": "operation-drake",
        "version": "0.1.0",
    }
