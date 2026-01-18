#!/usr/bin/env python3
"""
CLI команда для обработки файлов из папки /documents через Document Agent Adapter
Использование:
    python process_documents_folder.py --project-id <UUID> [--fast-indexing] [--max-concurrent 3]
"""
import asyncio
import argparse
import sys
from pathlib import Path
from uuid import UUID

# Добавляем путь к app для импорта
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import AsyncSessionLocal, init_db
from app.services.document_agent_adapter import DocumentAgentAdapter
from app.models.project import Project
from sqlalchemy import select
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description="Обработка файлов из папки /documents через Document Agent Adapter"
    )
    parser.add_argument(
        "--project-id",
        type=str,
        required=True,
        help="UUID проекта"
    )
    parser.add_argument(
        "--fast-indexing",
        action="store_true",
        help="Использовать быструю индексацию для больших PDF (200+ страниц)"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Максимальное количество одновременных задач (по умолчанию: 3)"
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Только сканировать папку, не обрабатывать файлы"
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Только показать статус обработки документов"
    )
    
    args = parser.parse_args()
    
    try:
        project_id = UUID(args.project_id)
    except ValueError:
        logger.error(f"Неверный формат UUID проекта: {args.project_id}")
        return 1
    
    # Инициализируем БД
    try:
        await init_db()
    except Exception as e:
        logger.warning(f"Ошибка инициализации БД: {e}")
    
    async with AsyncSessionLocal() as db:
        # Проверяем, существует ли проект
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        
        if not project:
            logger.error(f"Проект с ID {project_id} не найден")
            return 1
        
        logger.info(f"Проект найден: {project.name} (ID: {project_id})")
        
        adapter = DocumentAgentAdapter()
        
        # Если только статус
        if args.status_only:
            logger.info("Получение статуса обработки документов...")
            status = await adapter.get_processing_status(project_id=project_id)
            
            print("\n" + "="*60)
            print("СТАТУС ОБРАБОТКИ ДОКУМЕНТОВ")
            print("="*60)
            print(f"Всего документов: {status['total']}")
            print(f"Обрабатывается: {status['processing']}")
            print(f"Готово: {status['ready']}")
            print(f"Ошибки: {status['errors']}")
            print("\nДокументы:")
            for doc in status['documents']:
                status_emoji = {
                    'processing': '⏳',
                    'ready': '✅',
                    'error': '❌'
                }.get(doc['status'], '❓')
                print(f"  {status_emoji} {doc['filename']} ({doc['status']})")
            return 0
        
        # Сканируем папку
        logger.info("Сканирование папки с документами...")
        files = await adapter.scan_documents_folder(project_id=project_id)
        
        if not files:
            logger.warning("Файлы не найдены в папке проекта")
            return 0
        
        print("\n" + "="*60)
        print(f"НАЙДЕНО ФАЙЛОВ: {len(files)}")
        print("="*60)
        for file_info in files:
            size_mb = file_info['size'] / 1024 / 1024
            print(f"  📄 {file_info['filename']} ({size_mb:.2f} MB, {file_info['extension']})")
        
        # Если только сканирование
        if args.scan_only:
            return 0
        
        # Обрабатываем файлы
        print("\n" + "="*60)
        print("НАЧАЛО ОБРАБОТКИ ФАЙЛОВ")
        print("="*60)
        print(f"Быстрая индексация: {'Да' if args.fast_indexing else 'Нет'}")
        print(f"Максимум одновременных задач: {args.max_concurrent}")
        print()
        
        result = await adapter.process_all_files_from_folder(
            project_id=project_id,
            use_fast_indexing=args.fast_indexing,
            max_concurrent=args.max_concurrent
        )
        
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТЫ ОБРАБОТКИ")
        print("="*60)
        print(f"Обработано: {result['processed']}")
        print(f"Пропущено (уже обработаны): {result['skipped']}")
        print(f"Ошибки: {result['errors']}")
        print(f"Всего файлов: {result['total']}")
        
        if result['errors'] > 0:
            print("\nОшибки обработки:")
            for i, res in enumerate(result['results']):
                if isinstance(res, Exception):
                    print(f"  ❌ Ошибка файла {i+1}: {res}")
                elif not res.get('success'):
                    print(f"  ❌ {res.get('filename', 'Неизвестный файл')}: {res.get('error', 'Неизвестная ошибка')}")
        
        return 0 if result['errors'] == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
