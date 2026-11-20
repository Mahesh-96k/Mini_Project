
from datetime import datetime, date
from health_history_pdf import generate_health_history_pdf

# Synthetic patient information
patient = {
    "full_name": "Rahul Sharma",
    "global_pid": "TEST-P001",
    "date_of_birth": date(2000, 5, 15),
    "generated_at": datetime.now().strftime("%d-%m-%Y %H:%M")
}

# Synthetic health measurements
measurements = {
    "blood_sugar": [
        {
            "measurement_type": "blood_sugar_random",
            "value": 95,
            "unit": "mg/dL",
            "context": "Random",
            "recorded_at": "2026-11-08 10:27:00"
        },
        {
            "measurement_type": "blood_sugar_random",
            "value": 100,
            "unit": "mg/dL",
            "context": "Random",
            "recorded_at": "2026-11-08 10:00:00"
        },
        {
            "measurement_type": "blood_sugar_fasting",
            "value": 135,
            "unit": "mg/dL",
            "context": "Fasting",
            "recorded_at": "2026-11-07 10:58:00"
        }
    ],

    "blood_pressure": [
        {"value": 120, "secondary_value": 80, "unit": "mmHg", "recorded_at": "2026-11-02 09:00:00"},
        {"value": 125, "secondary_value": 82, "unit": "mmHg", "recorded_at": "2026-11-03 09:00:00"},
        {"value": 118, "secondary_value": 78, "unit": "mmHg", "recorded_at": "2026-11-04 09:00:00"}
    ],

    "heart_rate": [
        {"value": 72, "unit": "BPM", "context": "Resting", "recorded_at": "2026-11-03 10:00:00"},
        {"value": 76, "unit": "BPM", "context": "Resting", "recorded_at": "2026-11-04 10:00:00"},
        {"value": 70, "unit": "BPM", "context": "Resting", "recorded_at": "2026-11-05 10:00:00"}
    ],

    "weight": [
        {"value": 65, "unit": "kg", "recorded_at": "2026-11-04 07:00:00"},
        {"value": 64.8, "unit": "kg", "recorded_at": "2026-11-05 07:00:00"},
        {"value": 64.5, "unit": "kg", "recorded_at": "2026-11-06 07:00:00"}
    ],

    "sleep": [
        {"value": 7.5, "secondary_value": 93.75, "awake_minutes": 30, "recorded_at": "2026-11-05 22:00:00", "ended_at": "2026-11-06 06:00:00"},
        {"value": 7, "secondary_value": 90, "awake_minutes": 40, "recorded_at": "2026-11-06 22:00:00", "ended_at": "2026-11-07 06:00:00"},
        {"value": 8, "secondary_value": 95, "awake_minutes": 20, "recorded_at": "2026-11-07 22:00:00", "ended_at": "2026-11-08 06:00:00"}
    ],

    "temperature": [
        {"value": 36.8, "unit": "°C", "recorded_at": "2026-11-06 08:00:00"},
        {"value": 37.0, "unit": "°C", "recorded_at": "2026-11-07 08:00:00"},
        {"value": 36.7, "unit": "°C", "recorded_at": "2026-11-08 08:00:00"}
    ]
}

# Generate PDF
generate_health_history_pdf(
    "test_health_history.pdf",
    patient,
    measurements
)

print("Health History PDF generated successfully!")
