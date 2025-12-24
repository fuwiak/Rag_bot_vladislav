"""
Скрипт для загрузки прайс-листа из Excel в векторную БД Qdrant.
Извлекает информацию о продуктах/услугах и ценах для использования в RAG.
"""

import os
import logging
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

from qdrant_loader import QdrantLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PriceListLoader:
    """Загрузчик прайс-листа из Excel в векторную БД"""
    
    def __init__(self, excel_path: str, qdrant_loader: QdrantLoader = None):
        self.excel_path = Path(excel_path)
        self.qdrant_loader = qdrant_loader or QdrantLoader()
        
        if not self.excel_path.exists():
            raise FileNotFoundError(f"Excel файл не найден: {excel_path}")
    
    def parse_excel(self) -> List[Dict[str, Any]]:
        """
        Парсит Excel файл и извлекает данные о продуктах/услугах.
        
        Returns:
            Список словарей с данными о продуктах
        """
        logger.info(f"Чтение Excel файла: {self.excel_path}")
        
        try:
            # Читаем все листы Excel
            excel_file = pd.ExcelFile(self.excel_path)
            logger.info(f"Найдено листов: {excel_file.sheet_names}")
            
            all_products = []
            
            # Обрабатываем каждый лист
            # Приоритет листам с ценами и продуктами
            priority_sheets = [s for s in excel_file.sheet_names if 
                              s.startswith("SaleList") or s == "ProductList" or s in ["Home+SOHO", "Services"]]
            other_sheets = [s for s in excel_file.sheet_names if s not in priority_sheets]
            
            sheets_to_process = priority_sheets + other_sheets
            
            for sheet_name in sheets_to_process:
                logger.info(f"Обработка листа: {sheet_name}")
                try:
                    df = pd.read_excel(self.excel_path, sheet_name=sheet_name)
                    
                    # Пропускаем пустые листы
                    if df.empty or len(df.columns) == 0:
                        logger.info(f"  Пропуск пустого листа: {sheet_name}")
                        continue
                    
                    # Преобразуем DataFrame в список словарей
                    products = self._process_sheet(df, sheet_name)
                    all_products.extend(products)
                    
                    if products:
                        logger.info(f"  Извлечено продуктов: {len(products)}")
                except Exception as e:
                    logger.warning(f"  Ошибка обработки листа {sheet_name}: {str(e)}")
                    continue
            
            logger.info(f"Всего извлечено продуктов/услуг: {len(all_products)}")
            return all_products
            
        except Exception as e:
            logger.error(f"Ошибка при чтении Excel: {str(e)}")
            raise
    
    def _process_sheet(self, df: pd.DataFrame, sheet_name: str) -> List[Dict[str, Any]]:
        """
        Обрабатывает один лист Excel.
        
        Args:
            df: DataFrame с данными листа
            sheet_name: Название листа
        
        Returns:
            Список продуктов из листа
        """
        products = []
        
        # Заменяем NaN на пустые строки
        df = df.fillna("")
        
        # Преобразуем названия колонок в нижний регистр для удобства
        df.columns = df.columns.str.strip().str.lower()
        
        logger.info(f"Колонки в листе '{sheet_name}': {list(df.columns)}")
        
        # Проходим по каждой строке
        for idx, row in df.iterrows():
            try:
                product = self._row_to_product(row, sheet_name, idx, df.columns)
                if product:
                    products.append(product)
            except Exception as e:
                logger.warning(f"Ошибка обработки строки {idx}: {str(e)}")
                continue
        
        return products
    
    def _row_to_product(self, row: pd.Series, sheet_name: str, row_idx: int, df_columns: pd.Index) -> Dict[str, Any]:
        """
        Преобразует строку DataFrame в словарь с данными продукта.
        
        Args:
            row: Строка DataFrame
            sheet_name: Название листа
            row_idx: Индекс строки
            df_columns: Колонки DataFrame
        
        Returns:
            Словарь с данными продукта или None
        """
        # Пытаемся определить ключевые поля
        # Адаптируем под структуру прайс-листа
        
        product = {
            "sheet_name": sheet_name,
            "row_index": row_idx,
        }
        
        # Извлекаем основные поля (адаптируем под структуру прайс-листа)
        common_fields = {
            "name": ["product", "product name", "название", "product_name", "наименование", "товар", "услуга"],
            "description": ["component", "описание", "description", "детали"],
            "price": ["price", "цена", "стоимость", "руб", "рублей", "rub", "cost"],
            "category": ["category", "категория", "тип", "вид"],
            "sector": ["sector", "сектор", "отрасль"],
            "code": ["code", "артикул", "sku", "код", "article", "article number"],
            "model": ["model", "модель"],
            "licence_object": ["licenceobject", "licence_object", "объект лицензии"],
        }
        
        # Ищем значения для каждого поля
        for field, possible_names in common_fields.items():
            value = None
            for col_name in df_columns:
                col_lower = str(col_name).lower().strip()
                if any(name in col_lower for name in possible_names):
                    val = row[col_name]
                    if pd.notna(val) and str(val).strip() and str(val).lower() not in ["nan", "none", ""]:
                        value = val
                        break
            if value:
                product[field] = str(value).strip()
        
        # Если не нашли название - пытаемся взять первую непустую колонку с осмысленным значением
        if "name" not in product or not product["name"]:
            for col in df_columns:
                val = row[col]
                if pd.notna(val) and str(val).strip() and str(val).lower() not in ["nan", "none", ""]:
                    val_str = str(val).strip()
                    # Пропускаем слишком короткие значения
                    if len(val_str) > 3:
                        product["name"] = val_str
                        break
        
        # Если все равно нет названия - пропускаем строку
        if "name" not in product or not product["name"]:
            return None
        
        # Создаем текстовое описание для RAG
        text_parts = []
        text_parts.append(f"Продукт/услуга: {product.get('name', 'Не указано')}")
        
        if product.get("code"):
            text_parts.append(f"Код продукта: {product['code']}")
        
        if product.get("sector"):
            text_parts.append(f"Сектор: {product['sector']}")
        
        if product.get("category"):
            text_parts.append(f"Категория: {product['category']}")
        
        if product.get("model"):
            text_parts.append(f"Модель: {product['model']}")
        
        if product.get("description") or product.get("component"):
            comp = product.get("component") or product.get("description")
            text_parts.append(f"Компонент: {comp}")
        
        if product.get("licence_object"):
            text_parts.append(f"Объект лицензии: {product['licence_object']}")
        
        if product.get("price"):
            text_parts.append(f"Цена: {product['price']}")
        
        # Добавляем все остальные колонки как дополнительная информация
        used_fields = set()
        for fields_list in common_fields.values():
            used_fields.update(fields_list)
        
        for col in df_columns:
            col_lower = str(col).lower()
            if not any(name in col_lower for name in used_fields):
                val = row[col]
                if val and str(val).strip() and str(val).lower() not in ["nan", "none", ""]:
                    text_parts.append(f"{col}: {val}")
        
        product["text"] = "\n".join(text_parts)
        
        return product
    
    def load_to_qdrant(self, products: List[Dict[str, Any]], source_url: str = None) -> int:
        """
        Загружает продукты в векторную БД Qdrant.
        
        Args:
            products: Список продуктов
            source_url: URL источника (по умолчанию путь к файлу)
        
        Returns:
            Общее количество загруженных чанков
        """
        if not source_url:
            # Используем относительный путь для совместимости с whitelist
            excel_path_rel = Path(self.excel_path).relative_to(Path.cwd())
            source_url = f"file://{excel_path_rel}"
        
        total_chunks = 0
        
        for product in products:
            try:
                metadata = {
                    "source_url": source_url,
                    "source_type": "pricelist",
                    "file_name": self.excel_path.name,
                    "sheet_name": product.get("sheet_name", ""),
                    "row_index": product.get("row_index", 0),
                    "product_name": product.get("name", ""),
                    "category": product.get("category", ""),
                    "price": product.get("price", ""),
                    "sku": product.get("sku", ""),
                    "units": product.get("units", ""),
                }
                
                text = product.get("text", "")
                if not text:
                    continue
                
                # Загружаем в Qdrant (whitelist фильтр отключен для прайс-листа)
                chunks = self.qdrant_loader.load_document(
                    text=text,
                    metadata=metadata,
                    filter_by_whitelist=False  # Прайс-лист - это внутренний источник
                )
                
                total_chunks += chunks
                logger.debug(f"Загружено чанков для продукта '{product.get('name')}': {chunks}")
                
            except Exception as e:
                logger.error(f"Ошибка загрузки продукта '{product.get('name')}': {str(e)}")
                continue
        
        return total_chunks
    
    def load(self) -> int:
        """
        Полный цикл: парсинг Excel и загрузка в Qdrant.
        
        Returns:
            Общее количество загруженных чанков
        """
        logger.info("Начало загрузки прайс-листа...")
        
        # Парсим Excel
        products = self.parse_excel()
        
        if not products:
            logger.warning("Не найдено продуктов для загрузки")
            return 0
        
        # Загружаем в Qdrant
        total_chunks = self.load_to_qdrant(products)
        
        logger.info(f"✅ Загрузка завершена. Всего загружено чанков: {total_chunks}")
        
        return total_chunks


def main():
    """Главная функция для запуска скрипта"""
    load_dotenv()
    
    # Путь к прайс-листу
    pricelist_path = os.getenv(
        "PRICELIST_PATH",
        "/Users/user/kaspersky_bot/media/PriceListRUSSIA_09_10_2025.xlsx"
    )
    
    if not Path(pricelist_path).exists():
        logger.error(f"Файл прайс-листа не найден: {pricelist_path}")
        logger.info("Укажите правильный путь в переменной окружения PRICELIST_PATH")
        return
    
    try:
        loader = PriceListLoader(pricelist_path)
        total_chunks = loader.load()
        
        logger.info("="*50)
        logger.info(f"✅ Успешно загружено {total_chunks} чанков в векторную БД")
        logger.info("Теперь данные прайс-листа доступны для RAG поиска")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке прайс-листа: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

