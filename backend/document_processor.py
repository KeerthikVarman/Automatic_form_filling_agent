"""
Universal Document Processor
Extracts raw text, structured tables, and metadata from uploaded documents
(PDF, DOCX, TXT, CSV, JSON, MD) for requirement auto-filling.
"""

import io
import os
import logging
from typing import Tuple, Dict, Any

logger = logging.getLogger("udyam_assistant.doc_processor")

class DocumentProcessor:
    """Parses uploaded documents and extracts readable text."""

    @staticmethod
    def extract_text_from_file(file_bytes: bytes, filename: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extracts readable text and metadata from file bytes based on file extension.
        Returns: (extracted_text, metadata_dict)
        """
        ext = os.path.splitext(filename)[1].lower()
        size_kb = round(len(file_bytes) / 1024, 1)

        metadata = {
            "filename": filename,
            "extension": ext,
            "size_kb": size_kb,
            "pages": 1,
            "extracted_chars": 0
        }

        extracted_text = ""

        try:
            if ext == ".pdf":
                extracted_text, pages = DocumentProcessor._extract_pdf(file_bytes)
                metadata["pages"] = pages

            elif ext in [".docx", ".doc"]:
                extracted_text = DocumentProcessor._extract_docx(file_bytes)

            elif ext in [".txt", ".csv", ".json", ".md", ".rtf"]:
                extracted_text = DocumentProcessor._extract_plain_text(file_bytes)

            else:
                # Unsupported format fallback
                try:
                    extracted_text = DocumentProcessor._extract_plain_text(file_bytes)
                except Exception:
                    raise ValueError(f"Unsupported file format '{ext}'. Please upload a PDF, DOCX, or TXT file.")

        except Exception as e:
            logger.error(f"Error parsing document '{filename}': {e}")
            raise ValueError(f"Failed to process '{filename}': {str(e)}")

        metadata["extracted_chars"] = len(extracted_text)
        return extracted_text.strip(), metadata

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> Tuple[str, int]:
        """Extracts text from PDF bytes using PyMuPDF (fitz) or pypdf."""
        text_parts = []
        page_count = 0

        # Try PyMuPDF (fitz)
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            full_text = "\n".join(text_parts).strip()
            if full_text:
                return full_text, page_count
        except Exception as e:
            logger.warning(f"PyMuPDF extract failed, falling back to pypdf: {e}")

        # Fallback to pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            page_count = len(reader.pages)
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
            full_text = "\n".join(text_parts).strip()
            return full_text, page_count
        except Exception as e:
            raise ValueError(f"Could not read PDF contents: {e}")

    @staticmethod
    def _extract_docx(file_bytes: bytes) -> str:
        """Extracts text from DOCX bytes using python-docx."""
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            
            # Also extract text from tables
            table_texts = []
            for table in doc.tables:
                for row in table.rows:
                    row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_cells:
                        table_texts.append(" | ".join(row_cells))

            combined = paragraphs + table_texts
            return "\n".join(combined).strip()
        except Exception as e:
            raise ValueError(f"Could not read DOCX document: {e}")

    @staticmethod
    def _extract_plain_text(file_bytes: bytes) -> str:
        """Decodes raw text files with fallback encodings."""
        for enc in ["utf-8", "latin-1", "utf-16", "cp1252"]:
            try:
                return file_bytes.decode(enc)
            except UnicodeDecodeError:
                continue
        return file_bytes.decode("utf-8", errors="ignore")

# Global singleton
document_processor = DocumentProcessor()
