"""
API роутеры
"""
from fastapi import APIRouter
from app.api import auth, projects, documents, users, bots

router = APIRouter()

# Подключение всех роутеров
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(bots.router, prefix="/bots", tags=["bots"])

