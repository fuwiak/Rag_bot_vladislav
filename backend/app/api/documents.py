"""
Роутер для управления документами
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService
from app.api.dependencies import get_current_admin

router = APIRouter()


@router.post("/{project_id}/upload", response_model=List[DocumentResponse], status_code=status.HTTP_201_CREATED)
async def upload_documents(
    project_id: UUID,
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Загрузить документы в проект"""
    service = DocumentService(db)
    
    documents = []
    for file in files:
        # Валидация формата файла
        if not file.filename.endswith(('.txt', '.docx', '.pdf')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый формат файла: {file.filename}"
            )
        
        document = await service.upload_document(project_id, file)
        documents.append(document)
    
    return documents


@router.get("/{project_id}", response_model=List[DocumentResponse])
async def get_project_documents(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Получить список документов проекта"""
    service = DocumentService(db)
    documents = await service.get_project_documents(project_id)
    return documents


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin = Depends(get_current_admin)
):
    """Удалить документ"""
    service = DocumentService(db)
    success = await service.delete_document(document_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Документ не найден"
        )

