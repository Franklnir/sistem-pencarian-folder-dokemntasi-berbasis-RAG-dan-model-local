from pathlib import Path
from typing import List, Dict, Any


class TXTExtractor:
    @staticmethod
    def extract(file_path: str) -> List[Dict[str, Any]]:
        """
        Extract text from a plain text file using UTF-8 with fallback encodings.
        Returns a list of dicts: [{'text': str, 'page_no': None}]
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
        content = None
        last_err = None

        for enc in encodings:
            try:
                with open(str(path), "r", encoding=enc) as f:
                    content = f.read().strip()
                break
            except Exception as e:
                last_err = e

        if content is None:
            raise RuntimeError(f"Failed to read TXT ({path.name}): {str(last_err)}")

        if not content:
            return []

        return [{"text": content, "page_no": None}]
