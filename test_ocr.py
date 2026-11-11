
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image


pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

pdf_path = Path("test_documents/scanned_medical_report.pdf")

if not pdf_path.exists():
    print("Scanned PDF not found:", pdf_path)

else:
    with pymupdf.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            # Render the PDF page as an image for OCR.
            pix = page.get_pixmap(
                matrix=pymupdf.Matrix(2, 2),
                alpha=False
            )

            image = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            text = pytesseract.image_to_string(
                image,
                lang="eng"
            )

            print(f"\n--- OCR Page {page_number} ---")
            print(text if text.strip() else "No text recognized.")
