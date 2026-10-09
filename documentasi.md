# AI FILE SEARCH — Technical Architecture Specification v1.0

## 1. Tujuan
AI File Search adalah aplikasi pencarian dokumen lokal Windows berbasis semantic dan hybrid retrieval. Pengguna dapat mencari berdasarkan makna isi dokumen, misalnya `carikan PDF tentang keamanan jaringan`.

Core research:
- incremental semantic indexing
- hybrid lexical + vector retrieval
- efficient PostgreSQL/pgvector queries
- filesystem monitoring
- lightweight local web UI
- Windows Service

LLM dan RAG bukan dependency inti. Tidak ada training model dari nol.

## 2. Scope
### Didukung
- PDF
- DOCX
- TXT
- Folder Windows yang dipilih pengguna

### Di luar scope core
- image/video/audio search
- OCR
- multimodal embedding
- LLM answer generation
- chatbot
- model training dari nol

## 3. Arsitektur End-to-End
```text
Windows File System
       ↓
Watchdog File Watcher
       ↓ CREATE / MODIFY / DELETE / MOVE
Event Normalization
       ↓
Debounce + Deduplication Queue
       ↓
Incremental Ingestion
  ├─ extension validation
  ├─ file stability check
  ├─ SHA-256
  ├─ text extraction
  ├─ chunking
  └─ local embedding
       ↓
PostgreSQL + pgvector
       ↓
FastAPI
  ├─ lexical/BM25 or PostgreSQL FTS
  └─ vector similarity
       ↓
RRF Fusion
       ↓
File-level Top-K
       ↓
Jinja2 + Vanilla JS
```

## 4. Stack
| Layer | Teknologi |
|---|---|
| Backend | Python + FastAPI |
| Server | Uvicorn |
| Database | PostgreSQL |
| Vector | pgvector |
| Watcher | watchdog |
| PDF | PyMuPDF |
| DOCX | python-docx |
| TXT | Python I/O |
| Embedding | Sentence Transformers pretrained |
| Retrieval | BM25/PostgreSQL FTS + vector |
| Ranking | RRF |
| Frontend | Jinja2 + HTML/CSS + vanilla JS |
| Deployment | Windows Service |
| Container | Tidak diperlukan |

## 5. Struktur Project
```text
ai-file-search/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── search.py
│   │   ├── files.py
│   │   ├── folders.py
│   │   ├── indexing.py
│   │   └── health.py
│   ├── ingestion/
│   │   ├── watcher.py
│   │   ├── queue.py
│   │   ├── pipeline.py
│   │   └── hashing.py
│   ├── extractors/
│   │   ├── registry.py
│   │   ├── pdf.py
│   │   ├── docx.py
│   │   └── txt.py
│   ├── chunking/
│   │   └── chunker.py
│   ├── embedding/
│   │   └── model.py
│   ├── retrieval/
│   │   ├── bm25.py
│   │   ├── semantic.py
│   │   └── hybrid.py
│   ├── database/
│   │   ├── models.py
│   │   ├── repository.py
│   │   └── migrations/
│   ├── schemas/
│   │   ├── search.py
│   │   ├── files.py
│   │   └── folders.py
│   ├── templates/
│   │   ├── index.html
│   │   ├── results.html
│   │   └── settings.html
│   └── static/
│       ├── css/app.css
│       └── js/app.js
├── service/
│   └── ai_file_search_service.py
├── tests/
├── config/
├── data/
├── requirements.txt
└── README.md
```

## 6. Database Schema

### `files`
| Kolom | Tipe | Aturan |
|---|---|---|
| id | BIGINT | PK |
| path | TEXT | UNIQUE, canonical absolute path |
| filename | TEXT | nama file |
| extension | VARCHAR(16) | lowercase allowlist |
| size_bytes | BIGINT | >= 0 |
| modified_at | TIMESTAMPTZ | filesystem mtime |
| content_hash | CHAR(64) | SHA-256 |
| status | VARCHAR(16) | PENDING/PROCESSING/INDEXED/FAILED/DELETED |
| error_message | TEXT | nullable |
| indexed_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | timestamp |
| updated_at | TIMESTAMPTZ | timestamp |

### `document_chunks`
| Kolom | Tipe | Aturan |
|---|---|---|
| id | BIGINT | PK |
| file_id | BIGINT | FK → files ON DELETE CASCADE |
| page_no | INTEGER | nullable |
| chunk_index | INTEGER | urutan |
| text | TEXT | isi chunk |
| embedding | VECTOR(n) | dimensi model |
| token_count | INTEGER | opsional |
| created_at | TIMESTAMPTZ | timestamp |

### `monitored_folders`
| Kolom | Tipe |
|---|---|
| id | BIGINT PK |
| path | TEXT UNIQUE |
| enabled | BOOLEAN |
| created_at | TIMESTAMPTZ |
| updated_at | TIMESTAMPTZ |

## 7. Database Index
```sql
CREATE UNIQUE INDEX ux_files_path ON files(path);
CREATE INDEX ix_files_hash ON files(content_hash);
CREATE INDEX ix_files_status ON files(status);
CREATE INDEX ix_files_modified ON files(modified_at DESC);
CREATE INDEX ix_chunks_file_id ON document_chunks(file_id);

CREATE INDEX ix_chunks_embedding_hnsw
ON document_chunks USING hnsw (embedding vector_cosine_ops);
```
HNSW dipakai bila benchmark menunjukkan manfaat pada ukuran corpus. Untuk corpus kecil, exact search dapat lebih ringan.

## 8. Prinsip Query Efisien
- Jangan `SELECT *` pada search.
- Jangan mengambil semua embedding ke Python.
- Candidate retrieval harus dibatasi.
- Default `top_k=5`, maksimum `50`.
- Vector similarity dijalankan di pgvector.
- Lexical retrieval dijalankan di DB/retrieval engine.
- Snippet diambil dari chunk yang relevan.
- Embedding tidak dikirim ke browser.
- Gunakan parameterized SQL.
- Connection pool kecil dan terukur, misalnya 3–8 koneksi.
- Transaction dilakukan per file ingestion, bukan satu transaction seluruh folder.

## 9. Incremental Ingestion

### CREATE
```text
CREATE
→ normalize path
→ extension validation
→ stability check
→ SHA-256
→ compare existing hash
→ extract
→ chunk
→ batch embedding
→ transaction
→ INDEXED
```

### MODIFY
```text
MODIFY events
→ debounce by path
→ stability check
→ SHA-256
→ hash unchanged → metadata update/skip
→ hash changed → reindex file only
```

### MOVE/RENAME
Jika `content_hash` sama:
```text
UPDATE files
SET path = new_path,
    filename = new_filename
```
Tidak perlu extraction atau embedding.

### DELETE
```text
DELETE files
→ ON DELETE CASCADE
→ document_chunks ikut terhapus
```

## 10. File Stability Check
File baru dapat masih ditulis aplikasi lain:
```text
read size + mtime
→ wait stability window
→ read size + mtime
→ sama → process
→ berbeda → retry bounded
```
Tidak boleh retry tanpa batas.

## 11. Watcher dan Queue
Watchdog callback hanya memasukkan event ke queue. Extraction/embedding dilakukan worker.

```text
watchdog
→ normalize
→ per-path debounce
→ bounded queue
→ worker
→ pipeline
```

`WATCH_DEBOUNCE_MS` awal: `1000`.

Event storm harus di-coalesce sehingga banyak MODIFY tidak menjadi banyak embedding.

## 12. Extractor
| Format | Library | Output |
|---|---|---|
| PDF | PyMuPDF | text + page_no |
| DOCX | python-docx | paragraph/table text |
| TXT | Python I/O | text |

Extractor registry:
```text
.pdf  → PDFExtractor
.docx → DOCXExtractor
.txt  → TXTExtractor
```

## 13. Chunking
Nilai awal eksperimen:
- target ±500 token
- overlap ±75 token

Nilai final ditentukan dengan benchmark Precision/Recall/latency.

## 14. Embedding
Gunakan pretrained Sentence Transformers multilingual yang sesuai untuk Indonesia/Inggris.

Model:
- diload sekali saat startup
- query embedding satu kali per search
- ingestion menggunakan batch
- versi model disimpan
- pergantian model memerlukan reindex sesuai scope

## 15. Hybrid Retrieval
```text
Query
 ├── lexical retrieval
 └── semantic vector retrieval
          ↓
       RRF fusion
          ↓
      file grouping
          ↓
         Top-K
```

Lexical cocok untuk istilah exact, acronym, dan phrase. Semantic cocok untuk variasi bahasa dan kemiripan konsep.

### RRF
```text
RRF(d) = Σ 1 / (k + rank_i(d))
```
Nilai awal `k=60`.

Hasil akhir dikelompokkan pada level file agar satu file tidak memenuhi seluruh Top-K karena banyak chunk.

## 16. Search Pipeline
```text
POST /api/search
→ Pydantic validation
→ normalize query
→ query embedding
→ lexical candidates
→ vector candidates
→ RRF
→ group by file
→ Top-K
→ snippet
→ JSON
```

## 17. API

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/status` | status sistem |
| GET | `/api/folders` | monitored folders |
| POST | `/api/folders` | tambah folder |
| PATCH | `/api/folders/{id}` | enable/disable |
| DELETE | `/api/folders/{id}` | hapus monitoring |
| GET | `/api/files` | list file |
| GET | `/api/files/{id}` | detail |
| POST | `/api/search` | hybrid search |
| POST | `/api/index/rebuild` | full rebuild |
| POST | `/api/index/file/{id}` | reindex satu file |
| POST | `/api/index/resume` | resume jobs |

### `GET /api/health`
```json
{
  "status": "ok",
  "service": "ai-file-search",
  "version": "1.0.0"
}
```

### `GET /api/status`
```json
{
  "service": "running",
  "watcher": "running",
  "database": "ok",
  "embedding_model": "ready",
  "indexed_files": 1234,
  "indexed_chunks": 45678,
  "pending_jobs": 2,
  "failed_files": 1,
  "last_indexed_at": "2026-09-21T18:00:00+07:00"
}
```

### `POST /api/folders`
```json
{
  "path": "C:\Users\User\Downloads"
}
```
Validasi:
- absolute Windows path
- canonicalized
- exists
- directory
- tidak duplicate
- bukan critical system directory
- extension allowlist tetap berlaku

### `PATCH /api/folders/{id}`
```json
{
  "enabled": false
}
```

### `DELETE /api/folders/{id}`
Hanya menghapus konfigurasi monitoring. Tidak menghapus file fisik.

### `GET /api/files`
Contoh:
```text
GET /api/files?page=1&page_size=25&extension=.pdf
```
Validasi:
- `page >= 1`
- `page_size = 1..100`
- extension allowlist

### `GET /api/files/{id}`
Mengembalikan metadata, bukan seluruh isi dokumen.

### `POST /api/search`
Request:
```json
{
  "query": "carikan PDF tentang keamanan jaringan",
  "top_k": 5,
  "extensions": [".pdf"],
  "folder_id": null
}
```
Response:
```json
{
  "query": "carikan PDF tentang keamanan jaringan",
  "took_ms": 42,
  "results": [
    {
      "file_id": 18,
      "filename": "Network Security.pdf",
      "path": "C:\Users\User\Documents\Network Security.pdf",
      "extension": ".pdf",
      "score": 0.91,
      "match_type": "hybrid",
      "page_no": 12,
      "snippet": "Keamanan jaringan..."
    }
  ]
}
```

### `POST /api/index/file/{id}`
```json
{
  "job_id": "idx_01...",
  "file_id": 18,
  "status": "QUEUED"
}
```

### `POST /api/index/rebuild`
Request:
```json
{
  "confirm": true,
  "scope": "all"
}
```
Rebuild harus asynchronous.

### `POST /api/index/resume`
```json
{
  "status": "QUEUED",
  "count": 7
}
```

## 18. Validation
- query tidak boleh kosong
- query memiliki maximum length
- `top_k` 1–50
- extension hanya allowlist
- folder_id positive integer atau null
- path harus canonical dan valid
- rebuild wajib `confirm=true`
- SQL selalu parameterized

## 19. Request ID
Setiap HTTP request memiliki:
```text
X-Request-ID: req_01J...
```
Log minimum:
```text
request_id
method
path
status
duration_ms
```

## 20. Job ID
Operasi background memakai:
```text
job_id
file_id
event_type
status
duration_ms
error_code
```

## 21. Security
Default:
```text
127.0.0.1:8000
```
Bukan `0.0.0.0`.

Aturan:
- parameterized SQL
- canonical path
- path traversal prevention
- extension allowlist
- file size limit
- parser error isolation
- sanitized errors
- tidak menjalankan shell command dari raw path user
- tidak log full document
- tidak expose embedding
- Jinja autoescape
- `textContent` untuk dynamic JS
- CSRF/auth bila nanti dibuka ke network

File actions menggunakan `file_id`, bukan raw path:
```text
file_id
→ database lookup
→ canonical path
→ validation
→ Windows open
```

## 22. Frontend
Teknologi:
- Jinja2
- HTML
- CSS
- vanilla JavaScript

Tidak menggunakan React/Next/Vue/Redux atau UI framework besar.

Layout:
```text
┌─────────────────────────────────────────────────────────┐
│ AI FILE SEARCH                           ● Service OK   │
├───────────────┬─────────────────────────────────────────┤
│ Folders       │ [ Cari dokumen secara natural... ] 🔎 │
│ Documents     │                                         │
│ Downloads     │ 5 hasil                                 │
│ Desktop       │ Network Security.pdf                   │
│ + Add folder  │ Documents\Networking\                │
│               │ Relevansi 91%                           │
│               │ [Open File] [Open Location]             │
├───────────────┴─────────────────────────────────────────┤
│ Indexed 1,234 files • 45,678 chunks • Queue 2          │
└─────────────────────────────────────────────────────────┘
```

Performance:
- CSS satu file
- JS satu file
- no SPA
- no embedding to client
- pagination
- Top-K kecil
- optional search debounce 250–400 ms
- tidak polling agresif
- loading state
- tampilkan latency

Accessibility:
- semantic HTML
- labels
- keyboard navigation
- focus state
- `aria-live`
- Enter search
- Escape clear

## 23. Windows Service
Final deployment:
```text
Windows Boot
→ AI File Search Service
→ PostgreSQL check
→ load configuration
→ load embedding model
→ start FastAPI
→ start watcher
→ READY
```

Konfigurasi:
- Startup type: Automatic
- Recovery: restart on failure
- graceful shutdown
- development: `uvicorn app.main:app --reload`

## 24. Configuration
```env
APP_HOST=127.0.0.1
APP_PORT=8000
DATABASE_URL=postgresql://...
EMBEDDING_MODEL=...
EMBEDDING_DEVICE=cpu
SEARCH_TOP_K_DEFAULT=5
SEARCH_TOP_K_MAX=50
WATCH_DEBOUNCE_MS=1000
FILE_STABILITY_MS=1500
MAX_FILE_SIZE_MB=100
INDEX_WORKERS=1
LOG_LEVEL=INFO
```

Secret tidak boleh disimpan di repository.

## 25. Status
```text
PENDING
PROCESSING
INDEXED
FAILED
DELETED
```

Satu file gagal tidak boleh menghentikan file lain.

Error codes contoh:
```text
EXTRACTION_FAILED
FILE_LOCKED
UNSUPPORTED_EXTENSION
FILE_TOO_LARGE
EMBEDDING_FAILED
DATABASE_ERROR
```

Retry bounded dan hanya untuk error transient.

## 26. Observability
Structured logging:
```text
timestamp
level
request_id
job_id
file_id
event_type
duration_ms
status
error_code
```

Dashboard:
```text
Service: Running
Database: OK
Watcher: Running
Embedding: Ready
Indexed Files: 1,234
Indexed Chunks: 45,678
Pending Jobs: 2
Failed Files: 1
Last Index: ...
```

## 27. Testing

### Unit
- SHA-256
- hash comparison
- chunking
- extension validation
- folder validation
- Top-K
- rename detection
- repository SQL
- RRF

### Integration
1. Create PDF → watcher → index → search.
2. Modify PDF → hash berubah → reindex file.
3. Modify tanpa perubahan isi → skip embedding.
4. Rename → path berubah tanpa embedding.
5. Delete → chunks terhapus.
6. Restart service → watcher aktif.
7. PostgreSQL down → status error tanpa crash loop.

## 28. Dataset & Evaluasi
Dataset adalah corpus evaluasi, bukan training set.

Buat query natural-language dan relevance judgment manual.

Eksperimen:
- E1: BM25/FTS
- E2: vector semantic
- E3: hybrid + RRF
- E4: incremental vs full rebuild
- E5: latency berdasarkan corpus size

Metrik:
- Precision@5
- Recall@K
- MRR
- p50 latency
- p95 latency
- initial indexing time
- incremental indexing time
- CPU
- RAM
- database/vector size

## 29. Incremental vs Full Reindex
| Skenario | Incremental | Full |
|---|---|---|
| 1 file baru | 1 file | semua |
| rename | metadata | tidak perlu |
| 1 file berubah | 1 file | tidak perlu |
| model berubah | affected corpus | cocok |
| index corruption | recovery | cocok |

## 30. Acceptance Criteria
| Area | Kriteria |
|---|---|
| Watcher | CREATE/MODIFY/DELETE/MOVE |
| Incremental | tidak full reindex pada perubahan kecil |
| Extraction | PDF/DOCX/TXT |
| Hash | SHA-256 |
| Embedding | local pretrained |
| Database | PostgreSQL + pgvector |
| Retrieval | hybrid |
| Ranking | RRF |
| API | validation |
| Frontend | lightweight |
| Security | localhost default |
| Service | auto-start |
| Recovery | restart-safe |
| Research | retrieval + incremental benchmark |

## 31. Dependency
```text
fastapi
uvicorn[standard]
jinja2
pydantic
pydantic-settings
watchdog
pymupdf
python-docx
sentence-transformers
torch
psycopg[binary]
pgvector
alembic
rank-bm25
pytest
httpx
```

Versi final dikunci setelah environment berhasil dibangun dan dites.

## 32. Milestone
| Milestone | Output |
|---|---|
| M1 | FastAPI + Jinja + Health |
| M2 | PostgreSQL + pgvector |
| M3 | PDF/DOCX/TXT extractor |
| M4 | Chunking |
| M5 | Embedding |
| M6 | Watcher + Queue |
| M7 | Vector Search |
| M8 | Lexical Search |
| M9 | RRF Hybrid |
| M10 | Frontend |
| M11 | Windows Service |
| M12 | Testing |
| M13 | Benchmark |
| M14 | Dataset skripsi |

## 33. Final Architecture Statement

```text
Windows File System
→ Watchdog
→ Debounce + Queue
→ Incremental Ingestion
→ SHA-256
→ Text Extraction
→ Chunking
→ Local Pretrained Embedding
→ PostgreSQL + pgvector
→ Hybrid Lexical/Semantic Retrieval
→ RRF
→ FastAPI
→ Jinja2/Vanilla JS
→ Browser
```

Fokus penelitian:
**Incremental Semantic Indexing + Hybrid Document Retrieval**

Bukan:
- LLM training
- RAG generation
- multimodal AI
- chatbot

## 34. Final Rules
1. Jangan full scan setiap MODIFY.
2. Jangan re-embed jika hash sama.
3. Jangan re-embed ketika rename dengan hash sama.
4. Jangan SELECT seluruh chunk pada search.
5. Jangan menghitung seluruh cosine similarity di Python.
6. Jangan load model setiap request.
7. Jangan expose raw path execution.
8. Jangan expose FastAPI ke LAN pada default deployment.
9. Jangan log isi dokumen.
10. Jangan menambahkan LLM hanya agar sistem terlihat lebih AI.
11. Gunakan benchmark untuk menentukan chunk size, candidate pool, worker count, dan vector index.
12. Pertahankan deployment tetap single-service dan ringan untuk scope lokal.

## 35. Ringkasan

Sistem final adalah aplikasi AI File Search lokal Windows yang ringan tetapi memiliki arsitektur penelitian yang jelas:

**Filesystem-aware incremental indexing + SHA-256 change detection + pretrained semantic embedding + PostgreSQL/pgvector + hybrid lexical/vector retrieval + RRF + FastAPI + lightweight Jinja2 UI + Windows Service.**

Arsitektur ini cukup sederhana untuk implementasi S1 tetapi menyediakan variabel eksperimen yang terukur untuk penelitian: kualitas retrieval, latency, resource usage, dan efisiensi incremental indexing.
