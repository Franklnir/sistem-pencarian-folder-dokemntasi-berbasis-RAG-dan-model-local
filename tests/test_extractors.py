import os
import tempfile
import pymupdf
from app.extractors.registry import ExtractorRegistry
from app.extractors.txt import TXTExtractor


def test_txt_extractor():
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt", encoding="utf-8") as tf:
        tf.write("Sistem temu balik informasi hybrid untuk skripsi komputer.")
        tf_path = tf.name

    try:
        sections = ExtractorRegistry.extract(tf_path)
        assert len(sections) == 1
        assert "skripsi komputer" in sections[0]["text"]
        assert sections[0]["page_no"] is None
    finally:
        if os.path.exists(tf_path):
            os.remove(tf_path)


def test_pdf_extractor():
    # Generate a lightweight test PDF with PyMuPDF
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".pdf") as tf:
        pdf_path = tf.name

    try:
        doc = pymupdf.open()
        page1 = doc.new_page()
        page1.insert_text((50, 72), "Halaman pertama PDF: Keamanan Jaringan dan Firewall.")
        page2 = doc.new_page()
        page2.insert_text((50, 72), "Halaman kedua PDF: Arsitektur Sistem Terdistribusi.")
        doc.save(pdf_path)
        doc.close()

        sections = ExtractorRegistry.extract(pdf_path)
        assert len(sections) == 2
        assert sections[0]["page_no"] == 1
        assert "Keamanan Jaringan" in sections[0]["text"]
        assert sections[1]["page_no"] == 2
        assert "Sistem Terdistribusi" in sections[1]["text"]
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
