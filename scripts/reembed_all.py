import time
import json
import sqlite3
from pathlib import Path
from sentence_transformers import SentenceTransformer

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ai_file_search_local.db"
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
BATCH_SIZE = 128

def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return

    print(f"Loading embedding model: {MODEL_NAME}...")
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    print(f"Model loaded in {round(time.time() - t0, 2)}s.")

    conn = sqlite3.connect(str(DB_PATH), timeout=60.0)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA synchronous = NORMAL;")

    cur.execute("SELECT COUNT(*) FROM document_chunks;")
    total_chunks = cur.fetchone()[0]
    print(f"Total chunks to re-embed: {total_chunks}")

    if total_chunks == 0:
        print("No chunks found in database.")
        conn.close()
        return

    # Fetch chunks in pages
    start_time = time.time()
    processed = 0

    page_limit = 1000
    last_id = 0

    while True:
        cur.execute(
            "SELECT id, text FROM document_chunks WHERE id > ? ORDER BY id ASC LIMIT ?;",
            (last_id, page_limit)
        )
        rows = cur.fetchall()
        if not rows:
            break

        chunk_ids = [r[0] for r in rows]
        chunk_texts = [r[1] if r[1] else " " for r in rows]
        last_id = chunk_ids[-1]

        # Batch encode
        embeddings = model.encode(
            chunk_texts,
            batch_size=BATCH_SIZE,
            show_progress_bar=False,
            normalize_embeddings=True
        )

        # Prepare update params
        update_params = [
            (json.dumps(embeddings[i].tolist()), chunk_ids[i])
            for i in range(len(chunk_ids))
        ]

        cur.executemany(
            "UPDATE document_chunks SET embedding = ? WHERE id = ?;",
            update_params
        )
        conn.commit()

        processed += len(chunk_ids)
        elapsed = time.time() - start_time
        speed = round(processed / elapsed, 1) if elapsed > 0 else 0
        pct = round((processed / total_chunks) * 100, 1)
        remaining = round((total_chunks - processed) / speed) if speed > 0 else 0
        print(f"Progress: {processed}/{total_chunks} ({pct}%) - {speed} chunks/s - ETA: {remaining}s")

    conn.close()
    total_time = round(time.time() - start_time, 2)
    print(f"\n[DONE] Successfully re-embedded {processed} chunks in {total_time}s!")

if __name__ == "__main__":
    main()
