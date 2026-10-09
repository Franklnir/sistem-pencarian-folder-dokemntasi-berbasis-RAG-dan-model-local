from pathlib import Path
from typing import Dict, Type, List, Any
from app.extractors.pdf import PDFExtractor
from app.extractors.docx import DOCXExtractor
from app.extractors.txt import TXTExtractor


class ExtractorRegistry:
    """Registry mapping file extensions to their corresponding extractor classes."""

    _registry: Dict[str, Any] = {
        ".pdf": PDFExtractor,
        ".docx": DOCXExtractor,
        ".txt": TXTExtractor,
    }

    @classmethod
    def get_extractor(cls, extension_or_path: str):
        ext = Path(extension_or_path).suffix.lower()
        extractor = cls._registry.get(ext)
        if not extractor:
            raise ValueError(f"Unsupported file format: {ext}. Supported: {list(cls._registry.keys())}")
        return extractor

    @classmethod
    def extract(cls, file_path: str) -> List[Dict[str, Any]]:
        extractor = cls.get_extractor(file_path)
        return extractor.extract(file_path)


__all__ = ["ExtractorRegistry", "PDFExtractor", "DOCXExtractor", "TXTExtractor"]
