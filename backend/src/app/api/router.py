from fastapi import APIRouter

from app.api.routes import findings, health, runs, saved_tests, setup

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(setup.router)
api_router.include_router(runs.router)
api_router.include_router(findings.router)
api_router.include_router(saved_tests.router)
