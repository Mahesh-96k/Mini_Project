
import json
from pathlib import Path

from document_extractor import extract_pdf_text
from document_analyzer import analyze_document
from fraud_detector import analyze_report


def run_analysis(pdf_path):
    print("\nStep 1: Extracting PDF text...")
    pages = extract_pdf_text(pdf_path)

    for page in pages:
        print(
            f"Page {page['page']}: "
            f"{page['method']} "
            f"({len(page['text'])} characters)"
        )

    report_text = "\n\n".join(
        f"[Page {page['page']}]\n{page['text']}"
        for page in pages
    )

    if not report_text.strip() or not any(
        page["text"].strip() for page in pages
    ):
        return {
            "status": "manual_review_required",
            "reason": "No usable text could be extracted.",
            "pages": pages,
        }

    if any(page["needs_review"] for page in pages):
        print("WARNING: At least one page needs manual review.")

    print("\nStep 2: Extracting fields with Gemini...")
    extracted_data = analyze_document(report_text)

    print("\nStep 3: Running Python fraud checks...")
    fraud_result = analyze_report(extracted_data)

    missing_fields = extracted_data.get("missing_fields") or []
    review_status = fraud_result["review_status"]

    manual_review_required = (
        bool(missing_fields)
        or any(page["needs_review"] for page in pages)
        or review_status == "manual_review_required"
    )

    status = (
        "manual_review_required"
        if manual_review_required
        else "analysis_complete"
    )

    return {
        "status": status,
        "source_file": Path(pdf_path).name,
        "pages": pages,
        "extracted_data": extracted_data,
        "fraud_analysis": fraud_result,
    }


if __name__ == "__main__":
    pdf_path = input(
        "Enter the path to a synthetic medical PDF: "
    ).strip().strip('"')

    try:
        result = run_analysis(pdf_path)

        print("\nMEDITRUST DOCUMENT ANALYSIS")
        print("=" * 35)
        print(json.dumps(result, indent=4, ensure_ascii=False))

    except Exception as error:
        print("\nAnalysis failed:", error)
