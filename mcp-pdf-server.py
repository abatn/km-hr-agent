#!/usr/bin/env python3
"""
PDF-MCP-Server für KM-HR-Agent
Basiert auf PyMuPDF (fitz) – kein Tesseract nötig für Text-PDFs.
Quelle: https://github.com/pymupdf/PyMuPDF
"""

from fastmcp import FastMCP
import pymupdf
import os

mcp = FastMCP("pdf-reader")


@mcp.tool()
def read_pdf_text(file_path: str, page_range: str = "") -> str:
    """
    Extrahiert Text aus einer PDF-Datei.
    
    Args:
        file_path: Pfad zur PDF-Datei
        page_range: Optional, z.B. "1-3" oder "2" (standard: alle Seiten)
    
    Returns:
        Extrahierter Text als String
    """
    if not os.path.exists(file_path):
        return f"FEHLER: Datei nicht gefunden: {file_path}"
    
    try:
        doc = pymupdf.open(file_path)
        total_pages = len(doc)
        
        # Seiten-Bereich parse
        pages_to_read = range(total_pages)
        if page_range:
            if "-" in page_range:
                start, end = page_range.split("-")
                pages_to_read = range(int(start) - 1, min(int(end), total_pages))
            else:
                p = int(page_range) - 1
                if 0 <= p < total_pages:
                    pages_to_read = [p]
        
        result_parts = []
        for page_num in pages_to_read:
            page = doc[page_num]
            text = page.get_text()
            result_parts.append(f"--- Seite {page_num + 1} ---\n{text}")
        
        full_text = "\n\n".join(result_parts)
        num_pages = total_pages
        doc.close()
        
        return f"OK|{num_pages}|{len(full_text)}\n{full_text}"
        
    except Exception as e:
        return f"FEHLER: {str(e)}"


@mcp.tool()
def get_pdf_info(file_path: str) -> str:
    """
    Gibt Metadaten über eine PDF-Datei zurück.
    
    Args:
        file_path: Pfad zur PDF-Datei
    
    Returns:
        PDF-Metadaten (Seiten, Titel, Autor, etc.)
    """
    if not os.path.exists(file_path):
        return f"FEHLER: Datei nicht gefunden: {file_path}"
    
    try:
        doc = pymupdf.open(file_path)
        meta = doc.metadata
        info = {
            "seiten": len(doc),
            "titel": meta.get("title", ""),
            "autor": meta.get("author", ""),
            "erstellt": meta.get("creationDate", ""),
            "geaendert": meta.get("modDate", ""),
            "format": meta.get("format", ""),
            "dateigroesse_bytes": os.path.getsize(file_path),
        }
        doc.close()
        
        lines = [f"{k}: {v}" for k, v in info.items()]
        return "OK\n" + "\n".join(lines)
        
    except Exception as e:
        return f"FEHLER: {str(e)}"


@mcp.tool()
def analyze_pdf_structure(file_path: str) -> str:
    """
    Analysiert die Struktur einer PDF-Datei (Layout, Spalten, Bilder).
    
    Args:
        file_path: Pfad zur PDF-Datei
    
    Returns:
        Struktur-Analyse
    """
    if not os.path.exists(file_path):
        return f"FEHLER: Datei nicht gefunden: {file_path}"
    
    try:
        doc = pymupdf.open(file_path)
        result = []
        
        for i, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]
            text_blocks = [b for b in blocks if b["type"] == 0]
            image_blocks = [b for b in blocks if b["type"] == 1]
            
            # Spalten-Analyse (einfach: x-Positionen der Blöcke)
            x_positions = sorted(set(b["bbox"][0] for b in text_blocks))
            num_columns = 1
            if len(x_positions) > 1:
                gaps = [x_positions[i+1] - x_positions[i] for i in range(len(x_positions)-1)]
                if any(g > 100 for g in gaps):
                    num_columns = len([g for g in gaps if g > 100]) + 1
            
            result.append(
                f"Seite {i+1}: "
                f"{len(text_blocks)} Textblöcke, "
                f"{len(image_blocks)} Bilder, "
                f"~{num_columns} Spalte(n), "
                f"{page.get_text().__len__()} Zeichen"
            )
        
        doc.close()
        return "OK\n" + "\n".join(result)
        
    except Exception as e:
        return f"FEHLER: {str(e)}"


if __name__ == "__main__":
    mcp.run()
