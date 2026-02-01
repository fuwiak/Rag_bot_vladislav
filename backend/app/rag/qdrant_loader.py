"""
Модуль для загрузки документов в Qdrant векторную БД.
Поддерживает чанкинг, индексацию без whitelist (общий RAG).
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from uuid import uuid4
import re

from app.vector_db.vector_store import VectorStore
from app.services.embedding_service import EmbeddingService
from app.documents.chunker import DocumentChunker

logger = logging.getLogger(__name__)

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logger.warning("rank-bm25 не установлен. BM25 поиск недоступен. Установите: pip install rank-bm25")


class QdrantLoader:
    """Класс для загрузки и управления документами в Qdrant"""
    
    def __init__(
        self,
        collection_name: str = "rag_docs",
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        self.collection_name = collection_name
        self.vector_store = VectorStore()
        self.embedding_service = EmbeddingService()
        # Используем правильные параметры chunking из рабочего скрипта: 1000 символов, перекрытие 200
        self.chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        
        # BM25 индекс (будет построен при необходимости)
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_documents: List[List[str]] = []  # Токенизированные документы для BM25
        self.bm25_doc_map: Dict[int, Dict[str, Any]] = {}  # Маппинг индекса BM25 к документам Qdrant
        
        # Флаг необходимости перестроения BM25 индекса
        self._bm25_needs_rebuild = True
        
        # Коллекция будет создана при первом использовании (ленивая инициализация)
    
    async def _ensure_collection(self) -> None:
        """Создает коллекцию если она не существует"""
        try:
            from app.core.config import settings
            vector_size = settings.EMBEDDING_DIMENSION
            await self.vector_store.ensure_collection(self.collection_name, vector_size)
        except Exception as e:
            logger.error(f"Error ensuring collection: {str(e)}")
            raise
    
    async def load_document(
        self,
        text: str,
        metadata: Dict[str, Any],
        project_id: Optional[str] = None
    ) -> int:
        """
        Загружает документ в Qdrant.
        
        Args:
            text: Текст документа
            metadata: Метаданные (должен содержать source_url)
            project_id: ID проекта (опционально)
        
        Returns:
            Количество загруженных чанков
        """
        # Убеждаемся, что коллекция существует
        await self._ensure_collection()
        
        source_url = metadata.get("source_url") or metadata.get("url", "")
        
        # Разбиваем на чанки
        chunks = self.chunker.chunk_text(text)
        logger.info(f"Split document into {len(chunks)} chunks")
        
        if not chunks:
            logger.warning("No chunks generated from document")
            return 0
        
        # Фильтруем слишком короткие чанки (минимум 50 символов, как в рабочем скрипте)
        chunks = [chunk for chunk in chunks if len(chunk.strip()) >= 50]
        if not chunks:
            logger.warning("All chunks filtered out (too short)")
            return 0
        
        logger.info(f"After filtering: {len(chunks)} chunks")
        
        # Создаем embeddings батчами (как в рабочем скрипте)
        from qdrant_client.models import PointStruct
        import hashlib
        
        # Генерируем эмбеддинги батчами для эффективности
        batch_size = 100  # Размер батча для эмбеддингов
        points = []
        chunks_count = 0
        
        for batch_start in range(0, len(chunks), batch_size):
            batch_chunks = chunks[batch_start:batch_start + batch_size]
            
            try:
                # Генерируем эмбеддинги для батча
                logger.info(f"Generating embeddings for batch {batch_start // batch_size + 1} ({len(batch_chunks)} chunks)")
                embeddings = await self.embedding_service.create_embeddings_batch(batch_chunks)
                
                # Создаем точки для батча
                for i, (chunk, embedding) in enumerate(zip(batch_chunks, embeddings)):
                    if embedding is None:
                        logger.warning(f"Failed to generate embedding for chunk {batch_start + i}")
                        continue
                    
                    # Генерируем уникальный ID (как в рабочем скрипте)
                    chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
                    point_id = abs(hash(f"{source_url}_{batch_start + i}_{chunk_hash}")) % (10 ** 10)
                    
                    # Подготавливаем метаданные
                    point_metadata = {
                        **metadata,
                        "chunk_index": batch_start + i,
                        "chunk_text": chunk,
                        "text": chunk,  # Дублируем для совместимости
                        "source_url": source_url,
                        "total_chunks": len(chunks)
                    }
                    
                    if project_id:
                        point_metadata["project_id"] = project_id
                    
                    points.append(
                        PointStruct(
                            id=point_id,
                            vector=embedding,
                            payload=point_metadata
                        )
                    )
                    chunks_count += 1
                
            except Exception as e:
                logger.error(f"Error generating embeddings for batch {batch_start // batch_size + 1}: {str(e)}")
                # Пробуем создать эмбеддинги по одному для этого батча
                for i, chunk in enumerate(batch_chunks):
                    try:
                        embedding = await self.embedding_service.create_embedding(chunk)
                        if embedding:
                            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
                            point_id = abs(hash(f"{source_url}_{batch_start + i}_{chunk_hash}")) % (10 ** 10)
                            
                            point_metadata = {
                                **metadata,
                                "chunk_index": batch_start + i,
                                "chunk_text": chunk,
                                "text": chunk,
                                "source_url": source_url,
                                "total_chunks": len(chunks)
                            }
                            
                            if project_id:
                                point_metadata["project_id"] = project_id
                            
                            points.append(
                                PointStruct(
                                    id=point_id,
                                    vector=embedding,
                                    payload=point_metadata
                                )
                            )
                            chunks_count += 1
                    except Exception as chunk_error:
                        logger.error(f"Error storing chunk {batch_start + i}: {str(chunk_error)}")
                        continue
        
        # Сохраняем все точки в Qdrant батчами
        if points:
            qdrant_batch_size = 100  # Размер батча для Qdrant
            for qdrant_batch_start in range(0, len(points), qdrant_batch_size):
                qdrant_batch = points[qdrant_batch_start:qdrant_batch_start + qdrant_batch_size]
                try:
                    # Получаем клиент Qdrant напрямую для batch upsert
                    from app.vector_db.qdrant_client import qdrant_client
                    client = qdrant_client.get_client()
                    
                    client.upsert(
                        collection_name=self.collection_name,
                        points=qdrant_batch
                    )
                    logger.info(f"Inserted batch of {len(qdrant_batch)} points into {self.collection_name}")
                except Exception as e:
                    logger.error(f"Error inserting batch into Qdrant: {str(e)}")
                    # Пробуем сохранить по одному
                    for point in qdrant_batch:
                        try:
                            await self.vector_store.store_vector(
                                collection_name=self.collection_name,
                                vector=point.vector,
                                payload=point.payload
                            )
                        except Exception as single_error:
                            logger.error(f"Error storing single point: {str(single_error)}")
                            continue
        
        logger.info(f"Inserted {chunks_count} chunks into {self.collection_name}")
        
        # Помечаем BM25 индекс для перестроения
        self._bm25_needs_rebuild = True
        
        return chunks_count
    
    async def load_from_file(
        self,
        file_path: str,
        source_url: str,
        metadata: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None
    ) -> int:
        """
        Загружает документ из файла.
        Поддерживает текстовые файлы и PDF.
        
        Args:
            file_path: Путь к файлу
            source_url: URL источника
            metadata: Дополнительные метаданные
            project_id: ID проекта
        
        Returns:
            Количество загруженных чанков
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Определяем тип файла по расширению
        file_ext = file_path.suffix.lower()
        
        if file_ext == '.pdf':
            # Читаем PDF файл
            try:
                import PyPDF2
            except ImportError:
                raise ImportError("PyPDF2 не установлен. Установите: pip install PyPDF2")
            
            text = ""
            try:
                with open(file_path, "rb") as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    for page_num, page in enumerate(pdf_reader.pages):
                        try:
                            page_text = page.extract_text()
                            if page_text:
                                text += f"\n\n--- Страница {page_num + 1} ---\n\n"
                                text += page_text
                        except Exception as e:
                            logger.warning(f"Ошибка при чтении страницы {page_num + 1}: {str(e)}")
                            continue
            except Exception as e:
                logger.error(f"Ошибка при чтении PDF файла: {str(e)}")
                raise
        elif file_ext in ['.xlsx', '.xls']:
            # Читаем Excel файл
            try:
                import pandas as pd
            except ImportError:
                raise ImportError("pandas не установлен. Установите: pip install pandas openpyxl")
            
            try:
                # Читаем все листы Excel
                excel_file = pd.ExcelFile(file_path)
                text_parts = []
                
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    df = df.fillna("")
                    
                    # Преобразуем DataFrame в текст
                    for idx, row in df.iterrows():
                        row_text = " | ".join([str(val) for val in row.values if str(val).strip()])
                        if row_text:
                            text_parts.append(f"Лист '{sheet_name}', строка {idx + 1}: {row_text}")
                
                text = "\n".join(text_parts)
            except Exception as e:
                logger.error(f"Ошибка при чтении Excel файла: {str(e)}")
                raise
        else:
            # Читаем текстовый файл
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text = f.read()
            except UnicodeDecodeError:
                # Пробуем другие кодировки
                for encoding in ['cp1251', 'latin-1', 'iso-8859-1']:
                    try:
                        with open(file_path, "r", encoding=encoding) as f:
                            text = f.read()
                            break
                    except (UnicodeDecodeError, LookupError):
                        continue
                else:
                    raise ValueError(f"Не удалось декодировать файл {file_path} с доступными кодировками")
        
        if not text.strip():
            logger.warning(f"Файл {file_path} пуст или не содержит текста")
            return 0
        
        doc_metadata = {
            "source_url": source_url,
            "file_name": file_path.name,
            "file_type": file_ext,
            **(metadata or {})
        }
        
        return await self.load_document(text, doc_metadata, project_id)
    
    def _tokenize(self, text: str) -> List[str]:
        """Токенизация текста для BM25 (русский + английский)"""
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        return words
    
    async def _build_bm25_index(self) -> None:
        """Строит BM25 индекс из всех документов в Qdrant"""
        if not BM25_AVAILABLE:
            return
        
        try:
            logger.info("Building BM25 index from Qdrant documents...")
            
            # Получаем клиент Qdrant напрямую
            from app.vector_db.qdrant_client import qdrant_client
            client = qdrant_client.get_client()
            
            scroll_result = client.scroll(
                collection_name=self.collection_name,
                limit=10000,
                with_payload=True,
                with_vectors=False
            )
            points = scroll_result[0]
            
            if not points:
                return
            
            self.bm25_documents = []
            self.bm25_doc_map = {}
            
            for idx, point in enumerate(points):
                text = point.payload.get("chunk_text", "") or point.payload.get("text", "")
                if not text:
                    continue
                tokens = self._tokenize(text)
                if tokens:
                    self.bm25_documents.append(tokens)
                    self.bm25_doc_map[idx] = {
                        "text": text,
                        "source_url": point.payload.get("source_url", ""),
                        "payload": point.payload
                    }
            
            if self.bm25_documents:
                self.bm25_index = BM25Okapi(self.bm25_documents)
                logger.info(f"BM25 index built with {len(self.bm25_documents)} documents")
                
        except Exception as e:
            logger.error(f"Error building BM25 index: {str(e)}")
            self.bm25_index = None
    
    async def _bm25_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Выполняет BM25 поиск"""
        if not BM25_AVAILABLE:
            return []
        
        if self._bm25_needs_rebuild or not self.bm25_index:
            await self._build_bm25_index()
            self._bm25_needs_rebuild = False
        
        if not self.bm25_index:
            return []
        
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        
        scores = self.bm25_index.get_scores(query_tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k * 2]
        
        documents = []
        for idx in top_indices:
            if scores[idx] <= 0:
                continue
            doc_data = self.bm25_doc_map.get(idx)
            if not doc_data:
                continue
            
            import math
            normalized_score = 1 / (1 + math.exp(-scores[idx] / 10)) if scores[idx] > 0 else 0
            
            doc = {
                "text": doc_data.get("text", ""),
                "source_url": doc_data.get("source_url", ""),
                "score": normalized_score,
                "bm25_raw_score": float(scores[idx]),
                "search_method": "bm25",
                **{k: v for k, v in doc_data.get("payload", {}).items() 
                   if k not in ["text", "source_url", "chunk_text"]}
            }
            documents.append(doc)
        
        return documents[:top_k]
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.7,
        search_strategy: str = "hybrid",
        dense_weight: float = 0.4,
        bm25_weight: float = 0.6,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Поиск с поддержкой BM25 и hybrid search.
        
        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            score_threshold: Минимальный score
            search_strategy: "dense", "bm25", или "hybrid"
            dense_weight: Вес для dense search (для hybrid)
            bm25_weight: Вес для BM25 search (для hybrid)
            project_id: ID проекта для фильтрации
        """
        # Убеждаемся, что коллекция существует
        await self._ensure_collection()
        
        if search_strategy == "bm25":
            return await self._bm25_search(query, top_k)
        
        # Dense search
        query_embedding = await self.embedding_service.create_embedding(query)
        
        dense_results = []
        try:
            similar_chunks = await self.vector_store.search_similar(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k * 2 if search_strategy == "hybrid" else top_k,
                score_threshold=score_threshold,
                project_id=project_id
            )
            
            for chunk in similar_chunks:
                if chunk.get("score", 0) < score_threshold:
                    continue
                
                payload = chunk.get("payload", {})
                doc = {
                    "text": payload.get("chunk_text", ""),
                    "source_url": payload.get("source_url", ""),
                    "score": chunk.get("score", 0),
                    "search_method": "dense",
                    **{k: v for k, v in payload.items() if k not in ["chunk_text", "source_url"]}
                }
                dense_results.append(doc)
                    
        except Exception as e:
            logger.error(f"Error in dense search: {str(e)}")
        
        if search_strategy == "dense":
            return dense_results[:top_k]
        
        if search_strategy == "hybrid":
            return await self._hybrid_search(query, dense_results, top_k, score_threshold, dense_weight, bm25_weight)
        
        return dense_results[:top_k]
    
    async def _hybrid_search(
        self, query: str, dense_results: List[Dict[str, Any]], top_k: int,
        score_threshold: float, dense_weight: float, bm25_weight: float
    ) -> List[Dict[str, Any]]:
        """Комбинирует результаты BM25 и Dense search"""
        bm25_results = await self._bm25_search(query, top_k * 2)
        
        if not bm25_results:
            return dense_results[:top_k]
        
        def normalize_scores(results):
            if not results:
                return []
            scores = [r["score"] for r in results]
            max_score, min_score = max(scores) if scores else 1.0, min(scores) if scores else 0.0
            score_range = max_score - min_score if max_score != min_score else 1.0
            for r in results:
                r["normalized_score"] = (r["score"] - min_score) / score_range if score_range > 0 else 0.5
            return results
        
        dense_norm = normalize_scores(dense_results.copy())
        bm25_norm = normalize_scores(bm25_results.copy())
        combined_scores = {}
        
        for doc in dense_norm:
            text_key = doc["text"][:200]
            combined_scores[text_key] = {**doc, "hybrid_score": doc["normalized_score"] * dense_weight, "dense_score": doc["normalized_score"], "bm25_score": 0.0}
        
        for doc in bm25_norm:
            text_key = doc["text"][:200]
            bm25_norm_score = doc["normalized_score"]
            if text_key in combined_scores:
                combined_scores[text_key]["hybrid_score"] += bm25_norm_score * bm25_weight
                combined_scores[text_key]["bm25_score"] = bm25_norm_score
            else:
                combined_scores[text_key] = {**doc, "hybrid_score": bm25_norm_score * bm25_weight, "dense_score": 0.0, "bm25_score": bm25_norm_score}
        
        combined_list = sorted(combined_scores.values(), key=lambda x: x["hybrid_score"], reverse=True)
        filtered = [doc for doc in combined_list if doc["hybrid_score"] >= score_threshold]
        
        for doc in filtered:
            doc["score"] = doc["hybrid_score"]
            doc["search_method"] = "hybrid"
        
        return filtered[:top_k]
    
    async def get_collection_info(self) -> Dict[str, Any]:
        """Возвращает информацию о коллекции"""
        try:
            from app.vector_db.qdrant_client import qdrant_client
            client = qdrant_client.get_client()
            info = client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": getattr(info, 'points_count', 0),
                "status": str(getattr(info, 'status', 'unknown'))
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {str(e)}")
            return {
                "name": self.collection_name,
                "points_count": 0,
                "status": "error"
            }

