import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

from app.config import settings, canonicalize_path
from app.database.models import FileRecord, ChunkRecord, MonitoredFolderRecord

logger = logging.getLogger("ai_file_search.database")


class DatabaseRepository:
    def __init__(self):
        self._mode = "uninitialized"  # "postgres" or "sqlite"
        self._db_status = "down"  # "ok" or "down"
        self._last_error = None
        self._sqlite_path = Path(settings.DATA_DIR) / "ai_file_search_local.db"
        self._pg_pool = None
        self._sqlite_vector_cache = None
        self.init_db()

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def status(self) -> str:
        return self._db_status

    def init_db(self):
        """Try connecting to PostgreSQL. If unavailable, initialize local fallback."""
        pool = None
        try:
            import psycopg
            from psycopg_pool import ConnectionPool

            logger.info(f"Connecting to PostgreSQL at {settings.DATABASE_URL}...")
            # Fast check first without launching background pool threads
            with psycopg.connect(settings.DATABASE_URL, connect_timeout=1) as direct_conn:
                with direct_conn.cursor() as cur:
                    cur.execute("SELECT 1;")

            pool = ConnectionPool(settings.DATABASE_URL, min_size=1, max_size=5, timeout=2.0, open=True)
            self._pg_pool = pool
            self._mode = "postgres"
            self._db_status = "ok"
            self._init_postgres_schema()
            logger.info("Connected to PostgreSQL successfully.")
            return
        except Exception as e:
            self._pg_pool = None
            self._last_error = str(e)
            logger.warning(
                f"PostgreSQL connection failed ({e}). "
                f"Activating embedded SQLite storage at {self._sqlite_path}."
            )
            self._mode = "sqlite"
            self._db_status = "down"  # Documentasi: PostgreSQL down -> status error tanpa crash loop
            self._init_sqlite_schema()


    def _init_postgres_schema(self):
        with self._pg_pool.connection() as conn:
            with conn.cursor() as cur:
                # Extension
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                except Exception as e:
                    logger.warning(f"Could not enable pgvector extension: {e}")

                # Files table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS files (
                        id BIGSERIAL PRIMARY KEY,
                        path TEXT UNIQUE NOT NULL,
                        filename TEXT NOT NULL,
                        extension VARCHAR(16) NOT NULL,
                        size_bytes BIGINT NOT NULL DEFAULT 0,
                        modified_at TIMESTAMPTZ NOT NULL,
                        content_hash CHAR(64) NOT NULL,
                        status VARCHAR(16) NOT NULL DEFAULT 'PENDING',
                        error_message TEXT,
                        indexed_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)

                # Chunks table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id BIGSERIAL PRIMARY KEY,
                        file_id BIGINT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                        page_no INTEGER,
                        chunk_index INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        embedding VECTOR(384),
                        token_count INTEGER DEFAULT 0,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)

                # Monitored folders
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS monitored_folders (
                        id BIGSERIAL PRIMARY KEY,
                        path TEXT UNIQUE NOT NULL,
                        enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)

                # Indexes
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_files_path ON files(path);")
                cur.execute("CREATE INDEX IF NOT EXISTS ix_files_hash ON files(content_hash);")
                cur.execute("CREATE INDEX IF NOT EXISTS ix_files_status ON files(status);")
                cur.execute("CREATE INDEX IF NOT EXISTS ix_files_modified ON files(modified_at DESC);")
                cur.execute("CREATE INDEX IF NOT EXISTS ix_chunks_file_id ON document_chunks(file_id);")
                try:
                    cur.execute("CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);")
                except Exception:
                    pass
            conn.commit()

    def _init_sqlite_schema(self):
        conn = sqlite3.connect(str(self._sqlite_path), timeout=30.0)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode = WAL;")
        cur.execute("PRAGMA busy_timeout = 30000;")
        cur.execute("PRAGMA synchronous = NORMAL;")
        cur.execute("PRAGMA foreign_keys = ON;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                extension TEXT NOT NULL,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                modified_at TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                error_message TEXT,
                indexed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                page_no INTEGER,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                token_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS monitored_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_files_path ON files(path);")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_files_hash ON files(content_hash);")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_files_status ON files(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_chunks_file_id ON document_chunks(file_id);")
        conn.commit()
        conn.close()

    def _get_sqlite_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._sqlite_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    # -------------------------------------------------------------
    # Monitored Folders
    # -------------------------------------------------------------
    def get_folders(self) -> List[MonitoredFolderRecord]:
        canon_records = []
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, path, enabled, created_at, updated_at FROM monitored_folders ORDER BY id ASC;")
                    for r in cur.fetchall():
                        canon_records.append(MonitoredFolderRecord(id=r[0], path=r[1], enabled=r[2], created_at=r[3], updated_at=r[4]))
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, path, enabled, created_at, updated_at FROM monitored_folders ORDER BY id ASC;")
                for r in cur.fetchall():
                    canon_records.append(MonitoredFolderRecord(
                        id=r["id"],
                        path=r["path"],
                        enabled=bool(r["enabled"]),
                        created_at=datetime.fromisoformat(r["created_at"]),
                        updated_at=datetime.fromisoformat(r["updated_at"])
                    ))
        return canon_records

    def get_folder_by_id(self, folder_id: int) -> Optional[MonitoredFolderRecord]:
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, path, enabled, created_at, updated_at FROM monitored_folders WHERE id = %s;", (folder_id,))
                    r = cur.fetchone()
                    if r:
                        return MonitoredFolderRecord(id=r[0], path=r[1], enabled=r[2], created_at=r[3], updated_at=r[4])
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, path, enabled, created_at, updated_at FROM monitored_folders WHERE id = ?;", (folder_id,))
                r = cur.fetchone()
                if r:
                    return MonitoredFolderRecord(
                        id=r["id"],
                        path=r["path"],
                        enabled=bool(r["enabled"]),
                        created_at=datetime.fromisoformat(r["created_at"]),
                        updated_at=datetime.fromisoformat(r["updated_at"])
                    )
        return None

    def get_folder_by_path(self, path: str) -> Optional[MonitoredFolderRecord]:
        c_path = canonicalize_path(path)
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, path, enabled, created_at, updated_at FROM monitored_folders WHERE path = %s;", (c_path,))
                    r = cur.fetchone()
                    if r:
                        return MonitoredFolderRecord(id=r[0], path=r[1], enabled=r[2], created_at=r[3], updated_at=r[4])
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, path, enabled, created_at, updated_at FROM monitored_folders WHERE path = ?;", (c_path,))
                r = cur.fetchone()
                if r:
                    return MonitoredFolderRecord(
                        id=r["id"],
                        path=r["path"],
                        enabled=bool(r["enabled"]),
                        created_at=datetime.fromisoformat(r["created_at"]),
                        updated_at=datetime.fromisoformat(r["updated_at"])
                    )
        return None

    def add_folder(self, path: str) -> MonitoredFolderRecord:
        c_path = canonicalize_path(path)
        now = datetime.now(timezone.utc)
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO monitored_folders (path, enabled, created_at, updated_at)
                        VALUES (%s, TRUE, %s, %s)
                        RETURNING id;
                    """, (c_path, now, now))
                    fid = cur.fetchone()[0]
                conn.commit()
            return MonitoredFolderRecord(id=fid, path=c_path, enabled=True, created_at=now, updated_at=now)
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO monitored_folders (path, enabled, created_at, updated_at)
                    VALUES (?, 1, ?, ?);
                """, (c_path, now.isoformat(), now.isoformat()))
                fid = cur.lastrowid
                conn.commit()
            return MonitoredFolderRecord(id=fid, path=c_path, enabled=True, created_at=now, updated_at=now)

    def update_folder_enabled(self, folder_id: int, enabled: bool) -> Optional[MonitoredFolderRecord]:
        now = datetime.now(timezone.utc)
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE monitored_folders SET enabled = %s, updated_at = %s WHERE id = %s RETURNING path, created_at;
                    """, (enabled, now, folder_id))
                    r = cur.fetchone()
                    if r:
                        conn.commit()
                        return MonitoredFolderRecord(id=folder_id, path=r[0], enabled=enabled, created_at=r[1], updated_at=now)
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE monitored_folders SET enabled = ?, updated_at = ? WHERE id = ?;
                """, (1 if enabled else 0, now.isoformat(), folder_id))
                if cur.rowcount > 0:
                    conn.commit()
                    return self.get_folder_by_id(folder_id)
        return None

    def delete_folder(self, folder_id: int) -> bool:
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM monitored_folders WHERE id = %s;", (folder_id,))
                    count = cur.rowcount
                conn.commit()
            return count > 0
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM monitored_folders WHERE id = ?;", (folder_id,))
                count = cur.rowcount
                conn.commit()
            return count > 0

    # -------------------------------------------------------------
    # Files
    # -------------------------------------------------------------
    def get_file_by_path(self, path: str) -> Optional[FileRecord]:
        c_path = canonicalize_path(path)
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, path, filename, extension, size_bytes, modified_at, content_hash,
                               status, error_message, indexed_at, created_at, updated_at
                        FROM files WHERE path = %s;
                    """, (c_path,))
                    r = cur.fetchone()
                    if r:
                        return FileRecord(
                            id=r[0], path=r[1], filename=r[2], extension=r[3], size_bytes=r[4],
                            modified_at=r[5], content_hash=r[6], status=r[7], error_message=r[8],
                            indexed_at=r[9], created_at=r[10], updated_at=r[11]
                        )
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, path, filename, extension, size_bytes, modified_at, content_hash,
                           status, error_message, indexed_at, created_at, updated_at
                    FROM files WHERE path = ?;
                """, (c_path,))
                r = cur.fetchone()
                if r:
                    return self._sqlite_row_to_file(r)
        return None

    def get_file_by_id(self, file_id: int) -> Optional[FileRecord]:
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, path, filename, extension, size_bytes, modified_at, content_hash,
                               status, error_message, indexed_at, created_at, updated_at
                        FROM files WHERE id = %s;
                    """, (file_id,))
                    r = cur.fetchone()
                    if r:
                        return FileRecord(
                            id=r[0], path=r[1], filename=r[2], extension=r[3], size_bytes=r[4],
                            modified_at=r[5], content_hash=r[6], status=r[7], error_message=r[8],
                            indexed_at=r[9], created_at=r[10], updated_at=r[11]
                        )
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, path, filename, extension, size_bytes, modified_at, content_hash,
                           status, error_message, indexed_at, created_at, updated_at
                    FROM files WHERE id = ?;
                """, (file_id,))
                r = cur.fetchone()
                if r:
                    return self._sqlite_row_to_file(r)
        return None

    def get_file_by_hash(self, content_hash: str) -> Optional[FileRecord]:
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, path, filename, extension, size_bytes, modified_at, content_hash,
                               status, error_message, indexed_at, created_at, updated_at
                        FROM files WHERE content_hash = %s LIMIT 1;
                    """, (content_hash,))
                    r = cur.fetchone()
                    if r:
                        return FileRecord(
                            id=r[0], path=r[1], filename=r[2], extension=r[3], size_bytes=r[4],
                            modified_at=r[5], content_hash=r[6], status=r[7], error_message=r[8],
                            indexed_at=r[9], created_at=r[10], updated_at=r[11]
                        )
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, path, filename, extension, size_bytes, modified_at, content_hash,
                           status, error_message, indexed_at, created_at, updated_at
                    FROM files WHERE content_hash = ? LIMIT 1;
                """, (content_hash,))
                r = cur.fetchone()
                if r:
                    return self._sqlite_row_to_file(r)
        return None

    def upsert_file(self, file: FileRecord) -> int:
        now = datetime.now(timezone.utc)
        c_path = canonicalize_path(file.path)
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO files (path, filename, extension, size_bytes, modified_at, content_hash,
                                           status, error_message, indexed_at, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (path) DO UPDATE SET
                            filename = EXCLUDED.filename,
                            extension = EXCLUDED.extension,
                            size_bytes = EXCLUDED.size_bytes,
                            modified_at = EXCLUDED.modified_at,
                            content_hash = EXCLUDED.content_hash,
                            status = EXCLUDED.status,
                            error_message = EXCLUDED.error_message,
                            indexed_at = EXCLUDED.indexed_at,
                            updated_at = EXCLUDED.updated_at
                        RETURNING id;
                    """, (
                        c_path, file.filename, file.extension.lower(), file.size_bytes,
                        file.modified_at, file.content_hash, file.status, file.error_message,
                        file.indexed_at, file.created_at or now, now
                    ))
                    fid = cur.fetchone()[0]
                conn.commit()
            return fid
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO files (path, filename, extension, size_bytes, modified_at, content_hash,
                                       status, error_message, indexed_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (path) DO UPDATE SET
                        filename = excluded.filename,
                        extension = excluded.extension,
                        size_bytes = excluded.size_bytes,
                        modified_at = excluded.modified_at,
                        content_hash = excluded.content_hash,
                        status = excluded.status,
                        error_message = excluded.error_message,
                        indexed_at = excluded.indexed_at,
                        updated_at = excluded.updated_at;
                """, (
                    c_path, file.filename, file.extension.lower(), file.size_bytes,
                    file.modified_at.isoformat(), file.content_hash, file.status, file.error_message,
                    file.indexed_at.isoformat() if file.indexed_at else None,
                    file.created_at.isoformat() if file.created_at else now.isoformat(),
                    now.isoformat()
                ))
                cur.execute("SELECT id FROM files WHERE path = ?;", (c_path,))
                fid = cur.fetchone()["id"]
                conn.commit()
            return fid

    def update_file_status(self, file_id: int, status: str, error_message: Optional[str] = None):
        now = datetime.now(timezone.utc)
        indexed_at = now if status == "INDEXED" else None
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE files SET status = %s, error_message = %s, indexed_at = COALESCE(%s, indexed_at), updated_at = %s
                        WHERE id = %s;
                    """, (status, error_message, indexed_at, now, file_id))
                conn.commit()
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE files SET status = ?, error_message = ?, indexed_at = COALESCE(?, indexed_at), updated_at = ?
                    WHERE id = ?;
                """, (status, error_message, indexed_at.isoformat() if indexed_at else None, now.isoformat(), file_id))
                conn.commit()

    def update_file_indexed(self, file_id: int, content_hash: str, size_bytes: int, modified_at: datetime):
        now = datetime.now(timezone.utc)
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE files SET status = 'INDEXED', content_hash = %s, size_bytes = %s,
                                         modified_at = %s, error_message = NULL, indexed_at = %s, updated_at = %s
                        WHERE id = %s;
                    """, (content_hash, size_bytes, modified_at, now, now, file_id))
                conn.commit()
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE files SET status = 'INDEXED', content_hash = ?, size_bytes = ?,
                                     modified_at = ?, error_message = NULL, indexed_at = ?, updated_at = ?
                    WHERE id = ?;
                """, (content_hash, size_bytes, modified_at.isoformat(), now.isoformat(), now.isoformat(), file_id))
                conn.commit()


    def update_file_path(self, file_id: int, new_path: str, new_filename: str):
        c_path = canonicalize_path(new_path)
        now = datetime.now(timezone.utc)
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE files SET path = %s, filename = %s, updated_at = %s WHERE id = %s;
                    """, (c_path, new_filename, now, file_id))
                conn.commit()
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE files SET path = ?, filename = ?, updated_at = ? WHERE id = ?;
                """, (c_path, new_filename, now.isoformat(), file_id))
                conn.commit()

    def delete_file(self, file_id: int):
        self._sqlite_vector_cache = None
        try:
            from app.retrieval.bm25 import LexicalRetriever
            LexicalRetriever.invalidate_cache()
        except Exception:
            pass
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM files WHERE id = %s;", (file_id,))
                conn.commit()
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM files WHERE id = ?;", (file_id,))
                conn.commit()

    def list_files(
        self,
        page: int = 1,
        page_size: int = 25,
        extension: Optional[str] = None,
        folder_path: Optional[str] = None
    ) -> Tuple[List[FileRecord], int]:
        offset = (page - 1) * page_size
        records = []
        total = 0

        where_clauses = []
        params = []

        if extension:
            ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
            where_clauses.append("extension = %s" if self._mode == "postgres" else "extension = ?")
            params.append(ext)

        if folder_path:
            clean_fp = folder_path.rstrip("\\/") + "%"
            where_clauses.append("path LIKE %s" if self._mode == "postgres" else "path LIKE ?")
            params.append(clean_fp)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    count_query = f"SELECT COUNT(*) FROM files {where_sql};"
                    cur.execute(count_query, tuple(params))
                    total = cur.fetchone()[0]

                    select_query = f"""
                        SELECT id, path, filename, extension, size_bytes, modified_at, content_hash,
                               status, error_message, indexed_at, created_at, updated_at
                        FROM files {where_sql} ORDER BY id DESC LIMIT %s OFFSET %s;
                    """
                    cur.execute(select_query, tuple(params + [page_size, offset]))
                    for r in cur.fetchall():
                        records.append(FileRecord(
                            id=r[0], path=r[1], filename=r[2], extension=r[3], size_bytes=r[4],
                            modified_at=r[5], content_hash=r[6], status=r[7], error_message=r[8],
                            indexed_at=r[9], created_at=r[10], updated_at=r[11]
                        ))
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                count_query = f"SELECT COUNT(*) as cnt FROM files {where_sql};"
                cur.execute(count_query, tuple(params))
                total = cur.fetchone()["cnt"]

                select_query = f"""
                    SELECT id, path, filename, extension, size_bytes, modified_at, content_hash,
                           status, error_message, indexed_at, created_at, updated_at
                    FROM files {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?;
                """
                cur.execute(select_query, tuple(params + [page_size, offset]))
                for r in cur.fetchall():
                    records.append(self._sqlite_row_to_file(r))

        return records, total

    def get_file_preview(self, file_id: int) -> Optional[Dict[str, Any]]:
        file_rec = self.get_file_by_id(file_id)
        if not file_rec:
            return None

        first_chunk_text = ""
        chunk_count = 0
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM document_chunks WHERE file_id = %s;", (file_id,))
                    chunk_count = cur.fetchone()[0]
                    cur.execute("SELECT text FROM document_chunks WHERE file_id = %s ORDER BY chunk_index ASC LIMIT 1;", (file_id,))
                    row = cur.fetchone()
                    if row:
                        first_chunk_text = row[0]
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) as cnt FROM document_chunks WHERE file_id = ?;", (file_id,))
                chunk_count = cur.fetchone()["cnt"]
                cur.execute("SELECT text FROM document_chunks WHERE file_id = ? ORDER BY chunk_index ASC LIMIT 1;", (file_id,))
                row = cur.fetchone()
                if row:
                    first_chunk_text = row["text"]

        return {
            "file": file_rec,
            "chunk_count": chunk_count,
            "preview_text": first_chunk_text[:1200] if first_chunk_text else ""
        }

    def _sqlite_row_to_file(self, r: sqlite3.Row) -> FileRecord:
        return FileRecord(
            id=r["id"],
            path=r["path"],
            filename=r["filename"],
            extension=r["extension"],
            size_bytes=r["size_bytes"],
            modified_at=datetime.fromisoformat(r["modified_at"]),
            content_hash=r["content_hash"],
            status=r["status"],
            error_message=r["error_message"],
            indexed_at=datetime.fromisoformat(r["indexed_at"]) if r["indexed_at"] else None,
            created_at=datetime.fromisoformat(r["created_at"]),
            updated_at=datetime.fromisoformat(r["updated_at"])
        )

    # -------------------------------------------------------------
    # Document Chunks
    # -------------------------------------------------------------
    def replace_chunks(self, file_id: int, chunks: List[ChunkRecord]):
        """Transactional chunk replacement for a single file."""
        self._sqlite_vector_cache = None
        try:
            from app.retrieval.bm25 import LexicalRetriever
            LexicalRetriever.invalidate_cache()
        except Exception:
            pass
        now = datetime.now(timezone.utc)
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM document_chunks WHERE file_id = %s;", (file_id,))
                    for c in chunks:
                        cur.execute("""
                            INSERT INTO document_chunks (file_id, page_no, chunk_index, text, embedding, token_count, created_at)
                            VALUES (%s, %s, %s, %s, %s::vector, %s, %s);
                        """, (file_id, c.page_no, c.chunk_index, c.text, str(c.embedding), c.token_count, now))
                conn.commit()
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM document_chunks WHERE file_id = ?;", (file_id,))
                for c in chunks:
                    cur.execute("""
                        INSERT INTO document_chunks (file_id, page_no, chunk_index, text, embedding, token_count, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                    """, (file_id, c.page_no, c.chunk_index, c.text, json.dumps(c.embedding), c.token_count, now.isoformat()))
                conn.commit()

    def get_all_chunks_for_lexical(self, extensions: Optional[List[str]] = None, folder_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch chunks and file metadata for lexical BM25 matching."""
        # Note: Select only necessary columns (id, file_id, text, page_no, path, filename, extension)
        results = []
        folder_prefix = None
        if folder_id:
            folder = self.get_folder_by_id(folder_id)
            if folder:
                folder_prefix = folder.path.rstrip("\\/") + "\\"

        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT c.id, c.file_id, c.page_no, c.chunk_index, c.text, f.filename, f.path, f.extension
                        FROM document_chunks c
                        JOIN files f ON c.file_id = f.id
                        WHERE f.status = 'INDEXED'
                    """
                    params = []
                    if extensions:
                        query += " AND f.extension = ANY(%s)"
                        params.append([ext.lower() for ext in extensions])
                    if folder_prefix:
                        query += " AND f.path LIKE %s"
                        params.append(f"{folder_prefix}%")

                    cur.execute(query, tuple(params) if params else None)
                    for r in cur.fetchall():
                        results.append({
                            "chunk_id": r[0],
                            "file_id": r[1],
                            "page_no": r[2],
                            "chunk_index": r[3],
                            "text": r[4],
                            "filename": r[5],
                            "path": r[6],
                            "extension": r[7]
                        })
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                query = """
                    SELECT c.id, c.file_id, c.page_no, c.chunk_index, c.text, f.filename, f.path, f.extension
                    FROM document_chunks c
                    JOIN files f ON c.file_id = f.id
                    WHERE f.status = 'INDEXED'
                """
                params = []
                if extensions:
                    placeholders = ",".join("?" for _ in extensions)
                    query += f" AND f.extension IN ({placeholders})"
                    params.extend([ext.lower() for ext in extensions])
                if folder_prefix:
                    query += " AND f.path LIKE ?"
                    params.append(f"{folder_prefix}%")

                cur.execute(query, tuple(params))
                for r in cur.fetchall():
                    results.append({
                        "chunk_id": r["id"],
                        "file_id": r["file_id"],
                        "page_no": r["page_no"],
                        "chunk_index": r["chunk_index"],
                        "text": r["text"],
                        "filename": r["filename"],
                        "path": r["path"],
                        "extension": r["extension"]
                    })
        return results

    def get_chunks_by_file_id(self, file_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch all chunks for a specific file ordered by chunk_index."""
        results = []
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT c.id, c.file_id, c.page_no, c.chunk_index, c.text, f.filename, f.path, f.extension
                        FROM document_chunks c
                        JOIN files f ON c.file_id = f.id
                        WHERE c.file_id = %s
                        ORDER BY c.chunk_index ASC
                        LIMIT %s;
                    """, (file_id, limit))
                    for r in cur.fetchall():
                        results.append({
                            "chunk_id": r[0],
                            "file_id": r[1],
                            "page_no": r[2],
                            "chunk_index": r[3],
                            "text": r[4],
                            "filename": r[5],
                            "path": r[6],
                            "extension": r[7]
                        })
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT c.id, c.file_id, c.page_no, c.chunk_index, c.text, f.filename, f.path, f.extension
                    FROM document_chunks c
                    JOIN files f ON c.file_id = f.id
                    WHERE c.file_id = ?
                    ORDER BY c.chunk_index ASC
                    LIMIT ?;
                """, (file_id, limit))
                for r in cur.fetchall():
                    results.append({
                        "chunk_id": r["id"],
                        "file_id": r["file_id"],
                        "page_no": r["page_no"],
                        "chunk_index": r["chunk_index"],
                        "text": r["text"],
                        "filename": r["filename"],
                        "path": r["path"],
                        "extension": r["extension"]
                    })
        return results

    def get_relevant_chunks_for_file(
        self,
        file_id: int,
        query_embedding: Optional[List[float]] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Fetches chunks for a specific file and ranks them by cosine similarity
        against query_embedding if provided. Falls back to sequential chunks.
        """
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    if query_embedding:
                        cur.execute("""
                            SELECT c.id, c.file_id, c.page_no, c.chunk_index, c.text, f.filename, f.path, f.extension,
                                   1 - (c.embedding <=> %s::vector) AS score
                            FROM document_chunks c
                            JOIN files f ON c.file_id = f.id
                            WHERE c.file_id = %s
                            ORDER BY c.embedding <=> %s::vector ASC
                            LIMIT %s;
                        """, (str(query_embedding), file_id, str(query_embedding), limit))
                        results = []
                        for r in cur.fetchall():
                            results.append({
                                "chunk_id": r[0],
                                "file_id": r[1],
                                "page_no": r[2],
                                "chunk_index": r[3],
                                "text": r[4],
                                "filename": r[5],
                                "path": r[6],
                                "extension": r[7],
                                "score": float(r[8])
                            })
                        return results
                    else:
                        return self.get_chunks_by_file_id(file_id, limit=limit)
        else:
            with self._get_sqlite_conn() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT c.id, c.file_id, c.page_no, c.chunk_index, c.text, c.embedding, f.filename, f.path, f.extension
                    FROM document_chunks c
                    JOIN files f ON c.file_id = f.id
                    WHERE c.file_id = ?
                    ORDER BY c.chunk_index ASC;
                """, (file_id,))
                rows = cur.fetchall()
                if not rows:
                    return []

                if not query_embedding:
                    return [
                        {
                            "chunk_id": r["id"],
                            "file_id": r["file_id"],
                            "page_no": r["page_no"],
                            "chunk_index": r["chunk_index"],
                            "text": r["text"],
                            "filename": r["filename"],
                            "path": r["path"],
                            "extension": r["extension"],
                            "score": 1.0
                        }
                        for r in rows[:limit]
                    ]

                q_vec = np.array(query_embedding, dtype=np.float32)
                q_norm = np.linalg.norm(q_vec)
                if q_norm > 0:
                    q_vec = q_vec / q_norm

                scored = []
                for r in rows:
                    try:
                        emb = np.array(json.loads(r["embedding"]), dtype=np.float32)
                        norm = np.linalg.norm(emb)
                        sim = float(np.dot(q_vec, emb) / norm) if norm > 0 else 0.0
                    except Exception:
                        sim = 0.0
                    scored.append({
                        "chunk_id": r["id"],
                        "file_id": r["file_id"],
                        "page_no": r["page_no"],
                        "chunk_index": r["chunk_index"],
                        "text": r["text"],
                        "filename": r["filename"],
                        "path": r["path"],
                        "extension": r["extension"],
                        "score": sim
                    })

                scored.sort(key=lambda x: x["score"], reverse=True)
                return scored[:limit]

    def vector_search(
        self,
        query_embedding: List[float],
        top_k: int = 50,
        extensions: Optional[List[str]] = None,
        folder_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Vector similarity search using pgvector (or local cosine for fallback)."""
        folder_prefix = None
        if folder_id:
            folder = self.get_folder_by_id(folder_id)
            if folder:
                folder_prefix = folder.path.rstrip("\\/") + "\\"

        candidates = []
        if self._mode == "postgres":
            with self._pg_pool.connection() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT c.id, c.file_id, c.page_no, c.chunk_index, c.text,
                               f.filename, f.path, f.extension,
                               1 - (c.embedding <=> %s::vector) AS score
                        FROM document_chunks c
                        JOIN files f ON c.file_id = f.id
                        WHERE f.status = 'INDEXED'
                    """
                    params = [str(query_embedding)]
                    if extensions:
                        query += " AND f.extension = ANY(%s)"
                        params.append([ext.lower() for ext in extensions])
                    if folder_prefix:
                        query += " AND f.path LIKE %s"
                        params.append(f"{folder_prefix}%")

                    query += " ORDER BY c.embedding <=> %s::vector LIMIT %s;"
                    params.extend([str(query_embedding), top_k])

                    cur.execute(query, tuple(params))
                    for r in cur.fetchall():
                        candidates.append({
                            "chunk_id": r[0],
                            "file_id": r[1],
                            "page_no": r[2],
                            "chunk_index": r[3],
                            "text": r[4],
                            "filename": r[5],
                            "path": r[6],
                            "extension": r[7],
                            "score": float(r[8])
                        })
        else:
            # Ultra-fast vectorized cosine similarity via in-memory BLAS matrix cache
            q_vec = np.array(query_embedding, dtype=np.float32)
            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0:
                q_vec = q_vec / q_norm

            if getattr(self, "_sqlite_vector_cache", None) is None:
                with self._get_sqlite_conn() as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT c.id, c.file_id, c.page_no, c.chunk_index, c.text, c.embedding,
                               f.filename, f.path, f.extension
                        FROM document_chunks c
                        JOIN files f ON c.file_id = f.id
                        WHERE f.status = 'INDEXED'
                    """)
                    rows = cur.fetchall()
                    matrix_list = []
                    meta_list = []
                    for r in rows:
                        try:
                            emb = json.loads(r["embedding"])
                            matrix_list.append(emb)
                            meta_list.append({
                                "chunk_id": r["id"],
                                "file_id": r["file_id"],
                                "page_no": r["page_no"],
                                "chunk_index": r["chunk_index"],
                                "text": r["text"],
                                "filename": r["filename"],
                                "path": r["path"],
                                "extension": r["extension"]
                            })
                        except Exception:
                            continue

                    if matrix_list:
                        mat = np.array(matrix_list, dtype=np.float32)
                        norms = np.linalg.norm(mat, axis=1, keepdims=True)
                        norms[norms == 0] = 1.0
                        mat = mat / norms
                        self._sqlite_vector_cache = (mat, meta_list)
                    else:
                        self._sqlite_vector_cache = (np.empty((0, len(query_embedding)), dtype=np.float32), [])

            mat, meta_list = self._sqlite_vector_cache

            if len(meta_list) == 0:
                return []

            # 1-step BLAS matrix-vector product (< 3ms for 20k chunks)
            sims = np.dot(mat, q_vec)

            ext_set = set(e.lower() for e in extensions) if extensions else None
            scored_rows = []
            for idx, score in enumerate(sims):
                m = meta_list[idx]
                if ext_set and m["extension"].lower() not in ext_set:
                    continue
                if folder_prefix and not m["path"].startswith(folder_prefix):
                    continue
                scored_rows.append({
                    **m,
                    "score": float(score)
                })

            scored_rows.sort(key=lambda x: x["score"], reverse=True)
            candidates = scored_rows[:top_k]

        return candidates

    # -------------------------------------------------------------
    # Stats & Observability
    # -------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        stats = {
            "database": self._db_status,
            "indexed_files": 0,
            "indexed_chunks": 0,
            "failed_files": 0,
            "last_indexed_at": None,
        }
        try:
            if self._mode == "postgres":
                with self._pg_pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) FROM files WHERE status = 'INDEXED';")
                        stats["indexed_files"] = cur.fetchone()[0]
                        cur.execute("SELECT COUNT(*) FROM files WHERE status = 'FAILED';")
                        stats["failed_files"] = cur.fetchone()[0]
                        cur.execute("SELECT COUNT(*) FROM document_chunks;")
                        stats["indexed_chunks"] = cur.fetchone()[0]
                        cur.execute("SELECT MAX(indexed_at) FROM files WHERE status = 'INDEXED';")
                        max_idx = cur.fetchone()[0]
                        stats["last_indexed_at"] = max_idx.isoformat() if max_idx else None
            else:
                with self._get_sqlite_conn() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) as cnt FROM files WHERE status = 'INDEXED';")
                    stats["indexed_files"] = cur.fetchone()["cnt"]
                    cur.execute("SELECT COUNT(*) as cnt FROM files WHERE status = 'FAILED';")
                    stats["failed_files"] = cur.fetchone()["cnt"]
                    cur.execute("SELECT COUNT(*) as cnt FROM document_chunks;")
                    stats["indexed_chunks"] = cur.fetchone()["cnt"]
                    cur.execute("SELECT MAX(indexed_at) as max_idx FROM files WHERE status = 'INDEXED';")
                    max_idx = cur.fetchone()["max_idx"]
                    stats["last_indexed_at"] = max_idx
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")

        return stats


_repo_instance: Optional[DatabaseRepository] = None


def get_repository() -> DatabaseRepository:
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = DatabaseRepository()
    return _repo_instance
