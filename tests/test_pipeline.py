import os
import time
import tempfile
from pathlib import Path
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.queue import IngestionJob
from app.database.repository import get_repository
from app.retrieval.hybrid import HybridRetriever


def test_full_incremental_pipeline_workflow():
    repo = get_repository()
    pipeline = IngestionPipeline()
    retriever = HybridRetriever()

    # 1. Create temporary test document
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt", encoding="utf-8") as tf:
        tf.write("Protokol keamanan jaringan TCP/IP dan implementasi enkripsi RSA.")
        tf_path = tf.name

    try:
        # A. CREATE
        job_create = IngestionJob(
            job_id="test_job_1",
            path=tf_path,
            event_type="CREATE"
        )
        pipeline.process_job(job_create)

        file_rec = repo.get_file_by_path(tf_path)
        assert file_rec is not None
        assert file_rec.status == "INDEXED"
        original_hash = file_rec.content_hash

        # Search should find it immediately!
        results = retriever.search("keamanan jaringan RSA", top_k=5)
        assert len(results) > 0
        match_files = [r["filename"] for r in results]
        assert Path(tf_path).name in match_files

        # B. MODIFY with SAME CONTENT (Skip embedding test)
        job_modify_same = IngestionJob(
            job_id="test_job_2",
            path=tf_path,
            event_type="MODIFY"
        )
        pipeline.process_job(job_modify_same)
        file_rec_after = repo.get_file_by_path(tf_path)
        assert file_rec_after.content_hash == original_hash

        # C. MODIFY with CHANGED CONTENT
        with open(tf_path, "w", encoding="utf-8") as f:
            f.write("Sistem terdistribusi menggunakan replikasi multi-master database.")

        job_modify_new = IngestionJob(
            job_id="test_job_3",
            path=tf_path,
            event_type="MODIFY"
        )
        pipeline.process_job(job_modify_new)
        file_rec_mod = repo.get_file_by_path(tf_path)
        assert file_rec_mod.content_hash != original_hash
        assert file_rec_mod.status == "INDEXED"

        # Search new content
        results_new = retriever.search("replikasi multi-master", top_k=5)
        assert len(results_new) > 0

        # D. RENAME / MOVE
        new_path = tf_path + ".renamed.txt"
        os.rename(tf_path, new_path)

        job_move = IngestionJob(
            job_id="test_job_4",
            path=tf_path,
            event_type="MOVE",
            dest_path=new_path
        )
        pipeline.process_job(job_move)

        renamed_rec = repo.get_file_by_path(new_path)
        assert renamed_rec is not None
        assert renamed_rec.filename == Path(new_path).name
        # Old path should be gone
        assert repo.get_file_by_path(tf_path) is None

        # Clean up renamed file
        tf_path = new_path

        # E. DELETE
        job_delete = IngestionJob(
            job_id="test_job_5",
            path=tf_path,
            event_type="DELETE"
        )
        pipeline.process_job(job_delete)
        assert repo.get_file_by_path(tf_path) is None

    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)
