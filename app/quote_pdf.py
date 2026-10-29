"""Convert generated Excel quotation workbooks to PDF with LibreOffice Calc."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import HTTPException
from pypdf import PdfReader


def convert_excel_to_pdf(excel_content: bytes) -> bytes:
    """Convert an in-memory XLSX workbook using the installed LibreOffice binary."""
    converter = shutil.which("libreoffice") or shutil.which("soffice")
    if not converter:
        raise HTTPException(
            status_code=503,
            detail="Şablonlu PDF oluşturmak için LibreOffice dönüştürücüsü sunucuda kurulu değil.",
        )
    with tempfile.TemporaryDirectory(prefix="quote-pdf-") as temp_dir:
        workdir = Path(temp_dir)
        input_path = workdir / "quotation.xlsx"
        output_path = workdir / "quotation.pdf"
        profile_path = workdir / "lo-profile"
        input_path.write_bytes(excel_content)
        command = [
            converter,
            "--headless",
            f"-env:UserInstallation={profile_path.as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(workdir),
            str(input_path),
        ]
        try:
            completed = subprocess.run(
                command, check=False, capture_output=True, text=True, timeout=60
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="Excel şablonunun PDF dönüşümü zaman aşımına uğradı.") from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail="PDF dönüştürücüsü başlatılamadı.") from exc
        if completed.returncode != 0 or not output_path.is_file():
            raise HTTPException(status_code=502, detail="Excel şablonu PDF'ye dönüştürülemedi.")
        pdf_content = output_path.read_bytes()
        if not pdf_content.startswith(b"%PDF-"):
            raise HTTPException(status_code=502, detail="Dönüştürücü geçerli bir PDF üretmedi.")
        try:
            reader = PdfReader(pdf_content, strict=True)
            if reader.is_encrypted or not reader.pages:
                raise ValueError("PDF has no readable pages")
            _ = len(reader.pages)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Oluşturulan PDF okunamıyor veya bozuk.") from exc
        return pdf_content
