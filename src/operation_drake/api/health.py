from fastapi import APIRouter

from operation_drake.storage.database import check_db

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
