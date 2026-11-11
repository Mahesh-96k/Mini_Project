import os
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from xml.sax.saxutils import escape
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)

def add_page_design(canvas, document):
    canvas.saveState()

    page_width, page_height = A4

    # Top accent strip
    canvas.setFillColor(colors.HexColor("#087E75"))
    canvas.rect(0, page_height - 3 * mm, page_width, 3 * mm,
                fill=1, stroke=0)

    # White header background
    canvas.setFillColor(colors.white)
    canvas.rect(0, page_height - 30 * mm, page_width, 27 * mm,
                fill=1, stroke=0)

    # MediTrust logo
    logo_path = os.path.join(
        os.path.dirname(__file__),
        "static",
        "images",
        "meditrust_logo.png"
    )

    if os.path.exists(logo_path):
        canvas.drawImage(
            logo_path,
            18 * mm,
            page_height - 27 * mm,
            width=48 * mm,
            height=24 * mm,
            preserveAspectRatio=True,
            anchor="sw",
            mask="auto"
        )
    else:
        canvas.setFillColor(colors.HexColor("#087E75"))
        canvas.setFont("Helvetica-Bold", 17)
        canvas.drawString(18 * mm, page_height - 18 * mm, "MediTrust")

    # Header right text
    canvas.setFillColor(colors.HexColor("#17324D"))
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawRightString(
        page_width - 18 * mm,
        page_height - 17 * mm,
        "PATIENT HEALTH HISTORY"
    )

    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(
        page_width - 18 * mm,
        page_height - 22 * mm,
        "Your Health. Our Priority."
    )

    # Header bottom line
    canvas.setStrokeColor(colors.HexColor("#dbe4e8"))
    canvas.line(
        18 * mm, page_height - 30 * mm,
        page_width - 18 * mm, page_height - 30 * mm
    )

    # Footer
    canvas.setStrokeColor(colors.HexColor("#dbe4e8"))
    canvas.line(
        18 * mm, 14 * mm,
        page_width - 18 * mm, 14 * mm
    )

    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.setFont("Helvetica", 8)

    canvas.drawString(
        18 * mm, 9 * mm,
        "Confidential Patient Health History"
    )

    canvas.drawRightString(
        page_width - 18 * mm, 9 * mm,
        f"Page {document.page}"
    )

    canvas.restoreState()

def generate_health_history_pdf(output_path, patient, measurements):
    """
    Generate a basic patient health history PDF.

    patient:
        Dictionary containing patient information.

    measurements:
        Dictionary containing health measurement lists.
    """

    document = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=34 * mm,
        bottomMargin=20 * mm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "MediTrustTitle",
        parent=styles["Title"],
        fontSize=24,
        textColor=colors.HexColor("#176b60"),
        alignment=TA_CENTER,
        spaceAfter=8
    )

    subtitle_style = ParagraphStyle(
        "MediTrustSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        alignment=TA_CENTER,
        spaceAfter=20
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#176b60"),
        spaceBefore=16,
        spaceAfter=8
    )

    normal_style = styles["Normal"]

    story = []

    # REPORT TITLE
    story.append(Paragraph("MediTrust", title_style))
    story.append(
        Paragraph("PATIENT HEALTH HISTORY REPORT", subtitle_style)
    )


    # PATIENT INFORMATION CARD
    story.append(Paragraph("Patient Information", heading_style))

    patient_data = [
        ["PATIENT PROFILE", ""],
        ["Patient Name", str(patient.get("full_name") or "Not available")],
        ["Patient ID", str(patient.get("global_pid") or "Not available")],
        ["Date of Birth", str(patient.get("date_of_birth") or "Not available")],
        ["Report Generated", str(patient.get("generated_at") or "Not available")]
    ]

    patient_table = Table(
        patient_data,
        colWidths=[45 * mm, 115 * mm]
    )

    patient_table.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#087E75")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),

        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#E8F5F3")),
        ("BACKGROUND", (1, 1), (1, -1), colors.HexColor("#F8FAFC")),

        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#17324D")),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 1), (1, -1), "Helvetica"),

        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 1), (-1, -1), 0.5, colors.HexColor("#D5E5E2")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#087E75")),

        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),

        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")
    ]))

    story.append(patient_table)
    story.append(Spacer(1, 15))


    # HEALTH SUMMARY CARDS
    story.append(Paragraph("Health Summary", heading_style))

    def get_latest(records):
        if not records:
            return None

        return max(
            records,
            key=lambda r: str(r.get("recorded_at") or "")
        )

    summary_items = []

    # Blood Sugar - latest reading for each type
    sugar_types = {
        "blood_sugar_fasting": "Blood Sugar - Fasting",
        "blood_sugar_post_meal": "Blood Sugar - Post-meal",
        "blood_sugar_random": "Blood Sugar - Random",
        "blood_sugar_hba1c": "Blood Sugar - HbA1c"
    }

    sugar_records = measurements.get("blood_sugar", [])

    for measurement_type, label in sugar_types.items():
        matching = [
            r for r in sugar_records
            if r.get("measurement_type") == measurement_type
        ]

        latest = get_latest(matching)

        if latest:
            summary_items.append((
                label,
                str(latest.get("value", "—")),
                str(latest.get("unit", ""))
            ))

    # Other health measurements
    other_metrics = [
        ("Blood Pressure", "blood_pressure", "mmHg"),
        ("Heart Rate", "heart_rate", "BPM"),
        ("Weight", "weight", "kg"),
        ("Sleep", "sleep", "hours"),
        ("Temperature", "temperature", "°C")
    ]

    for label, key, unit in other_metrics:
        latest = get_latest(measurements.get(key, []))

        if not latest:
            continue

        if key == "blood_pressure":
            value = (
                f"{latest.get('value', '—')}/"
                f"{latest.get('secondary_value', '—')}"
            )

        else:
            value = str(latest.get("value", "—"))

        summary_items.append((label, value, unit))

    # Create individual summary cards
    if summary_items:

        card_rows = []

        for i in range(0, len(summary_items), 3):

            row = []

            for label, value, unit in summary_items[i:i + 3]:

                label_style = ParagraphStyle(
                    "CardLabel",
                    parent=normal_style,
                    fontName="Helvetica-Bold",
                    fontSize=8,
                    textColor=colors.HexColor("#087E75"),
                    leading=11
                )

                value_style = ParagraphStyle(
                    "CardValue",
                    parent=normal_style,
                    fontName="Helvetica-Bold",
                    fontSize=16,
                    textColor=colors.HexColor("#17324D"),
                    leading=20
                )

                unit_style = ParagraphStyle(
                    "CardUnit",
                    parent=normal_style,
                    fontSize=8,
                    textColor=colors.HexColor("#64748b"),
                    leading=11
                )

                card_content = [
                    [Paragraph(label, label_style)],
                    [Paragraph(value, value_style)],
                    [Paragraph(unit, unit_style)]
                ]

                card = Table(
                    card_content,
                    colWidths=[49 * mm]
                )

                card.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1),
                     colors.HexColor("#F0F9F7")),
                    ("BOX", (0, 0), (-1, -1), 0.8,
                     colors.HexColor("#B7DED7")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 9),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]))

                row.append(card)

            # Fill incomplete rows with empty spaces
            while len(row) < 3:
                row.append("")

            card_rows.append(row)

        summary_table = Table(
            card_rows,
            colWidths=[53 * mm, 53 * mm, 53 * mm],
            hAlign="LEFT"
        )

        summary_table.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 1),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        story.append(summary_table)

    else:
        story.append(
            Paragraph("No health measurements available.", normal_style)
        )

    story.append(Spacer(1, 15))




    # HEALTH MEASUREMENT SECTIONS

    measurement_sections = [
        ("Blood Sugar", "blood_sugar"),
        ("Blood Pressure", "blood_pressure"),
        ("Heart Rate", "heart_rate"),
        ("Weight", "weight"),
        ("Sleep Tracking", "sleep"),
        ("Temperature", "temperature")
    ]

    cell_style = ParagraphStyle(
        "HistoryCell",
        parent=normal_style,
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155")
    )

    header_cell_style = ParagraphStyle(
        "HistoryHeader",
        parent=normal_style,
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.white
    )

    def make_cell(value, style=cell_style):
        return Paragraph(escape(str(value)), style)

    for section_title, measurement_key in measurement_sections:

        story.append(Paragraph(section_title, heading_style))

        records = measurements.get(measurement_key, [])

        if not records:
            story.append(
                Paragraph(
                    "No records available for this period.",
                    normal_style
                )
            )
            story.append(Spacer(1, 10))
            continue

        # BLOOD PRESSURE
        if measurement_key == "blood_pressure":

            headers = [
                "Systolic",
                "Diastolic",
                "Unit",
                "Recorded At"
            ]

            column_widths = [
                30 * mm, 30 * mm, 20 * mm, 94 * mm
            ]

            table_data = [
                [make_cell(h, header_cell_style) for h in headers]
            ]

            for record in records:
                table_data.append([
                    make_cell(record.get("value", "—")),
                    make_cell(record.get("secondary_value", "—")),
                    make_cell(record.get("unit", "—")),
                    make_cell(record.get("recorded_at", "—"))
                ])

        # SLEEP TRACKING
        elif measurement_key == "sleep":

            headers = [
                "Duration",
                "Efficiency",
                "Awake Minutes",
                "Sleep Start",
                "Wake-up"
            ]

            column_widths = [
                28 * mm, 25 * mm, 28 * mm, 46 * mm, 47 * mm
            ]

            table_data = [
                [make_cell(h, header_cell_style) for h in headers]
            ]

            for record in records:
                efficiency = record.get("secondary_value")

                table_data.append([
                    make_cell(f"{record.get('value', '—')} hours"),
                    make_cell(
                        f"{efficiency}%"
                        if efficiency is not None else "—"
                    ),
                    make_cell(record.get("awake_minutes", "—")),
                    make_cell(record.get("recorded_at", "—")),
                    make_cell(record.get("ended_at", "—"))
                ])

        # OTHER MEASUREMENTS
        else:

            headers = [
                "Value",
                "Unit",
                "Context",
                "Recorded At"
            ]

            column_widths = [
                28 * mm, 20 * mm, 42 * mm, 84 * mm
            ]

            table_data = [
                [make_cell(h, header_cell_style) for h in headers]
            ]

            for record in records:
                table_data.append([
                    make_cell(record.get("value", "—")),
                    make_cell(record.get("unit", "—")),
                    make_cell(record.get("context") or "—"),
                    make_cell(record.get("recorded_at", "—"))
                ])

        # CREATE STYLED TABLE
        data_table = Table(
            table_data,
            colWidths=column_widths,
            repeatRows=1,
            splitByRow=1,
            hAlign="LEFT"
        )

        data_table.setStyle(TableStyle([
            # Header
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#087E75")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("LINEBELOW", (0, 0), (-1, 0), 1,
             colors.HexColor("#065F59")),

            # Body
            ("TEXTCOLOR", (0, 1), (-1, -1),
             colors.HexColor("#334155")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#F0F7F6")
            ]),

            # Borders and spacing
            ("GRID", (0, 0), (-1, -1), 0.4,
             colors.HexColor("#D8E5E3")),
            ("BOX", (0, 0), (-1, -1), 0.8,
             colors.HexColor("#B7CEC9")),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE")
        ]))

        story.append(data_table)
        story.append(Spacer(1, 14))



    # HEALTH TREND GRAPHS

    story.append(Paragraph("Health Trend Analysis", heading_style))

    def add_trend_chart(title, records, series_config):
        """
        series_config: list of (label, field, colour)
        """

        if not records or len(records) < 2:
            return

        # Sort readings from oldest to newest
        records = sorted(
            records,
            key=lambda r: str(r.get("recorded_at") or "")
        )

        dates = []
        series_data = [[] for _ in series_config]

        for record in records:
            date_value = str(record.get("recorded_at") or "Unknown")

            # Short date label
            date_label = date_value[:16]
            dates.append(date_label)

            for index, (label, field, colour) in enumerate(series_config):
                try:
                    value = float(record.get(field))
                except (TypeError, ValueError):
                    value = None

                series_data[index].append(value)

        # Keep only records where all required values exist
        valid_indices = [
            i for i in range(len(dates))
            if all(series[i] is not None for series in series_data)
        ]

        if len(valid_indices) < 2:
            return

        dates = [dates[i] for i in valid_indices]
        series_data = [
            [series[i] for i in valid_indices]
            for series in series_data
        ]

        all_values = [
            value
            for series in series_data
            for value in series
        ]

        minimum = min(all_values)
        maximum = max(all_values)

        padding = max((maximum - minimum) * 0.15, 1)

        chart = HorizontalLineChart()
        chart.x = 45
        chart.y = 35
        chart.width = 390
        chart.height = 125

        chart.data = series_data

        chart.categoryAxis.categoryNames = dates
        chart.categoryAxis.labels.fontName = "Helvetica"
        chart.categoryAxis.labels.fontSize = 6
        chart.categoryAxis.labels.angle = 30

        chart.valueAxis.valueMin = max(0, minimum - padding)
        chart.valueAxis.valueMax = maximum + padding
        chart.valueAxis.valueStep = max(
            (chart.valueAxis.valueMax - chart.valueAxis.valueMin) / 5,
            1
        )

        chart.valueAxis.labels.fontSize = 7

        for index, (label, field, colour) in enumerate(series_config):
            chart.lines[index].strokeColor = colors.HexColor(colour)
            chart.lines[index].strokeWidth = 2

        drawing = Drawing(450, 190)
        drawing.add(chart)

        story.append(Paragraph(title, heading_style))
        story.append(drawing)

        # Legend
        legend_text = "     ".join(
            f'<font color="{colour}">●</font> '
            f'<b>{label}</b>'
            for label, field, colour in series_config
        )

        story.append(
            Paragraph(
                legend_text,
                ParagraphStyle(
                    "GraphLegend",
                    parent=normal_style,
                    fontSize=8,
                    alignment=TA_CENTER,
                    spaceAfter=12
                )
            )
        )

    # Blood Sugar - separate graphs for each type
    sugar_types = [
        ("blood_sugar_fasting", "Fasting"),
        ("blood_sugar_post_meal", "Post-meal"),
        ("blood_sugar_random", "Random"),
        ("blood_sugar_hba1c", "HbA1c")
    ]

    sugar_records = measurements.get("blood_sugar", [])

    for measurement_type, label in sugar_types:
        matching = [
            r for r in sugar_records
            if r.get("measurement_type") == measurement_type
        ]

        add_trend_chart(
            f"Blood Sugar - {label}",
            matching,
            [
                ("Reading", "value", "#087E75")
            ]
        )

    # Blood Pressure - two lines in one graph
    add_trend_chart(
        "Blood Pressure Trend",
        measurements.get("blood_pressure", []),
        [
            ("Systolic", "value", "#087E75"),
            ("Diastolic", "secondary_value", "#2563EB")
        ]
    )

    # Other health trends
    other_graphs = [
        ("Heart Rate Trend", "heart_rate", "BPM"),
        ("Weight Trend", "weight", "kg"),
        ("Sleep Duration Trend", "sleep", "hours"),
        ("Temperature Trend", "temperature", "°C")
    ]

    for title, key, unit in other_graphs:
        add_trend_chart(
            title,
            measurements.get(key, []),
            [
                (unit, "value", "#087E75")
            ]
        )

    story.append(Spacer(1, 12))



    # DISCLAIMER
    story.append(Spacer(1, 15))
    story.append(Paragraph("Important Disclaimer", heading_style))

    disclaimer = (
        "This report is generated from information recorded in MediTrust. "
        "It is intended to help organize health information for discussion "
        "with healthcare professionals. It is not a medical diagnosis, "
        "and the report does not replace professional medical advice."
    )

    story.append(Paragraph(disclaimer, normal_style))

    # GENERATE PDF
    document.build(
        story,
        onFirstPage=add_page_design,
        onLaterPages=add_page_design
    )
