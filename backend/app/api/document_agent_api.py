"""
API endpoints для Document Agent Adapter
Позволяет обрабатывать файлы из папки /documents через веб-интерфейс
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.api.dependencies import get_current_admin
from app.services.document_agent_adapter import DocumentAgentAdapter
from app.models.project import Project
from sqlalchemy import select

router = APIRouter(prefix="/api/document-agent", tags=["document-agent"])


@router.post("/process-folder/{project_id}")
async def process_folder(
    project_id: UUID,
    use_fast_indexing: bool = True,
    max_concurrent: int = 3,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Обработать все файлы из папки проекта
    
    Args:
        project_id: ID проекта
        use_fast_indexing: Использовать быструю индексацию для больших PDF
        max_concurrent: Максимальное количество одновременных задач
    """
    # Проверяем, существует ли проект
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    adapter = DocumentAgentAdapter()
    
    # Запускаем обработку в фоне
    async def process_async():
        return await adapter.process_all_files_from_folder(
            project_id=project_id,
            use_fast_indexing=use_fast_indexing,
            max_concurrent=max_concurrent
        )
    
    # Запускаем в фоне
    background_tasks.add_task(process_async)
    
    return {
        "message": "Обработка файлов из папки запущена в фоне",
        "project_id": str(project_id),
        "use_fast_indexing": use_fast_indexing
    }


@router.get("/scan-folder/{project_id}")
async def scan_folder(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Сканировать папку проекта и показать найденные файлы
    """
    # Проверяем, существует ли проект
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    adapter = DocumentAgentAdapter()
    files = await adapter.scan_documents_folder(project_id=project_id)
    
    return {
        "project_id": str(project_id),
        "files_found": len(files),
        "files": files
    }


@router.get("/status/{project_id}")
async def get_status(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Получить статус обработки документов проекта
    """
    # Проверяем, существует ли проект
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    adapter = DocumentAgentAdapter()
    status = await adapter.get_processing_status(project_id=project_id)
    
    return status


@router.post("/process-file/{project_id}")
async def process_file(
    project_id: UUID,
    file_path: str,
    use_fast_indexing: bool = True,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """
    Обработать один файл из папки
    
    Args:
        project_id: ID проекта
        file_path: Путь к файлу относительно папки проекта
        use_fast_indexing: Использовать быструю индексацию
    """
    # Проверяем, существует ли проект
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    
    adapter = DocumentAgentAdapter()
    
    # Формируем полный путь к файлу
    from pathlib import Path
    project_folder = Path("media") / "documents" / str(project_id)
    full_path = project_folder / file_path
    
    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Файл не найден: {file_path}")
    
    result = await adapter.process_file_from_folder(
        file_path=str(full_path),
        project_id=project_id,
        use_fast_indexing=use_fast_indexing
    )
    
    return result
