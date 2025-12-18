"""
Модели базы данных (SQLAlchemy)

Ważne: Importuj modele w odpowiedniej kolejności (najpierw bez zależności):
1. AdminUser (bez zależności)
2. Project (bez zależności)
3. User (zależy od Project)
4. Document (zależy od Project)
5. DocumentChunk (zależy od Document)
6. Message (zależy od User)
"""
# Importujemy w odpowiedniej kolejności, aby uniknąć problemów z foreign keys
from app.models.admin_user import AdminUser
from app.models.project import Project
from app.models.user import User
from app.models.document import Document, DocumentChunk
from app.models.message import Message
from app.models.llm_model import LLMModel, GlobalModelSettings

__all__ = ["AdminUser", "Project", "User", "Document", "DocumentChunk", "Message", "LLMModel", "GlobalModelSettings"]

