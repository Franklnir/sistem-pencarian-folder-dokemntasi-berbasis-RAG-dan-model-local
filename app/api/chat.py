import logging
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from app.llm.manager import get_llm_manager
from app.database.repository import get_repository
from app.retrieval.hybrid import HybridRetriever

logger = logging.getLogger("ai_file_search.api.chat")
chat_router = APIRouter(prefix="/api", tags=["chat"])

# Mode configurations: controls LLM behavior per mode
MODE_CONFIG = {
    "fast": {
        "max_tokens": 180,
        "temperature": 0.25,
        "context_chunks": 3,
        "label": "⚡ Cepat"
    },
    "balance": {
        "max_tokens": 420,
        "temperature": 0.35,
        "context_chunks": 5,
        "label": "⚖️ Balance"
    },
    "thinking": {
        "max_tokens": 800,
        "temperature": 0.4,
        "context_chunks": 8,
        "label": "🧠 Thinking"
    }
}


class AskRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000, description="Pertanyaan untuk AI")
    file_id: Optional[int] = Field(None, description="ID file spesifik (opsional)")
    top_k: int = Field(5, ge=1, le=20, description="Jumlah potongan dokumen rujukan")
    mode: Literal["fast", "balance", "thinking"] = Field("balance", description="Mode jawaban: fast, balance, thinking")
    doc_chat: bool = Field(False, description="Apakah dari panel Document Chat (wajib file_id)")


class AskResponse(BaseModel):
    answer: str
    model: str
    mode: str = "balance"
    mode_label: str = "⚖️ Balance"
    duration_s: float = 0.0
    tokens_used: int = 0
    sources: List[Dict[str, Any]] = []


class SwitchModelRequest(BaseModel):
    model_name: str = Field(..., description="Nama file model .gguf yang ingin diaktifkan")


@chat_router.get("/llm/status")
def get_model_status():
    """Mendapatkan status ketersediaan model AI lokal Qwen 2.5."""
    manager = get_llm_manager()
    return manager.get_status()


@chat_router.get("/llm/models")
def get_available_models():
    """Mendapatkan daftar katalog model AI lokal dan status instalasinya."""
    manager = get_llm_manager()
    return manager.list_models()


@chat_router.post("/llm/switch")
def switch_active_model(req: SwitchModelRequest):
    """Beralih ke model AI lokal pilihan (misal: 0.5B vs 1.5B) secara instan."""
    manager = get_llm_manager()
    try:
        return manager.switch_model(req.model_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@chat_router.post("/llm/download")
def trigger_model_download():
    """Memulai pengunduhan model AI lokal Qwen 2.5 di latar belakang."""
    manager = get_llm_manager()
    res = manager.start_download_async()
    return res


@chat_router.post("/chat/ask", response_model=AskResponse)
def ask_document_ai(req: AskRequest):
    """
    Tanya Dokumen: Menggunakan model lokal Qwen 2.5 (100% offline & $0)
    untuk menjawab pertanyaan berdasarkan dokumen yang diindeks.

    Mendukung 3 mode:
    - fast: jawaban ringkas & cepat (160 tokens, 3 context chunks)
    - balance: jawaban standar & presisi (384 tokens, 5 context chunks)
    - thinking: jawaban mendalam, terstruktur & analitis (768 tokens, 8 context chunks)
    """
    manager = get_llm_manager()
    repo = get_repository()

    mode_cfg = MODE_CONFIG.get(req.mode, MODE_CONFIG["balance"])
    num_chunks = max(mode_cfg["context_chunks"], req.top_k if req.top_k > mode_cfg["context_chunks"] else mode_cfg["context_chunks"])

    # Document Chat mode: WAJIB punya file_id
    if req.doc_chat and not req.file_id:
        raise HTTPException(
            status_code=400,
            detail="Panel Chat Dokumen membutuhkan dokumen terpilih. Silakan pilih dokumen terlebih dahulu."
        )

    context_chunks: List[Dict[str, Any]] = []

    if req.file_id:
        # User bertanya spesifik tentang SATU dokumen
        file_rec = repo.get_file_by_id(req.file_id)
        if not file_rec:
            raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")

        from app.embedding.model import get_embedding_manager
        embedder = get_embedding_manager()
        query_vec = embedder.encode_query(req.query)

        chunks = repo.get_relevant_chunks_for_file(
            file_id=req.file_id,
            query_embedding=query_vec,
            limit=num_chunks
        )
        if not chunks:
            return AskResponse(
                answer="Dokumen ini belum memiliki teks yang terindeks atau masih dalam antrean pemrosesan.",
                model="SENA Assistant",
                mode=req.mode,
                mode_label=mode_cfg["label"],
                sources=[]
            )

        for c in chunks:
            context_chunks.append({
                "file_id": file_rec.id,
                "filename": file_rec.filename,
                "path": file_rec.path,
                "content": c.get("text", ""),
                "score": c.get("score", 1.0),
                "page_no": c.get("page_no")
            })

    else:
        # User bertanya lintas dokumen: Cari via Hybrid Retriever
        retriever = HybridRetriever()
        results = retriever.search(query=req.query, top_k=num_chunks)

        if not results:
            return AskResponse(
                answer="Tidak ditemukan dokumen yang relevan dengan kata kunci Anda. Coba kata kunci atau konsep yang berbeda.",
                model="SENA Assistant",
                mode=req.mode,
                mode_label=mode_cfg["label"],
                sources=[]
            )

        NOISE_FILENAMES = {
            "top_level.txt", "sha256sums.txt", "cmakelists.txt", "cmakecache.txt",
            "targetdirectories.txt", "labels.txt", "exclude.txt", "license.txt",
            "do_not_use_on_4mb.txt"
        }

        for r in results:
            fn = r.get("filename", "")
            if fn.lower() in NOISE_FILENAMES:
                continue

            chunk_text = r.get("best_chunk_text") or r.get("snippet", "")
            chunk_clean = chunk_text.strip()
            # Abaikan chunk yang terlalu pendek atau hanya token internal library
            if len(chunk_clean) < 25 or (chunk_clean.startswith("_") and len(chunk_clean) < 100):
                continue

            context_chunks.append({
                "file_id": r.get("file_id"),
                "filename": fn,
                "path": r.get("path", ""),
                "content": chunk_clean,
                "score": r.get("score", 0.0),
                "page_no": r.get("page_no")
            })
            if len(context_chunks) >= num_chunks:
                break

    # Generate jawaban dari LLM lokal dengan mode yang dipilih
    res = manager.generate_answer(
        query=req.query,
        context_chunks=context_chunks,
        max_tokens=mode_cfg["max_tokens"],
        temperature=mode_cfg["temperature"],
        mode=req.mode
    )

    model_name_str = "Qwen 2.5 0.5B (468 MB)" if "0.5b" in manager.model_filename.lower() else "Qwen 2.5 1.5B (1.06 GB)"

    return AskResponse(
        answer=res.get("answer", ""),
        model=model_name_str,
        mode=req.mode,
        mode_label=mode_cfg["label"],
        duration_s=res.get("duration_s", 0.0),
        tokens_used=res.get("tokens_used", 0),
        sources=res.get("sources", [])
    )
