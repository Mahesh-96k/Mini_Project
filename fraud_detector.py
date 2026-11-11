
import re
from datetime import date, datetime

TEST_LIMITS = {
    "hemoglobin": {
        "min": 0.0,
        "max": 30.0,
        "unit": "g/dL",
    }
}


def analyze_report(report):
    findings = []
    score = 0
    missing_fields = []

    def flag(reason, points):
        nonlocal score
        findings.append({"reason": reason, "points": points})
        score += points

    required_fields = [
        "patient_name",
        "patient_id",
        "hospital_name",
        "report_number",
        "report_date",
        "doctor_name",
    ]

    for field in required_fields:
        value = report.get(field)
        if value is None or (
            isinstance(value, str) and not value.strip()
        ):
            missing_fields.append(field)
            flag(f"Missing required field: {field}", 10)

    raw_date = report.get("report_date")
    if raw_date:
        try:
            parsed_date = datetime.strptime(
                raw_date, "%Y-%m-%d"
            ).date()
            if parsed_date > date.today():
                flag("Report date is in the future", 20)
        except (ValueError, TypeError):
            flag(
                "Report date is invalid or has an unsupported format",
                15,
            )

    report_number = report.get("report_number")
    if isinstance(report_number, str) and report_number.strip():
        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_-]{2,49}",
            report_number.strip(),
        ):
            flag("Report number has an unusual format", 10)

    test_name = report.get("test_name")
    test_result = report.get("test_result")

    if test_name and test_result:
        normalized_test = str(test_name).strip().lower()

        if normalized_test in TEST_LIMITS:
            match = re.fullmatch(
                r"\s*([-+]?\d+(?:\.\d+)?)\s*([A-Za-z/%]+)?\s*",
                str(test_result),
            )

            if not match:
                flag(
                    "Test result is not in an interpretable numeric format",
                    15,
                )
            else:
                value = float(match.group(1))
                unit = match.group(2)
                limits = TEST_LIMITS[normalized_test]

                if unit and unit.lower() != limits["unit"].lower():
                    flag(
                        "Test result unit does not match the configured unit",
                        20,
                    )
                elif value < limits["min"] or value > limits["max"]:
                    flag(
                        "Test result is outside the configured plausibility limits",
                        25,
                    )

    if report.get("duplicate_report_number") is True:
        flag(
            "Report number matches an existing registered record",
            30,
        )

    score = min(score, 100)

    if score < 20:
        risk_level = "Low"
    elif score < 50:
        risk_level = "Medium"
    else:
        risk_level = "High"

    if missing_fields:
        review_status = "manual_review_required"
    elif findings:
        review_status = "review_recommended"
    else:
        review_status = "no_configured_flags"

    return {
        "risk_score": score,
        "risk_level": risk_level,
        "review_status": review_status,
        "missing_fields": missing_fields,
        "findings": findings,
        "disclaimer": (
            "Preliminary screening only. A risk level is not proof "
            "of fraud or authenticity. Missing or uncertain information "
            "may require manual review."
        ),
    }
