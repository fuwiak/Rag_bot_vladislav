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
        """Парсинг PDF файла (блокирующая операция, выполняется в thread pool)
        
        Использует PyPDF2 как основной парсер, с fallback на pdfplumber для лучшей поддержки простых PDF.
        """
        import gc
        
        pdf_file = io.BytesIO(content)
        text_parts = []
        total_pages = 0
        empty_pages = 0
        error_pages = 0
        
        # Пробуем PyPDF2 сначала
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            total_pages = len(pdf_reader.pages)
            
            # Обрабатываем страницы по одной и освобождаем память
            for i, page in enumerate(pdf_reader.pages):
                try:
                    text = page.extract_text()
                    if text and text.strip():
                        text_parts.append(text)
                    else:
                        empty_pages += 1
                        logger.warning(f"PDF page {i+1}/{total_pages} returned empty text (PyPDF2)")
                except Exception as e:
                    error_pages += 1
                    logger.warning(f"Error extracting text from page {i+1}/{total_pages} (PyPDF2): {e}")
                    continue
                
                # Освобождаем память после каждой страницы
                if i % 10 == 0:  # Каждые 10 страниц
                    gc.collect()
            
            # Освобождаем память после парсинга
            del pdf_reader
            del pdf_file
            gc.collect()
            
            # Если PyPDF2 не извлек текст или слишком много пустых страниц, пробуем pdfplumber
            if not text_parts or (empty_pages > total_pages * 0.5 and total_pages > 0):
                logger.warning(f"PyPDF2 extracted {len(text_parts)} pages with text, {empty_pages} empty pages. Trying pdfplumber fallback...")
                return self._parse_pdf_with_pdfplumber(content)
            
            if empty_pages == total_pages and total_pages > 0:
                logger.error(f"All {total_pages} pages returned empty text with PyPDF2. Trying pdfplumber fallback...")
                return self._parse_pdf_with_pdfplumber(content)
            
            logger.info(f"PDF parsed successfully: {len(text_parts)} pages with text, {empty_pages} empty, {error_pages} errors (PyPDF2)")
            return "\n\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"PyPDF2 failed to parse PDF: {e}. Trying pdfplumber fallback...")
            return self._parse_pdf_with_pdfplumber(content)
    
    def _parse_pdf_with_pdfplumber(self, content: bytes) -> str:
        """Fallback парсер PDF используя pdfplumber (лучше для простых PDF)"""
        import gc
        try:
            import pdfplumber
        except ImportError:
            logger.error("pdfplumber not installed. Install with: pip install pdfplumber")
            raise ImportError("pdfplumber не установлен. Установите: pip install pdfplumber")
        
        pdf_file = io.BytesIO(content)
        text_parts = []
        total_pages = 0
        empty_pages = 0
        
        try:
            with pdfplumber.open(pdf_file) as pdf:
                total_pages = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    try:
                        text = page.extract_text()
                        if text and text.strip():
                            text_parts.append(text)
                        else:
                            empty_pages += 1
                            logger.warning(f"PDF page {i+1}/{total_pages} returned empty text (pdfplumber)")
                    except Exception as e:
                        logger.warning(f"Error extracting text from page {i+1}/{total_pages} (pdfplumber): {e}")
                        empty_pages += 1
                        continue
                    
                    # Освобождаем память после каждой страницы
                    if i % 10 == 0:
                        gc.collect()
            
            if empty_pages == total_pages and total_pages > 0:
                logger.error(f"All {total_pages} pages returned empty text with pdfplumber. PDF may be scanned/image-based.")
            
            logger.info(f"PDF parsed with pdfplumber: {len(text_parts)} pages with text, {empty_pages} empty")
            return "\n\n".join(text_parts)
            
        except Exception as e:
            logger.error(f"pdfplumber also failed to parse PDF: {e}")
            raise
        finally:
            del pdf_file
            gc.collect()
    
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


