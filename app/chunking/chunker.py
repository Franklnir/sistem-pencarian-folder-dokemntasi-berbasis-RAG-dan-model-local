import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class DocumentChunk(BaseModel):
    chunk_index: int
    text: str
    page_no: Optional[int] = None
    token_count: int = 0


class DocumentChunker:
    """
    Splits extracted document sections into bounded chunks.
    Target: ~500 tokens with ~75 tokens overlap.
    Preserves page numbers where available.
    """

    def __init__(self, target_tokens: int = 500, overlap_tokens: int = 75):
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        # Heuristic ratio: ~1 token is approx 0.75 words, so words = tokens * 0.75
        self.target_words = max(20, int(target_tokens * 0.75))
        self.overlap_words = max(5, int(overlap_tokens * 0.75))

    def _estimate_tokens(self, text: str) -> int:
        # Approximate token count: word count / 0.75 or whitespace split
        words = text.split()
        return int(len(words) / 0.75) if words else 0

    def chunk_extracted_sections(self, sections: List[Dict[str, Any]]) -> List[DocumentChunk]:
        """
        Takes extracted sections (e.g. from PDF pages or docx paragraphs)
        and returns a unified list of DocumentChunks.
        """
        all_chunks: List[DocumentChunk] = []
        global_index = 0

        for section in sections:
            raw_text = section.get("text", "")
            page_no = section.get("page_no")
            if not raw_text or not raw_text.strip():
                continue

            cleaned_text = re.sub(r"[ \t]+", " ", raw_text).strip()
            # Split into paragraphs/sentences
            paragraphs = [p.strip() for p in cleaned_text.split("\n") if p.strip()]
            if not paragraphs:
                continue

            words = cleaned_text.split()
            if len(words) <= self.target_words:
                all_chunks.append(DocumentChunk(
                    chunk_index=global_index,
                    text=cleaned_text,
                    page_no=page_no,
                    token_count=self._estimate_tokens(cleaned_text)
                ))
                global_index += 1
            else:
                # Sliding window over words
                start = 0
                step = self.target_words - self.overlap_words
                if step <= 0:
                    step = self.target_words // 2 or 1

                while start < len(words):
                    end = min(start + self.target_words, len(words))
                    chunk_words = words[start:end]
                    chunk_str = " ".join(chunk_words)

                    all_chunks.append(DocumentChunk(
                        chunk_index=global_index,
                        text=chunk_str,
                        page_no=page_no,
                        token_count=self._estimate_tokens(chunk_str)
                    ))
                    global_index += 1

                    if end >= len(words):
                        break
                    start += step

        return all_chunks
