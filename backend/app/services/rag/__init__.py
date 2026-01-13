"""
RAG Services - сервисы для работы с базой знаний
"""
from app.services.rag.qdrant_helper import (
    get_qdrant_client,
    ensure_collection,
    generate_embedding,
    generate_embedding_async,
    index_qa_to_qdrant,
    index_qa_to_qdrant_async,
    index_document_chunks_to_qdrant,
    search_qdrant,
    parse_qa_message,
    COLLECTION_NAME,
    EMBEDDING_DIMENSION
)

__all__ = [
    'get_qdrant_client',
    'ensure_collection',
    'generate_embedding',
    'generate_embedding_async',
    'index_qa_to_qdrant',
    'index_qa_to_qdrant_async',
    'index_document_chunks_to_qdrant',
    'search_qdrant',
    'parse_qa_message',
    'COLLECTION_NAME',
    'EMBEDDING_DIMENSION'
]
