import re
from datetime import date, datetime

# Configured physiological and clinical limits for common laboratory tests
TEST_LIMITS = {
    "hemoglobin": {
        "aliases": ["hemoglobin", "hb", "haemoglobin", "hgb"],
        "min": 0.0,
        "max": 30.0,
        "unit": "g/dL",
        "alt_units": ["g/dl", "gm/dl", "g/100ml"]
    },
    "wbc": {
        "aliases": ["wbc", "white blood cells", "total leukocyte count", "tlc", "leukocytes"],
        "min": 200.0,
        "max": 200000.0,
        "unit": "/mcL",
        "alt_units": ["/cumm", "cells/cumm", "cells/mcl", "/ul", "x10^3/ul", "k/ul"]
    },
    "rbc": {
        "aliases": ["rbc", "red blood cells", "total rbc count", "erythrocytes"],
        "min": 0.5,
        "max": 10.0,
        "unit": "million/mcL",
        "alt_units": ["million/cumm", "x10^6/ul", "mil/mcl", "m/ul"]
    },
    "platelets": {
        "aliases": ["platelets", "platelet count", "thrombocytes"],
        "min": 5000.0,
        "max": 2000000.0,
        "unit": "/mcL",
        "alt_units": ["/cumm", "cells/cumm", "lakhs/cumm", "x10^3/ul", "k/ul"]
    },
    "hematocrit": {
        "aliases": ["hematocrit", "packed cell volume", "pcv", "hct"],
        "min": 5.0,
        "max": 75.0,
        "unit": "%",
        "alt_units": ["percent"]
    },
    "fasting blood sugar": {
        "aliases": ["fasting blood sugar", "fbs", "glucose fasting", "blood sugar fasting"],
        "min": 10.0,
        "max": 1500.0,
        "unit": "mg/dL",
        "alt_units": ["mg/dl", "mg%"]
    },
    "post-meal blood sugar": {
        "aliases": ["post-meal blood sugar", "ppbs", "glucose post prandial", "blood sugar pp"],
        "min": 10.0,
        "max": 1500.0,
        "unit": "mg/dL",
        "alt_units": ["mg/dl", "mg%"]
    },
    "random blood sugar": {
        "aliases": ["random blood sugar", "rbs", "glucose random"],
        "min": 10.0,
        "max": 1500.0,
        "unit": "mg/dL",
        "alt_units": ["mg/dl", "mg%"]
    },
    "hba1c": {
        "aliases": ["hba1c", "glycated hemoglobin", "glycohemoglobin"],
        "min": 2.0,
        "max": 25.0,
        "unit": "%",
        "alt_units": ["percent"]
    },
    "serum creatinine": {
        "aliases": ["serum creatinine", "creatinine"],
        "min": 0.1,
        "max": 30.0,
        "unit": "mg/dL",
        "alt_units": ["mg/dl"]
    },
    "blood urea": {
        "aliases": ["blood urea", "urea", "blood urea nitrogen", "bun"],
        "min": 1.0,
        "max": 300.0,
        "unit": "mg/dL",
        "alt_units": ["mg/dl"]
    },
    "total bilirubin": {
        "aliases": ["total bilirubin", "bilirubin total", "serum bilirubin"],
        "min": 0.05,
        "max": 50.0,
        "unit": "mg/dL",
        "alt_units": ["mg/dl"]
    },
    "total cholesterol": {
        "aliases": ["total cholesterol", "serum cholesterol", "cholesterol"],
        "min": 20.0,
        "max": 1500.0,
        "unit": "mg/dL",
        "alt_units": ["mg/dl"]
    },
    "triglycerides": {
        "aliases": ["triglycerides", "tg", "serum triglycerides"],
        "min": 10.0,
        "max": 3000.0,
        "unit": "mg/dL",
        "alt_units": ["mg/dl"]
    },
    "hdl cholesterol": {
        "aliases": ["hdl cholesterol", "hdl", "high density lipoprotein"],
        "min": 5.0,
        "max": 200.0,
        "unit": "mg/dL",
        "alt_units": ["mg/dl"]
    },
    "ldl cholesterol": {
        "aliases": ["ldl cholesterol", "ldl", "low density lipoprotein"],
        "min": 10.0,
        "max": 1000.0,
        "unit": "mg/dL",
        "alt_units": ["mg/dl"]
    }
}


def find_matching_limit_key(name):
    """Resolve test name against known aliases."""
    if not name:
        return None
    name_clean = str(name).strip().lower()

    # Exact matches first
    for standard_key, config in TEST_LIMITS.items():
        if name_clean == standard_key or name_clean in [a.lower() for a in config.get("aliases", [])]:
            return standard_key

    # Specific sub-type prioritizations
    if "hdl" in name_clean:
        return "hdl cholesterol"
    if "ldl" in name_clean:
        return "ldl cholesterol"
    if "total cholesterol" in name_clean or ("cholesterol" in name_clean and "hdl" not in name_clean and "ldl" not in name_clean):
        return "total cholesterol"
    if ("fasting" in name_clean and "sugar" in name_clean) or "fbs" in name_clean:
        return "fasting blood sugar"
    if ("post" in name_clean and ("meal" in name_clean or "prandial" in name_clean)) or "ppbs" in name_clean:
        return "post-meal blood sugar"
    if ("random" in name_clean and "sugar" in name_clean) or "rbs" in name_clean:
        return "random blood sugar"
    if "hemoglobin" in name_clean or "haemoglobin" in name_clean or name_clean in ["hb", "hgb"]:
        return "hemoglobin"
    if "hematocrit" in name_clean or "pcv" in name_clean or name_clean == "hct":
        return "hematocrit"

    # General substring matching
    for standard_key, config in TEST_LIMITS.items():
        aliases = config.get("aliases", [standard_key])
        if any(alias in name_clean for alias in aliases if len(alias) >= 4):
            return standard_key

    return None


def parse_numeric_test_value(raw_val):
    """Extract numeric value and unit from a test result string or number."""
    if raw_val is None:
        return None, None
    if isinstance(raw_val, (int, float)):
        return float(raw_val), ""
    match = re.fullmatch(r"\s*([-+]?\d+(?:\.\d+)?)\s*([A-Za-z/%^0-9]+)?\s*", str(raw_val))
    if not match:
        return None, None
    val = float(match.group(1))
    unit = match.group(2) or ""
    return val, unit


def analyze_report(report):
    """
    Comprehensive multi-pattern clinical laboratory report fraud and integrity screening.
    Evaluates:
    - Required identity and provider metadata
    - Chronological consistency and timestamps
    - Biological limits for hematology, biochemistry, and metabolic panels
    - Cross-test physiological correlations (e.g. Hct vs Hgb, Lipid fractions, Glucose vs HbA1c)
    - Structural anomaly signals
    """
    findings = []
    score = 0
    missing_fields = []
    checked_tests_map = {}

    def flag(reason, points, check_category="Integrity Check", severity="medium"):
        nonlocal score
        findings.append({
            "check": check_category,
            "reason": reason,
            "message": reason,
            "points": points,
            "severity": severity
        })
        score += points

    # 1. REQUIRED FIELDS CHECK
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
        if value is None or (isinstance(value, str) and not value.strip()):
            missing_fields.append(field)
            flag(f"Missing required field: {field}", 10, check_category="Document Completeness")

    # 2. DATE & CHRONOLOGY CHECKS
    raw_date = report.get("report_date")
    parsed_report_date = None
    if raw_date:
        try:
            # Handle YYYY-MM-DD or DD-MM-YYYY or common formats
            date_str = str(raw_date).strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}", date_str):
                parsed_report_date = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
            elif re.match(r"^\d{2}[-/]\d{2}[-/]\d{4}", date_str):
                parsed_report_date = datetime.strptime(date_str[:10].replace("/", "-"), "%d-%m-%Y").date()
            else:
                parsed_report_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            if parsed_report_date > date.today():
                flag("Report date is in the future", 20, check_category="Chronological Integrity", severity="high")
        except (ValueError, TypeError):
            flag(
                "Report date is invalid or has an unsupported format",
                15,
                check_category="Chronological Integrity"
            )

    # Check specimen collection date vs report authorization date
    raw_collection_date = report.get("collection_date")
    if raw_collection_date and parsed_report_date:
        try:
            col_str = str(raw_collection_date).strip()
            if re.match(r"^\d{4}-\d{2}-\d{2}", col_str):
                parsed_col_date = datetime.strptime(col_str[:10], "%Y-%m-%d").date()
                if parsed_col_date > parsed_report_date:
                    flag(
                        "Specimen collection date is after the report authorization date",
                        25,
                        check_category="Chronological Integrity",
                        severity="high"
                    )
        except (ValueError, TypeError):
            pass

    # 3. REPORT IDENTIFIER FORMAT CHECKS
    report_number = report.get("report_number")
    if isinstance(report_number, str) and report_number.strip():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,49}", report_number.strip()):
            flag("Report number has an unusual format", 10, check_category="Identifier Validation")

    if report.get("duplicate_report_number") is True:
        flag("Report number matches an existing registered record", 30, check_category="Identifier Validation", severity="high")

    # 4. CLINICAL & BIOLOGICAL LIMITS CHECK
    # Test primary test_name & test_result first
    primary_test_name = report.get("test_name")
    primary_test_result = report.get("test_result")

    all_tests_to_evaluate = []
    if primary_test_name and primary_test_result:
        all_tests_to_evaluate.append({
            "test_name": primary_test_name,
            "value": primary_test_result,
            "is_primary": True
        })

    # Also evaluate all items in tests array if present
    multi_tests = report.get("tests", [])
    if isinstance(multi_tests, list):
        for t in multi_tests:
            if isinstance(t, dict) and t.get("test_name"):
                name = t.get("test_name")
                val_combined = f"{t.get('value', '')} {t.get('unit', '')}".strip()
                if not any(item["test_name"].lower() == name.lower() for item in all_tests_to_evaluate):
                    all_tests_to_evaluate.append({
                        "test_name": name,
                        "value": val_combined,
                        "unit": t.get("unit"),
                        "is_primary": False
                    })

    for test_item in all_tests_to_evaluate:
        t_name = test_item["test_name"]
        t_raw_val = test_item["value"]

        limit_key = find_matching_limit_key(t_name)
        val, unit = parse_numeric_test_value(t_raw_val)

        if val is None:
            if limit_key or test_item.get("is_primary"):
                flag(
                    "Test result is not in an interpretable numeric format",
                    15,
                    check_category="Clinical Validation"
                )
            continue

        checked_tests_map[limit_key or t_name.lower().strip()] = val

        if limit_key and limit_key in TEST_LIMITS:
            limits = TEST_LIMITS[limit_key]
            allowed_units = [limits["unit"].lower()] + [u.lower() for u in limits.get("alt_units", [])]

            if unit:
                unit_clean = unit.lower().strip()
                if unit_clean not in allowed_units:
                    flag(
                        "Test result unit does not match the configured unit",
                        20,
                        check_category="Clinical Validation"
                    )

            if val < limits["min"] or val > limits["max"]:
                flag(
                    "Test result is outside the configured plausibility limits",
                    25,
                    check_category="Clinical Validation",
                    severity="high"
                )

    # 5. CROSS-TEST BIOLOGICAL CORRELATIONS & PATTERNS
    # A. Hematology Rule of Three (Hematocrit % ≈ 3 × Hemoglobin g/dL ± 25%)
    hgb_val = checked_tests_map.get("hemoglobin")
    hct_val = checked_tests_map.get("hematocrit")
    if hgb_val and hct_val and hgb_val > 0:
        expected_hct = hgb_val * 3.0
        ratio = hct_val / expected_hct
        if ratio < 0.55 or ratio > 1.45:
            flag(
                f"Clinical inconsistency: Hematocrit ({hct_val}%) does not correlate with Hemoglobin ({hgb_val} g/dL). Violates standard hematology correlation.",
                20,
                check_category="Biological Correlation",
                severity="high"
            )

    # B. Lipid Profile Consistency: Total Cholesterol >= HDL + LDL
    tc = checked_tests_map.get("total cholesterol")
    hdl = checked_tests_map.get("hdl cholesterol")
    ldl = checked_tests_map.get("ldl cholesterol")
    if tc and hdl and ldl:
        if tc < (hdl + ldl - 5):
            flag(
                f"Biochemical discrepancy: Total Cholesterol ({tc} mg/dL) is less than the sum of HDL ({hdl}) and LDL ({ldl}) fractions.",
                20,
                check_category="Biological Correlation",
                severity="high"
            )

    # C. Glucose vs HbA1c Discordance (Extreme disconnect)
    glucose = (
        checked_tests_map.get("fasting blood sugar")
        or checked_tests_map.get("random blood sugar")
        or checked_tests_map.get("post-meal blood sugar")
    )
    hba1c = checked_tests_map.get("hba1c")
    if glucose and hba1c:
        if glucose > 350.0 and hba1c < 5.0:
            flag(
                f"Severe metabolic discordance: Blood glucose is severely elevated ({glucose} mg/dL) while HbA1c is sub-normal ({hba1c}%).",
                20,
                check_category="Biological Correlation"
            )

    # 6. NON-MEDICAL DOCUMENT / ANOMALY CHECKS
    if report.get("is_medical_document") is False:
        flag("Uploaded document does not exhibit standard clinical laboratory report characteristics.", 35, check_category="Document Classification", severity="high")

    # 7. AI ANOMALY OBSERVATIONS INTEGRATION
    ai_anomalies = report.get("ai_anomalies") or []
    if isinstance(ai_anomalies, list):
        for anomaly in ai_anomalies:
            if isinstance(anomaly, str) and anomaly.strip():
                # Avoid duplicates
                if not any(f["reason"] == anomaly for f in findings):
                    flag(anomaly, 15, check_category="AI Anomaly Analysis")

    # 8. FINAL SCORE & STATUS
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
