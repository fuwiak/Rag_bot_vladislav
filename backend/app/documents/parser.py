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
        """Парсинг PDF файла с множественными fallback-ами
        
        Fallback-цепочка:
        1. PyPDF2 (основной)
        2. pdfplumber (лучше для простых PDF)
        3. PyMuPDF/fitz (очень мощный парсер)
        4. pymupdf4llm (специально для LLM)
        5. OCR fallback (для сканированных PDF)
        
        Всегда показывает preview файла для диагностики
        """
        import gc
        
        # Показываем preview файла для диагностики
        file_size = len(content) / 1024  # KB
        logger.info(f"[PDF PARSER] Начало парсинга PDF: размер {file_size:.2f} KB")
        
        # Проверяем, что файл действительно PDF
        if not content.startswith(b'%PDF'):
            logger.warning(f"[PDF PARSER] Файл не начинается с %PDF, возможно поврежден")
            # Пробуем все равно парсить
        
        # Fallback 1: PyPDF2
        try:
            result = self._parse_pdf_with_pypdf2(content)
            if result and len(result.strip()) > 50:  # Минимум 50 символов
                logger.info(f"[PDF PARSER] ✅ PyPDF2 успешно: {len(result)} символов")
                return result
            else:
                logger.warning(f"[PDF PARSER] PyPDF2 вернул мало текста ({len(result) if result else 0} символов), пробуем pdfplumber...")
        except Exception as e:
            logger.warning(f"[PDF PARSER] PyPDF2 failed: {e}, пробуем pdfplumber...")
        
        # Fallback 2: pdfplumber
        try:
            result = self._parse_pdf_with_pdfplumber(content)
            if result and len(result.strip()) > 50:
                logger.info(f"[PDF PARSER] ✅ pdfplumber успешно: {len(result)} символов")
                return result
            else:
                logger.warning(f"[PDF PARSER] pdfplumber вернул мало текста ({len(result) if result else 0} символов), пробуем PyMuPDF...")
        except Exception as e:
            logger.warning(f"[PDF PARSER] pdfplumber failed: {e}, пробуем PyMuPDF...")
        
        # Fallback 3: PyMuPDF (fitz) - очень мощный парсер
        try:
            result = self._parse_pdf_with_pymupdf(content)
            if result and len(result.strip()) > 50:
                logger.info(f"[PDF PARSER] ✅ PyMuPDF успешно: {len(result)} символов")
                return result
            else:
                logger.warning(f"[PDF PARSER] PyMuPDF вернул мало текста ({len(result) if result else 0} символов), пробуем pymupdf4llm...")
        except Exception as e:
            logger.warning(f"[PDF PARSER] PyMuPDF failed: {e}, пробуем pymupdf4llm...")
        
        # Fallback 4: pymupdf4llm (специально для LLM)
        try:
            result = self._parse_pdf_with_pymupdf4llm(content)
            if result and len(result.strip()) > 50:
                logger.info(f"[PDF PARSER] ✅ pymupdf4llm успешно: {len(result)} символов")
                return result
            else:
                logger.warning(f"[PDF PARSER] pymupdf4llm вернул мало текста ({len(result) if result else 0} символов)")
        except Exception as e:
            logger.warning(f"[PDF PARSER] pymupdf4llm failed: {e}")
        
        # Fallback 5: OCR (для сканированных PDF) - опционально
        try:
            result = self._parse_pdf_with_ocr(content)
            if result and len(result.strip()) > 50:
                logger.info(f"[PDF PARSER] ✅ OCR успешно: {len(result)} символов")
                return result
        except Exception as e:
            logger.warning(f"[PDF PARSER] OCR failed: {e}")
        
        # Если все fallback-ы не сработали
        error_msg = f"Все методы парсинга PDF не смогли извлечь текст. Файл может быть сканированным изображением или поврежден."
        logger.error(f"[PDF PARSER] ❌ {error_msg}")
        raise ValueError(error_msg)
    
    def _parse_pdf_with_pypdf2(self, content: bytes) -> str:
        """Парсинг PDF с PyPDF2"""
        import gc
        
        pdf_file = io.BytesIO(content)
        text_parts = []
        total_pages = 0
        empty_pages = 0
        
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            total_pages = len(pdf_reader.pages)
            logger.info(f"[PDF PARSER PyPDF2] Всего страниц: {total_pages}")
            
            for i, page in enumerate(pdf_reader.pages):
                try:
                    text = page.extract_text()
                    if text and text.strip():
                        text_parts.append(text)
                        # Показываем preview первой страницы
                        if i == 0:
                            preview = text[:500] if len(text) > 500 else text
                            logger.info(f"[PDF PARSER PyPDF2] Preview страницы 1: {preview}...")
                    else:
                        empty_pages += 1
                        logger.warning(f"[PDF PARSER PyPDF2] Страница {i+1}/{total_pages} пустая")
                except Exception as e:
                    logger.warning(f"[PDF PARSER PyPDF2] Ошибка страницы {i+1}: {e}")
                    empty_pages += 1
                    continue
                
                if i % 10 == 0:
                    gc.collect()
            
            del pdf_reader
            del pdf_file
            gc.collect()
            
            if not text_parts:
                return ""
            
            result = "\n\n".join(text_parts)
            logger.info(f"[PDF PARSER PyPDF2] Извлечено {len(text_parts)} страниц, {empty_pages} пустых, всего {len(result)} символов")
            return result
            
        except Exception as e:
            logger.error(f"[PDF PARSER PyPDF2] Ошибка: {e}")
            raise
    
    def _parse_pdf_with_pdfplumber(self, content: bytes) -> str:
        """Fallback парсер PDF используя pdfplumber (лучше для простых PDF)"""
        import gc
        try:
            import pdfplumber
        except ImportError:
            logger.warning("[PDF PARSER pdfplumber] pdfplumber не установлен")
            raise ImportError("pdfplumber не установлен")
        
        pdf_file = io.BytesIO(content)
        text_parts = []
        total_pages = 0
        empty_pages = 0
        
        try:
            with pdfplumber.open(pdf_file) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"[PDF PARSER pdfplumber] Всего страниц: {total_pages}")
                
                for i, page in enumerate(pdf.pages):
                    try:
                        text = page.extract_text()
                        if text and text.strip():
                            text_parts.append(text)
                            # Preview первой страницы
                            if i == 0:
                                preview = text[:500] if len(text) > 500 else text
                                logger.info(f"[PDF PARSER pdfplumber] Preview страницы 1: {preview}...")
                        else:
                            empty_pages += 1
                            logger.warning(f"[PDF PARSER pdfplumber] Страница {i+1}/{total_pages} пустая")
                    except Exception as e:
                        logger.warning(f"[PDF PARSER pdfplumber] Ошибка страницы {i+1}: {e}")
                        empty_pages += 1
                        continue
                    
                    if i % 10 == 0:
                        gc.collect()
            
            if not text_parts:
                return ""
            
            result = "\n\n".join(text_parts)
            logger.info(f"[PDF PARSER pdfplumber] Извлечено {len(text_parts)} страниц, {empty_pages} пустых, всего {len(result)} символов")
            return result
            
        except Exception as e:
            logger.error(f"[PDF PARSER pdfplumber] Ошибка: {e}")
            raise
        finally:
            del pdf_file
            gc.collect()
    
    def _parse_pdf_with_pymupdf(self, content: bytes) -> str:
        """Парсинг PDF с PyMuPDF (fitz) - очень мощный парсер"""
        import gc
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("[PDF PARSER PyMuPDF] PyMuPDF не установлен. Установите: pip install pymupdf")
            raise ImportError("PyMuPDF не установлен")
        
        pdf_file = io.BytesIO(content)
        text_parts = []
        total_pages = 0
        
        try:
            doc = fitz.open(stream=pdf_file, filetype="pdf")
            total_pages = len(doc)
            logger.info(f"[PDF PARSER PyMuPDF] Всего страниц: {total_pages}")
            
            for i in range(total_pages):
                try:
                    page = doc[i]
                    text = page.get_text()
                    if text and text.strip():
                        text_parts.append(text)
                        # Preview первой страницы
                        if i == 0:
                            preview = text[:500] if len(text) > 500 else text
                            logger.info(f"[PDF PARSER PyMuPDF] Preview страницы 1: {preview}...")
                    else:
                        logger.warning(f"[PDF PARSER PyMuPDF] Страница {i+1}/{total_pages} пустая")
                except Exception as e:
                    logger.warning(f"[PDF PARSER PyMuPDF] Ошибка страницы {i+1}: {e}")
                    continue
                
                if i % 10 == 0:
                    gc.collect()
            
            doc.close()
            del pdf_file
            gc.collect()
            
            if not text_parts:
                return ""
            
            result = "\n\n".join(text_parts)
            logger.info(f"[PDF PARSER PyMuPDF] Извлечено {len(text_parts)} страниц, всего {len(result)} символов")
            return result
            
        except Exception as e:
            logger.error(f"[PDF PARSER PyMuPDF] Ошибка: {e}")
            raise
    
    def _parse_pdf_with_pymupdf4llm(self, content: bytes) -> str:
        """Парсинг PDF с pymupdf4llm (специально для LLM)"""
        import gc
        try:
            import pymupdf4llm
        except ImportError:
            logger.warning("[PDF PARSER pymupdf4llm] pymupdf4llm не установлен. Установите: pip install pymupdf4llm")
            raise ImportError("pymupdf4llm не установлен")
        
        pdf_file = io.BytesIO(content)
        
        try:
            # pymupdf4llm конвертирует PDF в Markdown для лучшей структуры
            md_text = pymupdf4llm.to_markdown(pdf_file)
            
            if md_text and len(md_text.strip()) > 50:
                preview = md_text[:500] if len(md_text) > 500 else md_text
                logger.info(f"[PDF PARSER pymupdf4llm] Preview: {preview}...")
                logger.info(f"[PDF PARSER pymupdf4llm] Извлечено {len(md_text)} символов в Markdown формате")
                return md_text
            else:
                return ""
            
        except Exception as e:
            logger.error(f"[PDF PARSER pymupdf4llm] Ошибка: {e}")
            raise
        finally:
            del pdf_file
            gc.collect()
    
    def _parse_pdf_with_ocr(self, content: bytes) -> str:
        """OCR fallback для сканированных PDF (опционально)"""
        import gc
        try:
            import pytesseract
            from PIL import Image
            import fitz  # PyMuPDF для конвертации PDF в изображения
        except ImportError:
            logger.warning("[PDF PARSER OCR] OCR библиотеки не установлены. Установите: pip install pytesseract pillow pymupdf")
            raise ImportError("OCR библиотеки не установлены")
        
        pdf_file = io.BytesIO(content)
        text_parts = []
        
        try:
            doc = fitz.open(stream=pdf_file, filetype="pdf")
            total_pages = len(doc)
            logger.info(f"[PDF PARSER OCR] OCR обработка {total_pages} страниц...")
            
            for i in range(min(total_pages, 10)):  # Ограничиваем до 10 страниц для OCR
                try:
                    page = doc[i]
                    # Конвертируем страницу в изображение
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x увеличение для лучшего качества
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # OCR
                    text = pytesseract.image_to_string(img, lang='rus+eng')
                    if text and text.strip():
                        text_parts.append(text)
                        if i == 0:
                            preview = text[:500] if len(text) > 500 else text
                            logger.info(f"[PDF PARSER OCR] Preview страницы 1: {preview}...")
                except Exception as e:
                    logger.warning(f"[PDF PARSER OCR] Ошибка OCR страницы {i+1}: {e}")
                    continue
            
            doc.close()
            del pdf_file
            gc.collect()
            
            if not text_parts:
                return ""
            
            result = "\n\n".join(text_parts)
            logger.info(f"[PDF PARSER OCR] OCR извлечено {len(text_parts)} страниц, всего {len(result)} символов")
            return result
            
        except Exception as e:
            logger.error(f"[PDF PARSER OCR] Ошибка: {e}")
            raise
    
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


