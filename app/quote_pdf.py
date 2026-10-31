"""Convert the populated Erşen Makina Excel quotation into a PDF."""
from __future__ import annotations

import shutil
from io import BytesIO
import subprocess
import tempfile
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from xml.sax.saxutils import escape

from fastapi import HTTPException
from openpyxl import load_workbook
from pypdf import PdfReader


def _reportlab_pdf(excel_content: bytes) -> bytes:
    """Fallback renderer for hosts without LibreOffice; reads the exact populated workbook."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import reportlab
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="PDF oluşturmak için ReportLab paketi sunucuda bulunamadı.") from exc

    workbook = load_workbook(BytesIO(excel_content), data_only=False)
    try:
        sheet = workbook["Teklif"]
        quote_number = str(sheet["D13"].value or "")
        quote_date = sheet["D14"].value
        valid_until = sheet["D15"].value
        currency = str(sheet["J15"].value or "EUR")
        company = str(sheet["J6"].value or "")
        address = str(sheet["J7"].value or "")
        tax = str(sheet["J8"].value or "")
        contact = str(sheet["J9"].value or "")
        phone_email = str(sheet["J10"].value or "")
        intro = str(sheet["B18"].value or "")
        rows = []
        subtotal = Decimal("0")
        for row in range(28, 43):
            description = str(sheet[f"D{row}"].value or "").strip()
            quantity = sheet[f"J{row}"].value
            price = sheet[f"K{row}"].value
            if not description and quantity in (None, "") and price in (None, ""):
                continue
            try:
                qty = Decimal(str(quantity or 0))
                unit = Decimal(str(price or 0))
            except Exception:
                continue
            line_total = qty * unit
            subtotal += line_total
            rows.append([str(sheet[f"C{row}"].value or len(rows) + 1), description, str(int(qty)), f"{unit:,.0f} {currency}", f"{line_total:,.0f} {currency}"])
        vat = (subtotal * Decimal("0.20")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = subtotal + vat

        styles = getSampleStyleSheet()
        regular_font = "Helvetica"
        bold_font = "Helvetica-Bold"
        font_candidates = [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
            Path(reportlab.__file__).parent / "fonts" / "Vera.ttf",
        ]
        for font_path in font_candidates:
            if font_path.is_file():
                try:
                    pdfmetrics.registerFont(TTFont("QuoteSans", str(font_path)))
                    regular_font = "QuoteSans"
                    bold_path = font_path.with_name("DejaVuSans-Bold.ttf") if "DejaVuSans" in font_path.name else font_path
                    if bold_path.is_file():
                        pdfmetrics.registerFont(TTFont("QuoteSans-Bold", str(bold_path)))
                        bold_font = "QuoteSans-Bold"
                    else:
                        bold_font = regular_font
                    break
                except Exception:
                    continue
        styles.add(ParagraphStyle(name="BrandTitle", parent=styles["Title"], fontName=bold_font, fontSize=19, leading=22, textColor=colors.HexColor("#292A2A"), alignment=TA_LEFT, spaceAfter=2))
        styles.add(ParagraphStyle(name="Subtle", parent=styles["Normal"], fontName=regular_font, fontSize=8, leading=11, textColor=colors.HexColor("#6D6D68")))
        styles.add(ParagraphStyle(name="BodyTR", parent=styles["BodyText"], fontName=regular_font, fontSize=8.5, leading=12, textColor=colors.HexColor("#292A2A")))
        styles.add(ParagraphStyle(name="SmallRight", parent=styles["BodyText"], fontName=regular_font, fontSize=8, leading=11, alignment=TA_RIGHT))
        styles.add(ParagraphStyle(name="SectionTR", parent=styles["Heading2"], fontName=bold_font, fontSize=10, leading=13, textColor=colors.HexColor("#292A2A"), spaceBefore=8, spaceAfter=5))
        styles.add(ParagraphStyle(name="TemplateRow", parent=styles["BodyText"], fontName=regular_font, fontSize=6.2, leading=7.4, textColor=colors.HexColor("#292A2A"), spaceAfter=0))
        styles.add(ParagraphStyle(name="TemplateSection", parent=styles["Heading3"], fontName=bold_font, fontSize=7.5, leading=8.5, textColor=colors.HexColor("#292A2A"), spaceBefore=2, spaceAfter=1))

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=13*mm, bottomMargin=15*mm, title=f"{company} {quote_number}")
        story = []

        # Keep the original workbook's embedded logo/signature artwork in the generated PDF.
        top_images, bottom_images = [], []
        for workbook_image in getattr(sheet, "_images", []):
            try:
                raw = workbook_image._data()
                image = RLImage(BytesIO(raw))
                anchor_row = getattr(getattr(workbook_image, "anchor", None), "_from", None)
                if anchor_row and getattr(anchor_row, "row", 0) >= 20:
                    image._restrictSize(30*mm, 12*mm)
                else:
                    image._restrictSize(52*mm, 22*mm)
                if anchor_row and getattr(anchor_row, "row", 0) >= 20:
                    bottom_images.append(image)
                else:
                    top_images.append(image)
            except Exception:
                continue
        if top_images:
            image_cells = [[image for image in top_images[:3]]]
            image_table = Table(image_cells, colWidths=[(A4[0]-32*mm)/min(len(top_images),3)]*min(len(top_images),3))
            image_table.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(-1,-1),"LEFT"),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
            story.append(image_table)
            story.append(Spacer(1, 3*mm))
        else:
            story.append(Paragraph("ERŞEN MAKİNA", styles["BrandTitle"]))
        story.append(Paragraph("MAKİNE TEKLİFİ", styles["SectionTR"]))
        meta = [
            [Paragraph(f"<b>Teklif No:</b> {escape(quote_number)}", styles["BodyTR"]), Paragraph(f"<b>Tarih:</b> {escape(str(quote_date or ''))}", styles["SmallRight"])],
            [Paragraph(f"<b>Geçerlilik:</b> {escape(str(valid_until or ''))}", styles["BodyTR"]), Paragraph(f"<b>Para birimi:</b> {escape(currency)}", styles["SmallRight"])],
        ]
        meta_table = Table(meta, colWidths=[90*mm, 88*mm])
        meta_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F4F1E9")),("BOX",(0,0),(-1,-1),.5,colors.HexColor("#D8D1C1")),("INNERGRID",(0,0),(-1,-1),.25,colors.HexColor("#E5E0D5")),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        story.append(meta_table)
        story.append(Paragraph("MÜŞTERİ BİLGİLERİ", styles["SectionTR"]))
        customer_rows = [
            [Paragraph("<b>Firma</b>", styles["BodyTR"]), Paragraph(escape(company), styles["BodyTR"])],
            [Paragraph("<b>Adres</b>", styles["BodyTR"]), Paragraph(escape(address), styles["BodyTR"])],
            [Paragraph("<b>Vergi</b>", styles["BodyTR"]), Paragraph(escape(tax), styles["BodyTR"])],
            [Paragraph("<b>Yetkili</b>", styles["BodyTR"]), Paragraph(escape(contact), styles["BodyTR"])],
            [Paragraph("<b>İletişim</b>", styles["BodyTR"]), Paragraph(escape(phone_email), styles["BodyTR"])],
        ]
        customer_table = Table(customer_rows, colWidths=[28*mm,150*mm])
        customer_table.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F4F1E9")),("BOX",(0,0),(-1,-1),.5,colors.HexColor("#D8D1C1")),("INNERGRID",(0,0),(-1,-1),.25,colors.HexColor("#E5E0D5")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
        story.append(customer_table)
        if intro:
            story.append(Spacer(1, 5*mm))
            story.append(Paragraph(escape(intro), styles["BodyTR"]))
        story.append(Paragraph("TEKLİF KALEMLERİ", styles["SectionTR"]))
        data = [[ "Sıra", "Ürün / Hizmet", "Miktar", "Birim Fiyat", "Toplam" ]]
        data.extend([[Paragraph(escape(str(cell)), styles["BodyTR"]) if col==1 else str(cell) for col,cell in enumerate(row)] for row in rows])
        if len(data)==1:
            data.append(["1","—","—","—","—"])
        item_table=Table(data,colWidths=[13*mm,75*mm,18*mm,36*mm,36*mm],repeatRows=1)
        item_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#292A2A")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),bold_font),("FONTSIZE",(0,0),(-1,-1),7.5),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#D8D1C1")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#FAF9F6")]),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(0,-1),"CENTER"),("ALIGN",(2,1),(-1,-1),"RIGHT"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
        story.append(item_table)
        totals=[
            ["Ara toplam",f"{subtotal:,.2f} {currency}"],
            ["KDV %20",f"{vat:,.2f} {currency}"],
            ["Genel toplam",f"{total:,.2f} {currency}"],
        ]
        total_table=Table(totals,colWidths=[125*mm,53*mm],hAlign="RIGHT")
        total_table.setStyle(TableStyle([("ALIGN",(1,0),(1,-1),"RIGHT"),("FONTNAME",(0,2),(-1,2),bold_font),("FONTSIZE",(0,0),(-1,-1),9),("LINEABOVE",(0,2),(-1,2),1,colors.HexColor("#C89B35")),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("BACKGROUND",(0,2),(-1,2),colors.HexColor("#F6EFDD"))]))
        story.append(Spacer(1,4*mm));story.append(total_table)
        # The fallback renderer must retain the template's two-page reading order:
        # sections 1-6 on page one, then section 7 onward on page two. Locate the
        # section from workbook content instead of hard-coding a row number.
        section_seven_row = None
        for row_index in range(1, sheet.max_row + 1):
            row_values = [
                str(sheet.cell(row_index, column_index).value or "").strip()
                for column_index in range(1, sheet.max_column + 1)
            ]
            if any(__import__("re").match(r"^7\s*[.)]", value) for value in row_values):
                section_seven_row = row_index
                break

        def append_template_rows(first_row: int, last_row: int) -> None:
            for row_index in range(first_row, last_row + 1):
                values = []
                for column_index in range(1, sheet.max_column + 1):
                    value = sheet.cell(row_index, column_index).value
                    if value is None or (isinstance(value, str) and value.startswith("=")):
                        continue
                    text_value = str(value).strip()
                    if text_value and text_value not in values:
                        values.append(text_value)
                if not values:
                    continue
                row_text = " · ".join(values)
                if __import__("re").match(r"^[1-9]\s*[.)]", row_text):
                    story.append(Paragraph(escape(row_text), styles["TemplateSection"]))
                else:
                    story.append(Paragraph(escape(row_text), styles["TemplateRow"]))

        if section_seven_row is not None:
            # Include the remainder of sections 1-6 on page one.
            append_template_rows(49, section_seven_row - 1)
            story.append(PageBreak())
            # Page two begins with the actual section 7 heading from the workbook.
            append_template_rows(section_seven_row, sheet.max_row)
        else:
            # Fail visibly rather than silently claiming the required pagination
            # when the workbook no longer contains the expected section heading.
            raise ValueError("Excel şablonunda 7. Garanti ve Kabul bölümü bulunamadı.")

        if bottom_images:
            story.append(Spacer(1, 5*mm))
            for image in bottom_images[:3]:
                story.append(image)
        story.append(Spacer(1,4*mm))
        story.append(Paragraph("Erşen Makina · Bu teklif kayıtlı teklif verileri ve teklif şablonu esas alınarak oluşturulmuştur.", styles["Subtle"]))
        doc.build(story)
        return buffer.getvalue()
    finally:
        workbook.close()


def convert_excel_to_pdf(excel_content: bytes) -> bytes:
    """Prefer LibreOffice's exact workbook rendering; otherwise render the workbook's own template artwork and values."""
    converter = shutil.which("libreoffice") or shutil.which("soffice")
    if converter:
        with tempfile.TemporaryDirectory(prefix="quote-pdf-") as temp_dir:
            workdir = Path(temp_dir)
            input_path = workdir / "quotation.xlsx"
            output_path = workdir / "quotation.pdf"
            profile_path = workdir / "lo-profile"
            input_path.write_bytes(excel_content)
            command = [
                converter, "--headless", f"-env:UserInstallation={profile_path.as_uri()}",
                "--convert-to", "pdf", "--outdir", str(workdir), str(input_path),
            ]
            try:
                completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60)
                if completed.returncode == 0 and output_path.is_file():
                    pdf_content = output_path.read_bytes()
                    if pdf_content.startswith(b"%PDF-"):
                        reader = PdfReader(BytesIO(pdf_content), strict=True)
                        if not reader.is_encrypted and len(reader.pages):
                            return pdf_content
            except (subprocess.TimeoutExpired, OSError, Exception):
                # Use the workbook-backed renderer below if the system converter fails.
                pass
    try:
        # This renderer reads the filled Erşen Makina workbook, including its embedded
        # logo/signature artwork and customer/quote cells; it does not create a generic report.
        pdf_content = _reportlab_pdf(excel_content)
        reader = PdfReader(BytesIO(pdf_content), strict=True)
        if reader.is_encrypted or not reader.pages:
            raise ValueError("PDF has no readable pages")
        return pdf_content
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Erşen Makina teklif şablonundan PDF üretilemedi. Excel teklif dosyası indirilebilir.",
        ) from exc
