"""
Простой тест RAG системы
"""
import asyncio
import logging
from app.rag.rag_chain import RAGChain

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_rag():
    """Тест RAG цепочки"""
    logger.info("=" * 50)
    logger.info("Тестирование RAG системы")
    logger.info("=" * 50)
    
    try:
        # Создаем RAG цепочку
        rag_chain = RAGChain(
            collection_name="test_rag",
            top_k=3,
            min_score=0.3
        )
        
        # Тест 1: Простой вопрос без документов (должен использовать общие знания)
        logger.info("\nТест 1: Вопрос без документов")
        logger.info("-" * 50)
        question1 = "Что такое Python?"
        result1 = await rag_chain.query(question1, use_rag=False)
        
        logger.info(f"Вопрос: {question1}")
        logger.info(f"Ответ: {result1['answer'][:200]}...")
        logger.info(f"Модель: {result1['model']}")
        logger.info(f"Провайдер: {result1['provider']}")
        logger.info(f"Ошибка: {result1.get('error', 'Нет')}")
        
        # Тест 2: Вопрос с RAG (может не найти документы, но должен работать)
        logger.info("\nТест 2: Вопрос с RAG поиском")
        logger.info("-" * 50)
        question2 = "Что содержится в документах?"
        result2 = await rag_chain.query(question2, use_rag=True)
        
        logger.info(f"Вопрос: {question2}")
        logger.info(f"Ответ: {result2['answer'][:200]}...")
        logger.info(f"Найдено документов: {result2['context_count']}")
        logger.info(f"Источники: {result2['sources']}")
        logger.info(f"Ошибка: {result2.get('error', 'Нет')}")
        
        # Закрываем ресурсы
        await rag_chain.close()
        
        logger.info("\n" + "=" * 50)
        logger.info("✅ Тест завершен успешно!")
        logger.info("=" * 50)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_rag())
    exit(0 if success else 1)

