
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image


# Tesseract installation on your Windows laptop
pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def extract_pdf_text(pdf_path):
    """
    Extract text from each PDF page.
    Use OCR when a page has no embedded text.
    """

    path = Path(pdf_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("This function currently accepts PDF files only.")

    extracted_pages = []

    with pymupdf.open(path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            method = "PyMuPDF"

            # Fall back to OCR when no embedded text is available.
            if not text:
                pix = page.get_pixmap(
                    matrix=pymupdf.Matrix(2, 2),
                    alpha=False,
                )

                image = Image.frombytes(
                    "RGB",
                    [pix.width, pix.height],
                    pix.samples,
                )

                text = pytesseract.image_to_string(
                    image,
                    lang="eng",
                ).strip()

                method = "Tesseract OCR"

            extracted_pages.append({
                "page": page_number,
                "text": text,
                "method": method,
                "needs_review": not bool(text),
            })

    return extracted_pages


if __name__ == "__main__":
    pdf_path = input("Enter the path to a PDF: ").strip().strip('"')

    try:
        pages = extract_pdf_text(pdf_path)

        for page in pages:
            print(f"\n--- Page {page['page']} ({page['method']}) ---")

            if page["text"]:
                print(page["text"])
            else:
                print("No text extracted. Manual review required.")

            if page["needs_review"]:
                print("WARNING: This page needs manual review.")

    except Exception as error:
        print("Extraction failed:", error)
