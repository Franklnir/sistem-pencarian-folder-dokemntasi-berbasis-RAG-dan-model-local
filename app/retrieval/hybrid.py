import re
from typing import List, Dict, Any, Optional, Set
from app.retrieval.bm25 import LexicalRetriever, tokenize
from app.retrieval.semantic import SemanticRetriever


class HybridRetriever:
    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k
        self.lexical = LexicalRetriever()
        self.semantic = SemanticRetriever()

    def _create_snippet(self, text: str, query: str, max_chars: int = 180) -> str:
        """Generates a clean contextual snippet around query keywords."""
        if not text:
            return ""

        clean = re.sub(r"\s+", " ", text).strip()
        query_words = [w for w in tokenize(query) if len(w) > 2]

        best_pos = -1
        for qw in query_words:
            m = re.search(r"\b" + re.escape(qw) + r"\b", clean, re.IGNORECASE)
            if m:
                best_pos = m.start()
                break

        if best_pos == -1 or len(clean) <= max_chars:
            snippet = clean[:max_chars]
            return snippet + ("..." if len(clean) > max_chars else "")

        start = max(0, best_pos - 40)
        end = min(len(clean), start + max_chars)
        snippet = clean[start:end].strip()

        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(clean) else ""
        return f"{prefix}{snippet}{suffix}"

    def search(
        self,
        query: str,
        top_k: int = 5,
        extensions: Optional[List[str]] = None,
        folder_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid lexical + semantic retrieval, combines ranks via RRF,
        groups by file_id, and returns Top-K files.
        """
        candidate_pool = max(top_k * 4, 30)

        lexical_candidates = self.lexical.search(
            query=query,
            limit=candidate_pool,
            extensions=extensions,
            folder_id=folder_id
        )

        semantic_candidates = self.semantic.search(
            query=query,
            limit=candidate_pool,
            extensions=extensions,
            folder_id=folder_id
        )

        # Map candidate chunks by chunk_id
        chunk_map: Dict[int, Dict[str, Any]] = {}
        rrf_scores: Dict[int, float] = {}
        chunk_source: Dict[int, Set[str]] = {}

        # 1. Process Lexical
        for cand in lexical_candidates:
            cid = cand["chunk_id"]
            chunk_map[cid] = cand
            chunk_source.setdefault(cid, set()).add("lexical")
            rrf_score = 1.0 / (self.rrf_k + cand["lexical_rank"])
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + rrf_score

        # 2. Process Semantic
        for cand in semantic_candidates:
            cid = cand["chunk_id"]
            if cid not in chunk_map:
                chunk_map[cid] = cand
            chunk_source.setdefault(cid, set()).add("semantic")
            rrf_score = 1.0 / (self.rrf_k + cand["vector_rank"])
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + rrf_score

        # 3. Group by file_id to avoid one file dominating results
        file_matches: Dict[int, Dict[str, Any]] = {}

        for cid, total_rrf in rrf_scores.items():
            cand = chunk_map[cid]
            fid = cand["file_id"]

            sources = chunk_source[cid]
            if "lexical" in sources and "semantic" in sources:
                match_type = "hybrid"
            elif "semantic" in sources:
                match_type = "semantic"
            else:
                match_type = "lexical"

            if fid not in file_matches:
                file_matches[fid] = {
                    "file_id": fid,
                    "filename": cand["filename"],
                    "path": cand["path"],
                    "extension": cand["extension"],
                    "best_score": total_rrf,
                    "match_type": match_type,
                    "page_no": cand.get("page_no"),
                    "best_chunk_text": cand.get("text", "")
                }
            else:
                # Update if better chunk found
                curr = file_matches[fid]
                if total_rrf > curr["best_score"]:
                    curr["best_score"] = total_rrf
                    curr["match_type"] = match_type
                    curr["page_no"] = cand.get("page_no")
                    curr["best_chunk_text"] = cand.get("text", "")

        # 4. Sort files by score descending
        sorted_files = sorted(file_matches.values(), key=lambda x: x["best_score"], reverse=True)
        top_files = sorted_files[:top_k]

        # 5. Normalize score to 0.0 - 1.0 scale and format output
        max_possible_rrf = (1.0 / (self.rrf_k + 1)) * 2  # rank 1 in both lexical and semantic
        results = []
        for f in top_files:
            norm_score = min(1.0, f["best_score"] / max_possible_rrf)
            # Round score for clean presentation
            norm_score = round(max(0.1, norm_score), 2)

            results.append({
                "file_id": f["file_id"],
                "filename": f["filename"],
                "path": f["path"],
                "extension": f["extension"],
                "score": norm_score,
                "match_type": f["match_type"],
                "page_no": f["page_no"],
                "snippet": self._create_snippet(f["best_chunk_text"], query),
                "best_chunk_text": f["best_chunk_text"]
            })

        return results
