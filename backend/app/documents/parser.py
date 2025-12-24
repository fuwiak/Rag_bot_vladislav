"""
Парсер для различных форматов документов
"""
from typing import BinaryIO
import docx
import PyPDF2
import io
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class DocumentParser:
    """Парсер документов разных форматов"""
    
    def __init__(self):
        # Thread pool для CPU-интенсивных операций (парсинг PDF/DOCX)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="doc_parser")
    
    async def parse(self, content: bytes, file_type: str) -> str:
        """
        Парсинг документа в текст (неблокирующий)
        
        Args:
            content: Содержимое файла в байтах
            file_type: Тип файла (txt, docx, pdf, xlsx, xls)
        
        Returns:
            Текст документа
        """
        loop = asyncio.get_event_loop()
        
        if file_type == "txt":
            # Текст быстро парсится, можно синхронно
            return self._parse_txt(content)
        elif file_type == "docx":
            # Запускаем в thread pool, чтобы не блокировать event loop
            return await loop.run_in_executor(self.executor, self._parse_docx, content)
        elif file_type == "pdf":
            # Запускаем в thread pool, чтобы не блокировать event loop
            return await loop.run_in_executor(self.executor, self._parse_pdf, content)
        elif file_type in ["xlsx", "xls"]:
            # Запускаем в thread pool для Excel
            return await loop.run_in_executor(self.executor, self._parse_excel, content)
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {file_type}")
    
    def _parse_txt(self, content: bytes) -> str:
        """Парсинг текстового файла"""
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("utf-8", errors="ignore")
    
    def _parse_docx(self, content: bytes) -> str:
        """Парсинг DOCX файла (блокирующая операция, выполняется в thread pool)"""
        import gc
        
        doc = docx.Document(io.BytesIO(content))
        paragraphs = []
        
        # Обрабатываем параграфы по одному для экономии памяти
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)
        
        # Освобождаем память после парсинга
        del doc
        gc.collect()
        
        return "\n".join(paragraphs)
    
    def _parse_pdf(self, content: bytes) -> str:
        """Парсинг PDF файла (блокирующая операция, выполняется в thread pool)"""
        import gc
        
        pdf_file = io.BytesIO(content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text_parts = []
        # Обрабатываем страницы по одной и освобождаем память
        for i, page in enumerate(pdf_reader.pages):
            try:
                text = page.extract_text()
                if text.strip():
                    text_parts.append(text)
                # Освобождаем память после каждой страницы
                if i % 10 == 0:  # Каждые 10 страниц
                    gc.collect()
            except Exception as e:
                # Пропускаем страницы с ошибками, продолжаем обработку
                continue
        
        # Освобождаем память после парсинга
        del pdf_reader
        del pdf_file
        gc.collect()
        
        return "\n\n".join(text_parts)
    
    def _parse_excel(self, content: bytes) -> str:
        """Парсинг Excel файла (блокирующая операция, выполняется в thread pool)"""
        import gc
        import pandas as pd
        
        excel_file = io.BytesIO(content)
        text_parts = []
        
        try:
            # Читаем все листы Excel
            excel_reader = pd.ExcelFile(excel_file)
            
            for sheet_name in excel_reader.sheet_names:
                try:
                    df = pd.read_excel(excel_reader, sheet_name=sheet_name)
                    df = df.fillna("")
                    
                    # Преобразуем DataFrame в текст
                    for idx, row in df.iterrows():
                        row_text = " | ".join([str(val) for val in row.values if str(val).strip()])
                        if row_text:
                            text_parts.append(f"Лист '{sheet_name}', строка {idx + 1}: {row_text}")
                    
                    # Освобождаем память после каждого листа
                    del df
                    gc.collect()
                except Exception as e:
                    # Пропускаем листы с ошибками
                    continue
            
            del excel_reader
            del excel_file
            gc.collect()
            
        except Exception as e:
            logger.warning(f"Ошибка при парсинге Excel: {str(e)}")
            raise
        
        return "\n".join(text_parts)


