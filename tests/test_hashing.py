import os
import tempfile
from pathlib import Path
from app.ingestion.hashing import compute_sha256
from app.config import is_allowed_file, canonicalize_path, is_critical_system_directory


def test_sha256_computation():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tf:
        tf.write("Hello AI File Search!")
        tf_path = tf.name

    try:
        h1 = compute_sha256(tf_path)
        assert len(h1) == 64
        # Same content should give identical hash
        h2 = compute_sha256(tf_path)
        assert h1 == h2

        # Change content
        with open(tf_path, "a") as f:
            f.write(" Modified!")
        h3 = compute_sha256(tf_path)
        assert h1 != h3
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_path_canonicalization_and_system_detection():
    # System path detection
    assert is_critical_system_directory(r"C:\Windows") is True
    assert is_critical_system_directory(r"C:\Windows\System32") is True
    assert is_critical_system_directory(r"C:\Program Files") is True
    assert is_critical_system_directory(r"C:\Users\User\Documents") is False

    # Extension allowlist
    assert is_allowed_file("test.pdf") is True
    assert is_allowed_file("test.docx") is True
    assert is_allowed_file("test.txt") is True
    assert is_allowed_file("test.exe") is False
    assert is_allowed_file("test.mp4") is False
