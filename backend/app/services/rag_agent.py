"""
AI агент для определения стратегии ответа на вопрос
Анализирует вопрос и решает, какую информацию использовать
"""
import logging
from typing import Dict, Any, Optional, List
from uuid import UUID

logger = logging.getLogger(__name__)


class RAGAgent:
    """AI агент для определения стратегии ответа"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    async def analyze_question(
        self,
        question: str,
        available_documents: List[Dict[str, Any]],
        has_chunks: bool = False,
        has_summaries: bool = False,
        has_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        Анализирует вопрос и определяет стратегию ответа
        
        Args:
            question: Вопрос пользователя
            available_documents: Список доступных документов с метаданными
            has_chunks: Есть ли чанки в Qdrant
            has_summaries: Есть ли summaries документов
            has_metadata: Есть ли метаданные документов
        
        Returns:
            Словарь с рекомендациями по стратегии ответа
        """
        # Формируем контекст о доступных ресурсах
        resources_info = []
        if has_chunks:
            resources_info.append("Есть проиндексированные чанки документов в векторной БД")
        if has_summaries:
            resources_info.append("Есть краткие содержания (summaries) документов")
        if has_metadata:
            resources_info.append("Есть метаданные документов (названия, ключевые слова)")
        
        if not resources_info:
            resources_info.append("Документы еще обрабатываются, доступны только метаданные")
        
        # Список доступных документов
        documents_list = []
        for doc in available_documents[:10]:  # Максимум 10 документов
            doc_info = f"- {doc.get('filename', 'Неизвестный файл')} ({doc.get('file_type', 'unknown')})"
            keywords = doc.get('keywords', [])
            if keywords:
                doc_info += f" [ключевые слова: {', '.join(keywords[:5])}]"
            documents_list.append(doc_info)
        
        # Промпт для анализа вопроса
        analysis_prompt = f"""Ты - AI агент, который анализирует вопросы пользователей и определяет стратегию ответа.

Вопрос пользователя: {question}

Доступные ресурсы:
{chr(10).join(resources_info)}

Доступные документы:
{chr(10).join(documents_list) if documents_list else "Нет документов"}

Проанализируй вопрос и определи:
1. Тип вопроса (содержание/обзор, конкретный вопрос, поиск информации, общий вопрос)
2. Какие ресурсы лучше использовать (чанки, summaries, метаданные, общие знания)
3. Ключевые слова/темы для поиска (если нужен поиск)
4. Рекомендации по ответу

Ответь в формате JSON:
{{
    "question_type": "содержание|конкретный_вопрос|поиск|общий",
    "use_chunks": true/false,
    "use_summaries": true/false,
    "use_metadata": true/false,
    "use_general_knowledge": true/false,
    "search_keywords": ["ключевое слово 1", "ключевое слово 2"],
    "recommendation": "краткое описание стратегии"
}}"""

        try:
            response = await self.llm_client.generate(
                prompt=analysis_prompt,
                system_prompt="Ты - эксперт по анализу вопросов. Отвечай только валидным JSON без дополнительного текста.",
                temperature=0.3,
                max_tokens=500
            )
            
            # Парсим JSON ответ
            import json
            import re
            
            # Извлекаем JSON из ответа (может быть обернут в markdown)
            json_text = response.content.strip()
            # Убираем markdown code blocks если есть
            json_text = re.sub(r'```json\s*', '', json_text)
            json_text = re.sub(r'```\s*', '', json_text)
            json_text = json_text.strip()
            
            # Пробуем найти JSON объект
            json_match = re.search(r'\{[^}]+\}', json_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            
            analysis = json.loads(json_text)
            
            logger.info(f"[RAG AGENT] Analysis result: {analysis}")
            return analysis
            
        except Exception as e:
            logger.warning(f"[RAG AGENT] Error analyzing question: {e}, using default strategy")
            # Fallback: определяем стратегию по ключевым словам в вопросе
            question_lower = question.lower()
            
            # Определяем тип вопроса
            if any(word in question_lower for word in ["содержание", "содержание", "обзор", "что в", "что есть", "список"]):
                question_type = "содержание"
                use_summaries = True
                use_metadata = True
            elif any(word in question_lower for word in ["как", "почему", "что такое", "объясни"]):
                question_type = "конкретный_вопрос"
                use_chunks = has_chunks
                use_summaries = True
            else:
                question_type = "поиск"
                use_chunks = has_chunks
                use_summaries = True
                use_metadata = True
            
            # Извлекаем ключевые слова из вопроса (простой способ)
            keywords = []
            # Убираем стоп-слова
            stop_words = {"что", "как", "почему", "где", "когда", "кто", "в", "на", "с", "по", "для", "о", "об", "документ", "документы"}
            words = re.findall(r'\b\w+\b', question_lower)
            keywords = [w for w in words if w not in stop_words and len(w) > 2][:5]
            
            return {
                "question_type": question_type,
                "use_chunks": use_chunks if has_chunks else False,
                "use_summaries": use_summaries,
                "use_metadata": use_metadata,
                "use_general_knowledge": True,
                "search_keywords": keywords,
                "recommendation": f"Использовать {question_type} стратегию"
            }
    
    async def get_answer_strategy(
        self,
        question: str,
        project_id: UUID,
        db
    ) -> Dict[str, Any]:
        """
        Получает стратегию ответа на основе анализа вопроса и доступных ресурсов
        
        Args:
            question: Вопрос пользователя
            project_id: ID проекта
            db: Сессия базы данных
        
        Returns:
            Словарь со стратегией и рекомендациями
        """
        # Проверяем доступные ресурсы
        from app.vector_db.vector_store import VectorStore
        from app.services.document_metadata_service import DocumentMetadataService
        from app.models.document import Document
        from sqlalchemy import select, text
        
        vector_store = VectorStore()
        collection_name = f"project_{project_id}"
        has_chunks = await vector_store.collection_exists(collection_name)
        
        # Получаем документы проекта
        try:
            result = await db.execute(
                select(Document.id, Document.filename, Document.file_type, Document.created_at)
                .where(Document.project_id == project_id)
                .limit(20)
            )
            rows = result.all()
        except Exception:
            result = await db.execute(
                text("SELECT id, filename, file_type, created_at FROM documents WHERE project_id = :project_id LIMIT 20"),
                {"project_id": str(project_id)}
            )
            rows = result.all()
        
        # Получаем метаданные документов
        metadata_service = DocumentMetadataService()
        documents_metadata = []
        for row in rows:
            doc_id = row[0]
            filename = row[1] or "Неизвестный файл"
            file_type = row[2] or "unknown"
            created_at = row[3]
            
            metadata = metadata_service.extract_metadata_from_filename(filename)
            metadata["id"] = doc_id
            metadata["file_type"] = file_type
            metadata["created_at"] = created_at
            documents_metadata.append(metadata)
        
        # Проверяем наличие summaries
        has_summaries = False
        try:
            for doc_meta in documents_metadata[:5]:
                doc_id = doc_meta["id"]
                result = await db.execute(
                    text("SELECT summary FROM documents WHERE id = :doc_id"),
                    {"doc_id": str(doc_id)}
                )
                row = result.first()
                if row and row[0] and row[0].strip():
                    has_summaries = True
                    break
        except Exception:
            pass
        
        # Анализируем вопрос
        analysis = await self.analyze_question(
            question=question,
            available_documents=documents_metadata,
            has_chunks=has_chunks,
            has_summaries=has_summaries,
            has_metadata=len(documents_metadata) > 0
        )
        
        return {
            "strategy": analysis,
            "documents_metadata": documents_metadata,
            "has_chunks": has_chunks,
            "has_summaries": has_summaries
        }

