from fastapi import APIRouter
from sqlalchemy import text

from app.db.neo4j_db import verify_neo4j_connection
from app.db.postgres import engine

router = APIRouter(tags=["health"])


def _postgres_status() -> str:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


@router.get("/health")
def health_check() -> dict[str, object]:
    postgres_status = _postgres_status()
    neo4j_status = "ok" if verify_neo4j_connection() else "error"
    overall_status = "ok" if postgres_status == "ok" and neo4j_status == "ok" else "degraded"

    return {
        "status": overall_status,
        "database": {
            "postgres": postgres_status,
            "neo4j": neo4j_status,
        },
    }
