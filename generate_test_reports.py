
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUTPUT_DIR = Path("test_documents")
OUTPUT_DIR.mkdir(exist_ok=True)

REPORT_TEXT = [
    "SYNTHETIC MEDICAL REPORT - TEST DATA ONLY",
    "Hospital: Example Care Hospital",
    "Patient Name: Rahul Sharma (FICTIONAL)",
    "Patient ID: TEST-P001",
    "Report Number: TEST-LAB-001",
    "Report Date: 2026-10-15",
    "Doctor: Dr. Example Kumar",
    "Test: Hemoglobin",
    "Result: 14.2 g/dL",
    "",
    "This document is fictional and is not for clinical use.",
]


def draw_report(pdf_path, scanned_style=False):
    page = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4

    if scanned_style:
        # Draw the text as an image-like page.
        # This creates a PDF with no embedded text,
        # suitable for testing OCR.
        from reportlab.pdfbase.pdfmetrics import stringWidth

        page.setFont("Helvetica-Bold", 16)
        page.drawString(55, height - 65, REPORT_TEXT[0])

        page.setFont("Helvetica", 11)
        y = height - 105

        for line in REPORT_TEXT[1:]:
            page.drawString(55, y, line)
            y -= 25

        page.showPage()
        page.save()

        # Convert the PDF page to an image-only PDF using PyMuPDF.
        import fitz

        with fitz.open(pdf_path) as source:
            pix = source[0].get_pixmap(matrix=fitz.Matrix(2, 2))
            image_path = OUTPUT_DIR / "temporary_report.png"
            pix.save(image_path)

        image_pdf = OUTPUT_DIR / "scanned_medical_report.pdf"

        with fitz.open() as new_pdf:
            page = new_pdf.new_page(width=width, height=height)
            page.insert_image(page.rect, filename=str(image_path))
            new_pdf.save(image_pdf)

        Path(pdf_path).unlink(missing_ok=True)
        image_path.unlink(missing_ok=True)
        print("Created:", image_pdf)

    else:
        page.setFont("Helvetica-Bold", 16)
        page.drawString(55, height - 65, REPORT_TEXT[0])

        page.setFont("Helvetica", 11)
        y = height - 105

        for line in REPORT_TEXT[1:]:
            page.drawString(55, y, line)
            y -= 25

        page.save()
        print("Created:", pdf_path)


draw_report(OUTPUT_DIR / "digital_medical_report.pdf")
draw_report(OUTPUT_DIR / "temporary_scanned.pdf", scanned_style=True)
