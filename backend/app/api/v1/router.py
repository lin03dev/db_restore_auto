from fastapi import APIRouter

from app.api.v1.endpoints import databases, health, jobs, status

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(status.router, tags=["status"])
api_router.include_router(databases.router, tags=["databases"])
api_router.include_router(jobs.router, tags=["jobs"])
