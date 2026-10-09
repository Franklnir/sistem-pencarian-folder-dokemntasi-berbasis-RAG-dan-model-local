from pathlib import Path
from typing import List, Dict, Any
import pymupdf  # PyMuPDF


class PDFExtractor:
    @staticmethod
    def extract(file_path: str) -> List[Dict[str, Any]]:
        """
        Extract text page-by-page from a PDF file using PyMuPDF.
        Returns a list of dicts: [{'text': str, 'page_no': int}]
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        extracted = []
        try:
            doc = pymupdf.open(str(path))
            for page_index in range(len(doc)):
                page = doc.load_page(page_index)
                text = page.get_text("text").strip()
                if text:
                    extracted.append({
                        "text": text,
                        "page_no": page_index + 1
                    })
            doc.close()
        except Exception as e:
            raise RuntimeError(f"Failed to extract PDF ({path.name}): {str(e)}") from e

        return extracted
