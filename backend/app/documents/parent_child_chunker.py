"""
Parent-Child Chunking - hierarchiczne chunking dla lepszego zachowania kontekstu
"""
from typing import List, Dict, Any
from app.documents.chunker import DocumentChunker


class ParentChildChunker:
    """
    Hierarchiczne chunking:
    - Parent = cały dokument lub duże sekcje
    - Child = małe fragmenty dla precyzyjnego retrieval
    """
    
    def __init__(
        self,
        parent_chunk_size: int = 2000,
        child_chunk_size: int = 500,
        child_chunk_overlap: int = 100
    ):
        """
        Args:
            parent_chunk_size: Rozmiar parent chunk (większy dla kontekstu)
            child_chunk_size: Rozmiar child chunk (mniejszy dla precyzji)
            child_chunk_overlap: Overlap między child chunks
        """
        self.parent_chunk_size = parent_chunk_size
        self.child_chunker = DocumentChunker(
            chunk_size=child_chunk_size,
            chunk_overlap=child_chunk_overlap
        )
        self.parent_chunker = DocumentChunker(
            chunk_size=parent_chunk_size,
            chunk_overlap=parent_chunk_size // 4  # 25% overlap dla parent
        )
    
    def chunk_document(self, text: str, document_id: str = None) -> List[Dict[str, Any]]:
        """
        Dzieli dokument na parent i child chunks
        
        Args:
            text: Tekst dokumentu
            document_id: ID dokumentu
        
        Returns:
            Lista chunków z parent_id i metadata
        """
        # Tworzymy parent chunks (większe sekcje)
        parent_chunks = self.parent_chunker.chunk_text(text)
        
        all_chunks = []
        
        for parent_idx, parent_text in enumerate(parent_chunks):
            parent_id = f"{document_id}_parent_{parent_idx}" if document_id else f"parent_{parent_idx}"
            
            # Parent chunk
            parent_chunk = {
                "id": parent_id,
                "text": parent_text,
                "type": "parent",
                "parent_id": None,
                "chunk_index": parent_idx,
                "metadata": {
                    "chunk_size": len(parent_text),
                    "total_parents": len(parent_chunks)
                }
            }
            all_chunks.append(parent_chunk)
            
            # Child chunks z tego parent
            child_chunks = self.child_chunker.chunk_text(parent_text)
            
            for child_idx, child_text in enumerate(child_chunks):
                child_id = f"{parent_id}_child_{child_idx}"
                
                child_chunk = {
                    "id": child_id,
                    "text": child_text,
                    "type": "child",
                    "parent_id": parent_id,
                    "chunk_index": child_idx,
                    "parent_index": parent_idx,
                    "metadata": {
                        "chunk_size": len(child_text),
                        "parent_chunk_size": len(parent_text),
                        "total_children": len(child_chunks)
                    }
                }
                all_chunks.append(child_chunk)
        
        return all_chunks
    
    def get_parent_context(self, chunks: List[Dict[str, Any]], child_id: str) -> str:
        """
        Pobiera kontekst parent dla danego child chunk
        
        Args:
            chunks: Lista wszystkich chunków
            child_id: ID child chunk
        
        Returns:
            Tekst parent chunk
        """
        # Znajdujemy child chunk
        child_chunk = next((c for c in chunks if c["id"] == child_id), None)
        if not child_chunk or child_chunk["type"] != "child":
            return ""
        
        # Znajdujemy parent
        parent_id = child_chunk.get("parent_id")
        if not parent_id:
            return ""
        
        parent_chunk = next((c for c in chunks if c["id"] == parent_id), None)
        if parent_chunk:
            return parent_chunk["text"]
        
        return ""

