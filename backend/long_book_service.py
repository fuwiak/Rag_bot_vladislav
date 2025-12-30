"""
long_book_service.py — сервис для работы с embedding и RAG для длинных книг (400+ страниц).

• Использует OpenRouter для AI-запросов
• Qdrant как основная векторная БД (легкий fallback на ChromaDB)
• Оптимизирован для больших объемов текста
"""
import os
import re
import json
import requests
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
import hashlib

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("[yellow]Qdrant не установлен. Будет использован ChromaDB fallback.[/yellow]")

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from rich import print, progress

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────── env ──────────────────────────────── #
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise EnvironmentError("В .env должен быть OPENROUTER_API_KEY")

# ─────────────────────────────── OpenRouter models ──────────────────────────────── #
OPENROUTER_PRIORITY = [
    "deepseek/deepseek-prover-v2:free",
    "tngtech/deepseek-r1t-chimera:free",
    "microsoft/mai-ds-r1:free",
    "mistral/mistral-8b:free",
]

# ─────────────────────────────── config ──────────────────────────────── #
@dataclass
class BookChunk:
    """Фрагмент книги с метаданными."""
    text: str
    source: str  # название книги
    page: Optional[int] = None
    chapter: Optional[str] = None
    chunk_index: int = 0
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

# ─────────────────────────────── OpenRouter chat ──────────────────────────────── #

def chat_openrouter(prompt: str, temp: float = 0.2, max_tokens: int = 4096) -> str:
    """Вызов OpenRouter API с автоматическим переключением моделей."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    for model in OPENROUTER_PRIORITY:
        data = {
            "model": model,
            "temperature": temp,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=120
            )
            if r.status_code == 429:
                print(f"[yellow]OpenRouter limit на {model}. Перехожу к следующей…[/yellow]")
                continue
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()
        except (requests.HTTPError, requests.ConnectionError) as e:
            print(f"[yellow]Ошибка OpenRouter model {model}: {e}. Пробую следующую…[/yellow]")
            continue
    
    raise RuntimeError("Все OpenRouter модели недоступны или исчерпали лимит")

# ─────────────────────────────── text splitting ──────────────────────────────── #

class SmartTextSplitter:
    """Умный разделитель текста с сохранением контекста для медицинских книг."""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
    
    def split_book(self, text: str, source: str, metadata: Optional[Dict] = None) -> List[BookChunk]:
        """Разделяет книгу на чанки с метаданными."""
        chunks = self.splitter.split_text(text)
        result = []
        
        for idx, chunk_text in enumerate(chunks):
            chunk = BookChunk(
                text=chunk_text,
                source=source,
                chunk_index=idx,
                metadata=metadata or {}
            )
            result.append(chunk)
        
        return result

# ─────────────────────────────── embeddings ──────────────────────────────── #

class EmbeddingService:
    """Сервис для создания embedding с fallback на разные модели."""
    
    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self.embeddings = None
        self.embedding_dim = 384  # для multilingual-MiniLM
        self._init_embeddings()
    
    def _init_embeddings(self):
        """Инициализирует embedding модель."""
        # Пробуем OpenRouter embeddings (если доступны)
        try:
            # OpenRouter поддерживает некоторые embedding модели
            # Но для простоты используем HuggingFace как основной вариант
            print(f"[cyan]Использую HuggingFace embeddings: {self.model_name}[/cyan]")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            # Получаем реальную размерность
            test_embed = self.embeddings.embed_query("test")
            self.embedding_dim = len(test_embed)
        except Exception as e:
            print(f"[red]Ошибка инициализации embeddings: {e}[/red]")
            raise
    
    def embed_text(self, text: str) -> List[float]:
        """Создает embedding для текста."""
        return self.embeddings.embed_query(text)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Создает embeddings для списка документов."""
        return self.embeddings.embed_documents(texts)

# ─────────────────────────────── vector store (Qdrant) ──────────────────────────────── #

class QdrantStore:
    """Обертка для работы с Qdrant."""
    
    def __init__(self, collection_name: str, path: Optional[str] = None, url: Optional[str] = None):
        self.collection_name = collection_name
        
        if url:
            self.client = QdrantClient(url=url)
        elif path:
            self.client = QdrantClient(path=path)
        else:
            # In-memory для тестов
            self.client = QdrantClient(":memory:")
        
        self.embedding_dim = None  # будет установлено при первом добавлении
    
    def ensure_collection(self, embedding_dim: int):
        """Создает коллекцию, если её нет."""
        if self.embedding_dim is None:
            self.embedding_dim = embedding_dim
        
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            # Коллекция не существует, создаем
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=embedding_dim,
                    distance=Distance.COSINE
                )
            )
    
    def add_points(self, ids: List[str], embeddings: List[List[float]], 
                   texts: List[str], metadatas: List[Dict]):
        """Добавляет точки в коллекцию."""
        if not ids:
            return
        
        embedding_dim = len(embeddings[0])
        self.ensure_collection(embedding_dim)
        
        points = [
            PointStruct(
                id=hash(id_str) % (2**63),  # Qdrant требует int64 ID
                vector=emb,
                payload={
                    "text": text,
                    "id": id_str,
                    **meta
                }
            )
            for id_str, emb, text, meta in zip(ids, embeddings, texts, metadatas)
        ]
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
    
    def search(self, query_embedding: List[float], n_results: int = 5, 
               source_filter: Optional[str] = None) -> List[Dict]:
        """Поиск по коллекции."""
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            return []
        
        query_filter = None
        if source_filter:
            query_filter = {
                "must": [{"key": "source", "match": {"value": source_filter}}]
            }
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=n_results,
            query_filter=query_filter
        )
        
        formatted = []
        for result in results:
            formatted.append({
                "text": result.payload.get("text", ""),
                "metadata": {k: v for k, v in result.payload.items() if k != "text"},
                "score": result.score,
                "id": result.payload.get("id", "")
            })
        
        return formatted
    
    def delete_by_source(self, source: str):
        """Удаляет все точки с указанным source."""
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            return
        
        self.client.delete(
            collection_name=self.collection_name,
            points_selector={
                "filter": {
                    "must": [{"key": "source", "match": {"value": source}}]
                }
            }
        )
    
    def get_all_sources(self) -> List[str]:
        """Возвращает список всех источников."""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            # Qdrant не имеет прямого способа получить все payload, 
            # используем scroll для получения всех точек
            points, _ = self.client.scroll(
                collection_name=self.collection_name,
                limit=10000
            )
            sources = set()
            for point in points:
                if "source" in point.payload:
                    sources.add(point.payload["source"])
            return sorted(list(sources))
        except Exception:
            return []

# ─────────────────────────────── vector store (ChromaDB fallback) ──────────────────────────────── #

class ChromaStore:
    """Fallback обертка для ChromaDB."""
    
    def __init__(self, collection_name: str, db_path: Path):
        if not CHROMA_AVAILABLE:
            raise RuntimeError("ChromaDB не установлен")
        
        self.collection_name = collection_name
        self.db_path = db_path
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_points(self, ids: List[str], embeddings: List[List[float]], 
                   texts: List[str], metadatas: List[Dict]):
        """Добавляет точки в коллекцию."""
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
    
    def search(self, query_embedding: List[float], n_results: int = 5, 
               source_filter: Optional[str] = None) -> List[Dict]:
        """Поиск по коллекции."""
        where = {"source": source_filter} if source_filter else None
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )
        
        formatted = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                distance = results['distances'][0][i] if 'distances' in results else 0.0
                similarity = 1 - distance
                
                formatted.append({
                    "text": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "score": similarity,
                    "id": results['ids'][0][i]
                })
        
        return formatted
    
    def delete_by_source(self, source: str):
        """Удаляет все точки с указанным source."""
        existing = self.collection.get(where={"source": source})
        if existing['ids']:
            self.collection.delete(ids=existing['ids'])
    
    def get_all_sources(self) -> List[str]:
        """Возвращает список всех источников."""
        all_data = self.collection.get()
        sources = set()
        if all_data['metadatas']:
            for meta in all_data['metadatas']:
                if 'source' in meta:
                    sources.add(meta['source'])
        return sorted(list(sources))

# ─────────────────────────────── main service ──────────────────────────────── #

class LongBookService:
    """Основной сервис для работы с длинными книгами через RAG."""
    
    def __init__(
        self,
        collection_name: str = "long_books",
        qdrant_path: Optional[Path] = None,
        qdrant_url: Optional[str] = None,
        chroma_fallback_path: Optional[Path] = None,
        use_qdrant: bool = True
    ):
        self.collection_name = collection_name
        self.use_qdrant = use_qdrant and QDRANT_AVAILABLE
        
        # Инициализация векторного хранилища
        if self.use_qdrant:
            try:
                qdrant_path_str = str(qdrant_path) if qdrant_path else None
                self.vector_store = QdrantStore(
                    collection_name=collection_name,
                    path=qdrant_path_str,
                    url=qdrant_url
                )
                print(f"[green]✓ Использую Qdrant для векторного хранилища[/green]")
            except Exception as e:
                print(f"[yellow]Ошибка Qdrant: {e}. Переключаюсь на ChromaDB fallback...[/yellow]")
                self.use_qdrant = False
        
        if not self.use_qdrant:
            if not CHROMA_AVAILABLE:
                raise RuntimeError("Ни Qdrant, ни ChromaDB не доступны")
            
            fallback_path = chroma_fallback_path or Path("./chroma_index_fallback")
            self.vector_store = ChromaStore(collection_name, fallback_path)
            print(f"[green]✓ Использую ChromaDB fallback[/green]")
        
        # Инициализация сервисов
        self.embedding_service = EmbeddingService()
        self.text_splitter = SmartTextSplitter(chunk_size=1000, chunk_overlap=200)
    
    def _generate_id(self, source: str, chunk_index: int) -> str:
        """Генерирует уникальный ID для чанка."""
        content = f"{source}_{chunk_index}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def index_book(
        self,
        text: str,
        source: str,
        metadata: Optional[Dict] = None,
        batch_size: int = 50
    ) -> int:
        """
        Индексирует книгу в векторной БД.
        
        Args:
            text: Текст книги
            source: Название/источник книги
            metadata: Дополнительные метаданные
            batch_size: Размер батча для обработки
        
        Returns:
            Количество проиндексированных чанков
        """
        print(f"[cyan]Индексирую книгу: {source}[/cyan]")
        
        # Проверка, не проиндексирована ли уже эта книга
        existing_sources = self.vector_store.get_all_sources()
        if source in existing_sources:
            print(f"[yellow]Книга {source} уже проиндексирована. Удаляю старую версию...[/yellow]")
            self.vector_store.delete_by_source(source)
        
        # Разделение на чанки
        chunks = self.text_splitter.split_book(text, source, metadata)
        print(f"[cyan]Создано {len(chunks)} чанков[/cyan]")
        
        # Обработка батчами
        total_indexed = 0
        with progress.Progress() as prog:
            task = prog.add_task("Создание embeddings...", total=len(chunks))
            
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                
                # Подготовка данных
                texts = [chunk.text for chunk in batch]
                ids = [self._generate_id(chunk.source, chunk.chunk_index) for chunk in batch]
                metadatas = [
                    {
                        "source": chunk.source,
                        "chunk_index": chunk.chunk_index,
                        **chunk.metadata
                    }
                    for chunk in batch
                ]
                
                # Создание embeddings
                embeddings = self.embedding_service.embed_documents(texts)
                
                # Добавление в хранилище
                self.vector_store.add_points(
                    ids=ids,
                    embeddings=embeddings,
                    texts=texts,
                    metadatas=metadatas
                )
                
                total_indexed += len(batch)
                prog.update(task, advance=len(batch))
        
        print(f"[green]✓ Проиндексировано {total_indexed} чанков из {source}[/green]")
        return total_indexed
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        source_filter: Optional[str] = None,
        min_score: float = 0.0
    ) -> List[Dict]:
        """
        Семантический поиск по индексированным книгам.
        
        Args:
            query: Поисковый запрос
            n_results: Количество результатов
            source_filter: Фильтр по источнику (опционально)
            min_score: Минимальный score для результата
        
        Returns:
            Список результатов с текстом, метаданными и score
        """
        # Создание embedding для запроса
        query_embedding = self.embedding_service.embed_text(query)
        
        # Поиск
        results = self.vector_store.search(
            query_embedding=query_embedding,
            n_results=n_results,
            source_filter=source_filter
        )
        
        # Фильтрация по min_score
        filtered_results = [
            r for r in results if r['score'] >= min_score
        ]
        
        return filtered_results
    
    def get_context_for_query(
        self,
        query: str,
        n_results: int = 5,
        source_filter: Optional[str] = None,
        context_window: int = 3000
    ) -> str:
        """
        Получает контекст для запроса, объединяя найденные фрагменты.
        
        Args:
            query: Поисковый запрос
            n_results: Количество результатов для объединения
            source_filter: Фильтр по источнику
            context_window: Максимальная длина контекста в символах
        
        Returns:
            Объединенный контекст
        """
        results = self.search(query, n_results=n_results * 2, source_filter=source_filter)
        
        context_parts = []
        current_length = 0
        
        for result in results:
            text = result['text']
            if current_length + len(text) > context_window:
                break
            context_parts.append(
                f"[Источник: {result['metadata'].get('source', 'неизвестно')}]\n{text}"
            )
            current_length += len(text)
        
        return "\n\n---\n\n".join(context_parts)
    
    def rag_query(
        self,
        query: str,
        n_results: int = 5,
        source_filter: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temp: float = 0.2,
        max_tokens: int = 4096
    ) -> str:
        """
        RAG-запрос: поиск контекста + генерация ответа через OpenRouter.
        
        Args:
            query: Пользовательский запрос
            n_results: Количество результатов для поиска
            source_filter: Фильтр по источнику
            system_prompt: Дополнительный системный промпт
            temp: Temperature для генерации
            max_tokens: Максимальное количество токенов
        
        Returns:
            Ответ AI с использованием найденного контекста
        """
        # Поиск релевантного контекста
        print(f"[cyan]Ищу контекст для запроса: {query[:50]}...[/cyan]")
        context = self.get_context_for_query(query, n_results=n_results, source_filter=source_filter)
        
        if not context:
            return "Не найдено релевантной информации в индексированных книгах."
        
        # Формирование промпта
        system = system_prompt or (
            "Ты опытный медицинский эксперт. Используй предоставленный контекст из медицинских книг "
            "для ответа на вопрос. Если в контексте нет достаточной информации, укажи это."
        )
        
        prompt = f"""{system}

КОНТЕКСТ ИЗ КНИГ:
{context}

ВОПРОС: {query}

ОТВЕТ:"""
        
        # Вызов OpenRouter
        print("[cyan]Генерирую ответ с использованием RAG через OpenRouter...[/cyan]")
        response = chat_openrouter(prompt, temp=temp, max_tokens=max_tokens)
        
        return response
    
    def list_indexed_books(self) -> List[str]:
        """Возвращает список проиндексированных книг."""
        return self.vector_store.get_all_sources()
    
    def delete_book(self, source: str) -> bool:
        """Удаляет книгу из индекса."""
        existing_sources = self.vector_store.get_all_sources()
        if source in existing_sources:
            self.vector_store.delete_by_source(source)
            print(f"[green]✓ Удалена книга: {source}[/green]")
            return True
        print(f"[yellow]Книга {source} не найдена в индексе[/yellow]")
        return False
    
    def get_stats(self) -> Dict:
        """Возвращает статистику по индексу."""
        sources = self.vector_store.get_all_sources()
        
        # Подсчет чанков по источникам (приблизительный)
        books = {}
        for source in sources:
            # Получаем несколько результатов для оценки
            results = self.search("", n_results=1000, source_filter=source)
            books[source] = len(results)
        
        return {
            "total_chunks": sum(books.values()),
            "indexed_books": len(sources),
            "books": books,
            "vector_store": "Qdrant" if self.use_qdrant else "ChromaDB"
        }

# ─────────────────────────────── CLI ──────────────────────────────── #

def main():
    """Пример использования сервиса."""
    import typer
    from book_compiler import extract_text
    
    app = typer.Typer()
    
    @app.command()
    def index(
        book_path: Path = typer.Argument(..., help="Путь к книге (PDF/DOCX/TXT)"),
        collection: str = typer.Option("long_books", help="Название коллекции"),
        qdrant_path: Optional[Path] = typer.Option(None, help="Путь к Qdrant БД"),
        use_chroma: bool = typer.Option(False, help="Принудительно использовать ChromaDB"),
    ):
        """Индексирует книгу в векторной БД."""
        service = LongBookService(
            collection_name=collection,
            qdrant_path=qdrant_path,
            use_qdrant=not use_chroma
        )
        text = extract_text(book_path)
        service.index_book(text, source=book_path.stem)
        print(f"[bold green]✓ Книга проиндексирована![/bold green]")
    
    @app.command()
    def search_cmd(
        query: str = typer.Argument(..., help="Поисковый запрос"),
        n_results: int = typer.Option(5, help="Количество результатов"),
        collection: str = typer.Option("long_books", help="Название коллекции"),
        source: Optional[str] = typer.Option(None, help="Фильтр по источнику"),
    ):
        """Поиск по индексированным книгам."""
        service = LongBookService(collection_name=collection)
        results = service.search(query, n_results=n_results, source_filter=source)
        
        print(f"\n[bold]Найдено {len(results)} результатов:[/bold]\n")
        for i, result in enumerate(results, 1):
            print(f"[cyan]{i}. Score: {result['score']:.3f}[/cyan]")
            print(f"   Источник: {result['metadata'].get('source', 'неизвестно')}")
            print(f"   Текст: {result['text'][:200]}...\n")
    
    @app.command()
    def rag(
        query: str = typer.Argument(..., help="Вопрос для RAG"),
        n_results: int = typer.Option(5, help="Количество результатов для контекста"),
        collection: str = typer.Option("long_books", help="Название коллекции"),
        source: Optional[str] = typer.Option(None, help="Фильтр по источнику"),
    ):
        """RAG-запрос с использованием OpenRouter."""
        service = LongBookService(collection_name=collection)
        response = service.rag_query(query, n_results=n_results, source_filter=source)
        print(f"\n[bold green]Ответ:[/bold green]\n{response}\n")
    
    @app.command()
    def stats(
        collection: str = typer.Option("long_books", help="Название коллекции"),
    ):
        """Статистика по индексу."""
        service = LongBookService(collection_name=collection)
        stats = service.get_stats()
        print(f"\n[bold]Статистика индекса:[/bold]")
        print(f"Векторное хранилище: {stats['vector_store']}")
        print(f"Всего чанков: {stats['total_chunks']}")
        print(f"Проиндексировано книг: {stats['indexed_books']}")
        print(f"\nКниги:")
        for book, chunks in stats['books'].items():
            print(f"  • {book}: {chunks} чанков")
    
    app()

if __name__ == "__main__":
    main()