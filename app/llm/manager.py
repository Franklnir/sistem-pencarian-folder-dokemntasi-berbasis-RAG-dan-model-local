import os
import sys
import time
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.config import settings

logger = logging.getLogger("ai_file_search.llm")

# Try to import llama_cpp gracefully
try:
    import llama_cpp
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    llama_cpp = None
    LLAMA_CPP_AVAILABLE = False


# Known model catalog for SENA
MODEL_CATALOG = {
    "qwen2.5-0.5b-instruct-q4_k_m.gguf": {
        "name": "Qwen 2.5 0.5B Instruct",
        "tag": "⚡ Ultra-Cepat (~468 MB)",
        "description": "Model super ringan dengan respon 3-5 detik di CPU. Sangat presisi di atas Hybrid RAG.",
        "size_bytes": 491400032,
        "size_mb": 468.6,
        "repo_id": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        "recommended": True
    },
    "qwen2.5-1.5b-instruct-q4_k_m.gguf": {
        "name": "Qwen 2.5 1.5B Instruct",
        "tag": "🧠 Deep Synthesis (~1.06 GB)",
        "description": "Model standar dengan penalaran mendalam dan sintesis dokumen komprehensif.",
        "size_bytes": 1117320736,
        "size_mb": 1065.6,
        "repo_id": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "recommended": False
    }
}


class LLMManager:
    _instance: Optional["LLMManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.model_dir = Path(settings.LLM_MODEL_DIR)
        self.model_filename = settings.LLM_MODEL_NAME
        self.model_path = self.model_dir / self.model_filename
        self.repo_id = settings.LLM_REPO_ID

        self._llm = None
        self._llm_lock = threading.Lock()
        self._is_loading = False

        # Download tracking state
        self._is_downloading = False
        self._download_progress_pct = 0
        self._download_bytes_downloaded = 0
        self._download_total_bytes = 1117320736
        self._download_error = None
        self._download_thread: Optional[threading.Thread] = None

    @classmethod
    def get_instance(cls) -> "LLMManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def list_models(self) -> List[Dict[str, Any]]:
        """Return list of models with installation and active status."""
        result = []
        seen_files = set()
        for filename, info in MODEL_CATALOG.items():
            seen_files.add(filename)
            file_path = self.model_dir / filename
            is_installed = file_path.is_file() and (file_path.stat().st_size > 50 * 1024 * 1024)
            size_mb = round(file_path.stat().st_size / (1024 * 1024), 1) if file_path.is_file() else info["size_mb"]
            is_active = (self.model_filename == filename)
            result.append({
                "filename": filename,
                "name": info["name"],
                "tag": info["tag"],
                "description": info["description"],
                "size_mb": size_mb,
                "repo_id": info["repo_id"],
                "recommended": info["recommended"],
                "is_installed": is_installed,
                "is_active": is_active,
                "is_loaded": is_active and (self._llm is not None)
            })

        if self.model_dir.is_dir():
            for f in self.model_dir.glob("*.gguf"):
                if f.name not in seen_files:
                    size_mb = round(f.stat().st_size / (1024 * 1024), 1)
                    is_active = (self.model_filename == f.name)
                    result.append({
                        "filename": f.name,
                        "name": f.name.replace(".gguf", "").replace("-", " ").title(),
                        "tag": f"Custom ({size_mb} MB)",
                        "description": "Custom local GGUF model",
                        "size_mb": size_mb,
                        "repo_id": "",
                        "recommended": False,
                        "is_installed": True,
                        "is_active": is_active,
                        "is_loaded": is_active and (self._llm is not None)
                    })
        return result

    def switch_model(self, model_name: str) -> Dict[str, Any]:
        """Switch active model dynamically."""
        target_path = self.model_dir / model_name
        if not target_path.is_file() or target_path.stat().st_size < 50 * 1024 * 1024:
            raise FileNotFoundError(f"Model '{model_name}' belum diunduh ke folder models.")

        with self._llm_lock:
            if self._llm is not None:
                del self._llm
                self._llm = None
                import gc
                gc.collect()
                logger.info("Unloaded previous LLM model from memory.")

            self.model_filename = model_name
            self.model_path = target_path
            if model_name in MODEL_CATALOG:
                self.repo_id = MODEL_CATALOG[model_name]["repo_id"]

            logger.info(f"Switched active model to: {model_name}")

        return {
            "status": "ok",
            "model_name": self.model_filename,
            "message": f"Berhasil beralih ke model {model_name}."
        }

    def get_status(self) -> Dict[str, Any]:
        """Return the current status of the LLM library, model file, and download."""
        file_exists = self.model_path.is_file()
        file_size_mb = 0.0
        if file_exists:
            try:
                file_size_mb = round(self.model_path.stat().st_size / (1024 * 1024), 2)
            except OSError:
                pass

        return {
            "library_installed": LLAMA_CPP_AVAILABLE,
            "model_name": self.model_filename,
            "model_path": str(self.model_path),
            "model_exists": file_exists and (file_size_mb > 50),
            "model_size_mb": file_size_mb,
            "is_loaded": self._llm is not None,
            "is_loading": self._is_loading,
            "is_downloading": self._is_downloading,
            "download_progress_pct": self._download_progress_pct,
            "download_error": self._download_error,
            "available_models": self.list_models()
        }

    def start_download_async(self) -> Dict[str, Any]:
        """Start downloading the GGUF model in background if not already downloading or present."""
        if self.model_path.is_file() and self.model_path.stat().st_size > 1000 * 1024 * 1024:
            return {"status": "already_downloaded", "message": "Model file is already present."}

        with self._lock:
            if self._is_downloading:
                return {"status": "in_progress", "progress_pct": self._download_progress_pct}

            self._is_downloading = True
            self._download_error = None
            self._download_progress_pct = 0

            self._download_thread = threading.Thread(
                target=self._run_download,
                name="llm_model_downloader",
                daemon=True
            )
            self._download_thread.start()

        return {"status": "started", "message": f"Downloading {self.model_filename} from Hugging Face..."}

    def _run_download(self):
        """Worker thread to download model via huggingface_hub or direct stream."""
        logger.info(f"Starting background download of {self.model_filename}...")
        try:
            import urllib.request
            url = f"https://huggingface.co/{self.repo_id}/resolve/main/{self.model_filename}"
            tmp_path = self.model_path.with_suffix(".downloading")

            def report_progress(block_num, block_size, total_size):
                if total_size > 0:
                    downloaded = block_num * block_size
                    self._download_bytes_downloaded = downloaded
                    self._download_total_bytes = total_size
                    self._download_progress_pct = min(100, int((downloaded / total_size) * 100))

            opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
            urllib.request.install_opener(opener)

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "SENA-Local-AI/1.0"}
            )

            with urllib.request.urlopen(req) as resp, open(tmp_path, "wb") as f_out:
                total_size = int(resp.headers.get("content-length", self._download_total_bytes))
                self._download_total_bytes = total_size
                downloaded = 0
                block_size = 1024 * 512  # 512 KB chunks

                while True:
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    downloaded += len(chunk)
                    self._download_bytes_downloaded = downloaded
                    self._download_progress_pct = min(100, int((downloaded / total_size) * 100))

            # Rename once completed
            if tmp_path.exists():
                if self.model_path.exists():
                    self.model_path.unlink()
                tmp_path.rename(self.model_path)

            self._download_progress_pct = 100
            self._is_downloading = False
            logger.info(f"Model {self.model_filename} downloaded successfully.")

        except Exception as e:
            logger.error(f"Download failed: {e}", exc_info=True)
            self._download_error = str(e)
            self._is_downloading = False

    def load_model(self):
        """Lazy load the llama.cpp model into memory."""
        if not LLAMA_CPP_AVAILABLE:
            raise RuntimeError(
                "Library 'llama-cpp-python' belum terpasang. "
                "Silakan jalankan: pip install llama-cpp-python"
            )

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"File model '{self.model_filename}' belum diunduh ke {self.model_dir}."
            )

        with self._llm_lock:
            if self._llm is not None:
                return self._llm

            self._is_loading = True
            logger.info(f"Loading local LLM model from {self.model_path}...")
            start_t = time.perf_counter()

            try:
                self._llm = llama_cpp.Llama(
                    model_path=str(self.model_path),
                    n_ctx=settings.LLM_CONTEXT_SIZE,
                    n_threads=settings.LLM_THREADS,
                    n_batch=512,
                    verbose=False
                )
                dur = round((time.perf_counter() - start_t), 2)
                logger.info(f"Local LLM model loaded successfully in {dur}s.")
                return self._llm
            except Exception as e:
                logger.error(f"Failed to load Llama model: {e}", exc_info=True)
                raise
            finally:
                self._is_loading = False

    def generate_answer(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        max_tokens: int = 256,
        temperature: float = 0.2,
        mode: str = "balance"
    ) -> Dict[str, Any]:
        """
        Generate an accurate answer in Indonesian based on provided document chunks.
        Supports 3 modes: fast, balance, thinking — each with different system prompts.
        """
        if not LLAMA_CPP_AVAILABLE:
            return {
                "answer": (
                    "⚠️ Fitur Tanya AI Dokumen membutuhkan library `llama-cpp-python`. "
                    "Pastikan dependensi telah terpasang dengan menjalankan `pip install llama-cpp-python`."
                ),
                "model": "Not Available",
                "tokens_used": 0,
                "sources": []
            }

        if not self.model_path.is_file() or self.model_path.stat().st_size < 100 * 1024 * 1024:
            return {
                "answer": (
                    "⏳ Model AI lokal (`qwen2.5-1.5b-instruct-q4_k_m.gguf`) sedang diunduh atau belum selesai. "
                    "Setelah unduhan selesai, Anda bisa bertanya apa saja mengenai isi dokumen Anda secara offline."
                ),
                "model": "Pending Download",
                "tokens_used": 0,
                "sources": []
            }

        # Ensure model is loaded
        llm = self.load_model()

        # Mode-specific system prompts (Natural Perplexity Synthesis)
        if mode == "fast":
            system_instruction = (
                "Anda adalah asisten AI cerdas SENA (Search Engine & Knowledge Hub).\n"
                "Tugas Anda: Berikan KESIMPULAN NARATIF YANG NATURAL, singkat, dan jelas dalam Bahasa Indonesia "
                "berdasarkan topik pencarian dan isi dokumen yang ditemukan.\n\n"
                "ATURAN UTAMA:\n"
                "1. MENYIMPULKAN, BUKAN MENYALIN: Dilarang menyalin teks mentah dokumen atau membuat daftar potongan kutipan. "
                "Rangkum makna intinya dengan bahasa Anda sendiri yang mengalir alami.\n"
                "2. JELASKAN MAKNA TEMUAN: Hubungkan langsung isi dokumen dengan apa yang dicari pengguna dalam 2-3 kalimat lugas.\n"
                "3. SITASI ALAMI: Sematkan nomor sitasi [1], [2] di akhir kalimat fakta secara rapi.\n"
                "4. JIKA TIDAK COCOK: Bila dokumen tidak memuat topik yang dicari, jelaskan bahwa informasi tidak ditemukan."
            )
            max_content_len = 800
        elif mode == "thinking":
            system_instruction = (
                "Anda adalah asisten analis AI cerdas SENA bergaya Perplexity AI Pro.\n"
                "Tugas Anda: Berikan SINTESIS MENDALAM, komprehensif, terstruktur, dan naratif dalam Bahasa Indonesia "
                "yang menganalisis isi dokumen-dokumen temuan secara mendalam.\n\n"
                "PEDOMAN PENULISAN:\n"
                "1. BAHASA ALAMI & ANALITIS: Tuliskan penjelasan yang mengalir secara alami seperti analis profesional. "
                "Dilarang keras sekadar menyalin ulang teks dokumen atau mencetak potongan kutipan mentah.\n"
                "2. STRUKTUR SISTEMATIS:\n"
                "   - Paragraf Pembuka: Berikan ringkasan eksekutif mengenai apa inti topik dan temuan dokumen.\n"
                "   - Poin-Poin Analisis: Jabarkan rincian konsep, isu, fenomena, atau solusi yang ada di dalam dokumen secara terstruktur.\n"
                "   - Kesimpulan Akhir: Rangkuman penutup yang tajam.\n"
                "3. SITASI: Cantumkan sitasi nomor dokumen [1], [2] pada kalimat-kalimat temuan data.\n"
                "4. RELEVANSI: Hanya bahas dokumen yang benar-benar relevan dengan pencarian pengguna."
            )
            max_content_len = 2000
        else:  # balance (default)
            system_instruction = (
                "Anda adalah asisten AI cerdas SENA (Search Engine & Knowledge Hub).\n"
                "Tugas Anda: Membuat KESIMPULAN NARATIF YANG NATURAL, jelas, dan terstruktur dalam Bahasa Indonesia "
                "mengenai isi dokumen yang ditemukan di komputer pengguna.\n\n"
                "PEDOMAN WAJIB (SANGAT PENTING):\n"
                "1. MENYIMPULKAN, BUKAN MENYALIN: DILARANG KERAS menyalin teks dokumen secara mentah atau membuat daftar kutipan mentah. "
                "Anda wajib merangkum dan menjelaskan maknanya menggunakan bahasa Anda sendiri yang mengalir alami dan mudah dipahami.\n"
                "2. JAWAB MAKSUD PENCARIAN: Jelaskan inti informasi dokumen dan bagaimana kaitannya dengan topik yang dicari pengguna. "
                "Jelaskan apa tujuan, isu, atau pembahasan utama dokumen tersebut.\n"
                "3. FORMAT JAWABAN:\n"
                "   - Awali dengan 1 paragraf kesimpulan utama yang alami dan informatif.\n"
                "   - Uraikan poin-poin penting atau temuan utama menggunakan bullet points (-) yang jelas dan padat.\n"
                "4. SITASI HALUS: Cantumkan nomor sitasi seperti [1] atau [2] di bagian akhir kalimat fakta yang merujuk pada dokumen terkait.\n"
                "5. JIKA TIDAK COCOK: Jika dokumen yang ditemukan tidak relevan dengan topik pencarian, sampaikan secara ramah bahwa dokumen yang sesuai belum ditemukan."
            )
            max_content_len = 1200

        # Format context from top chunks based on mode
        context_text = ""
        sources = []
        num_chunks = len(context_chunks)
        for i, chunk in enumerate(context_chunks, 1):
            fn = chunk.get("filename", f"Dokumen_{i}")
            content = chunk.get("content", "").strip()
            # Clean excessive whitespace
            clean_content = " ".join(content.split())
            if len(clean_content) > max_content_len:
                clean_content = clean_content[:max_content_len] + "..."
            
            page_info = f"Hal. {chunk.get('page_no')}" if chunk.get("page_no") else "Teks Utama"
            context_text += f"\n[Dokumen {i}: {fn} ({page_info})]\n{clean_content}\n"
            sources.append({
                "source_index": i,
                "file_id": chunk.get("file_id"),
                "filename": fn,
                "path": chunk.get("path", ""),
                "page_no": chunk.get("page_no"),
                "score": round(float(chunk.get("score", 0.0)), 4)
            })

        user_content = (
            f'Topik / Pertanyaan Pencarian: "{query}"\n\n'
            f"Konteks Isi Dokumen yang Ditemukan di Komputer:\n{context_text}\n\n"
            f"Instruksi: Buatlah KESIMPULAN NARATIF YANG NATURAL dalam Bahasa Indonesia yang menjelaskan makna isi dokumen di atas terkait '{query}'. "
            f"Rangkum dengan bahasa Anda sendiri yang mengalir (jangan menyalin mentah potongan teks dokumen). Sertakan nomor sitasi [1], [2] pada kalimat fakta yang relevan."
        )

        prompt = (
            f"<|im_start|>system\n{system_instruction}<|im_end|>\n"
            f"<|im_start|>user\n{user_content}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        with self._llm_lock:
            start_t = time.perf_counter()
            response = llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9,
                repeat_penalty=1.15,
                stop=["<|im_end|>", "<|endoftext|>"],
                echo=False
            )
            duration_s = round(time.perf_counter() - start_t, 2)

        raw_text = response["choices"][0]["text"].strip()
        tokens = response.get("usage", {}).get("total_tokens", 0)

        # Human-friendly model display name
        display_model = self.model_filename.replace(".gguf", "").replace("-", " ").title()

        logger.info(f"LLM [{mode}] generated answer in {duration_s}s ({tokens} tokens).")

        return {
            "answer": raw_text,
            "model": display_model,
            "duration_s": duration_s,
            "tokens_used": tokens,
            "sources": sources
        }


def get_llm_manager() -> LLMManager:
    return LLMManager.get_instance()
