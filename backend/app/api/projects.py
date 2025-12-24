"""
Роутер для управления проектами
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
from app.services.project_service import ProjectService
from app.api.dependencies import get_current_admin

router = APIRouter()


@router.get("", response_model=List[ProjectListResponse])
async def get_projects(
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить список всех проектов (оптимизировано - лимит 50, без больших полей)"""
    import gc
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        service = ProjectService(db)
        projects = await service.get_all_projects()
        
        # Преобразуем в упрощенную схему без больших полей
        # Это критично для предотвращения out of memory
        simplified_projects = []
        for project in projects:
            simplified_projects.append({
                "id": project.id,
                "name": project.name,
                "description": project.description[:200] + "..." if project.description and len(project.description) > 200 else project.description,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
            })
        
        # Освобождаем память
        del projects
        gc.collect()
        
        logger.info(f"Returning {len(simplified_projects)} projects (simplified)")
        return simplified_projects
    except Exception as e:
        logger.error(f"Error getting projects: {e}", exc_info=True)
        # Возвращаем пустой список вместо ошибки, чтобы не падал backend
        gc.collect()
        return []


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Создать новый проект"""
    service = ProjectService(db)
    project = await service.create_project(project_data)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить проект по ID"""
    service = ProjectService(db)
    project = await service.get_project_by_id(project_id)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Обновить проект"""
    service = ProjectService(db)
    project = await service.update_project(project_id, project_data)
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )
    
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Удалить проект"""
    service = ProjectService(db)
    success = await service.delete_project(project_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Проект не найден"
        )














