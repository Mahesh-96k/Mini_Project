
import unittest

from fraud_detector import analyze_report


def make_report(**overrides):
    report = {
        "patient_name": "Rahul Sharma",
        "patient_id": "TEST-P001",
        "hospital_name": "Example Care Hospital",
        "report_number": "TEST-LAB-001",
        "report_date": "2026-10-15",
        "doctor_name": "Dr. Example Kumar",
        "test_name": "Hemoglobin",
        "test_result": "14.2 g/dL",
        "duplicate_report_number": False,
    }
    report.update(overrides)
    return report


class FraudDetectorTests(unittest.TestCase):

    def test_normal_report(self):
        result = analyze_report(make_report())

        self.assertEqual(result["risk_score"], 0)
        self.assertEqual(result["risk_level"], "Low")
        self.assertEqual(result["review_status"], "no_configured_flags")
        self.assertEqual(result["findings"], [])

    def test_future_report_date(self):
        result = analyze_report(
            make_report(report_date="2099-10-15")
        )

        reasons = [item["reason"] for item in result["findings"]]
        self.assertIn("Report date is in the future", reasons)

    def test_missing_patient_id(self):
        result = analyze_report(make_report(patient_id=None))

        self.assertIn("patient_id", result["missing_fields"])

        reasons = [item["reason"] for item in result["findings"]]
        self.assertIn("Missing required field: patient_id", reasons)

    def test_missing_field_requires_manual_review(self):
        result = analyze_report(make_report(patient_id=None))

        self.assertEqual(
            result["review_status"],
            "manual_review_required",
        )

    def test_implausible_hemoglobin(self):
        result = analyze_report(
            make_report(test_result="99 g/dL")
        )

        reasons = [item["reason"] for item in result["findings"]]
        self.assertIn(
            "Test result is outside the configured plausibility limits",
            reasons,
        )

    def test_invalid_date(self):
        result = analyze_report(
            make_report(report_date="not-a-date")
        )

        reasons = [item["reason"] for item in result["findings"]]
        self.assertIn(
            "Report date is invalid or has an unsupported format",
            reasons,
        )

    def test_duplicate_report_number(self):
        result = analyze_report(
            make_report(duplicate_report_number=True)
        )

        reasons = [item["reason"] for item in result["findings"]]
        self.assertIn(
            "Report number matches an existing registered record",
            reasons,
        )

    def test_score_never_exceeds_100(self):
        result = analyze_report(
            make_report(
                patient_name=None,
                patient_id=None,
                hospital_name=None,
                report_number=None,
                report_date="not-a-date",
                doctor_name=None,
                test_result="99 g/dL",
                duplicate_report_number=True,
            )
        )

        self.assertLessEqual(result["risk_score"], 100)
        self.assertGreaterEqual(result["risk_score"], 0)

    def test_review_status_is_separate_from_risk_level(self):
        result = analyze_report(make_report(patient_id=None))

        self.assertEqual(result["risk_level"], "Low")
        self.assertEqual(
            result["review_status"],
            "manual_review_required",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
