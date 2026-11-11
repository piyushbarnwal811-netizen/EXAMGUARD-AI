from datetime import datetime, timezone

from openpyxl import Workbook

from app.api.admin import _build_report_rows, _format_report_worksheet
from app.db.models import ExamLog, Student


def test_report_marks_camera_detected_mobile_phone():
    first_detection = datetime(2026, 11, 11, 8, 0, tzinfo=timezone.utc)
    latest_detection = datetime(2026, 11, 11, 8, 5, tzinfo=timezone.utc)
    student = Student(
        id=1,
        roll_no="ROLL001",
        name="Test Student",
        email="student@example.com",
        is_pin_used=False,
    )
    student_without_detection = Student(
        id=2,
        roll_no="ROLL002",
        name="Student Without Detection",
        email="student2@example.com",
        is_pin_used=False,
    )
    logs = [
        ExamLog(
            student_id=1,
            event_type="MOBILE_PHONE_DETECTED",
            timestamp=first_detection,
            details='{"detector":"MEDIAPIPE_OBJECT_DETECTOR"}',
        ),
        ExamLog(
            student_id=1,
            event_type="MOBILE_PHONE_DETECTED",
            timestamp=latest_detection,
            details='{"detector":"MEDIAPIPE_OBJECT_DETECTOR"}',
        ),
    ]

    rows = _build_report_rows(
        [student, student_without_detection],
        [],
        [],
        logs,
        [],
    )
    row, row_without_detection = rows

    assert row["name"] == "Test Student"
    assert row["mobile_phone_camera_detected"] == "YES"
    assert row["mobile_phone_camera_detection_count"] == 2
    assert row["mobile_phone_camera_first_detected_at"] == first_detection.isoformat()
    assert row["mobile_phone_camera_latest_detected_at"] == latest_detection.isoformat()
    assert row["ai_cheating_detected_count"] == 2
    assert row_without_detection["mobile_phone_camera_detected"] == "NO"
    assert row_without_detection["mobile_phone_camera_detection_count"] == 0


def test_report_worksheet_has_readable_filterable_headers():
    worksheet = Workbook().active
    worksheet.append(["name", "mobile_phone_camera_detected"])
    worksheet.append(["Test Student", "YES"])

    _format_report_worksheet(worksheet)

    assert worksheet.freeze_panes == "A2"
    assert worksheet.auto_filter.ref == "A1:B2"
    assert worksheet.sheet_view.showGridLines is False
    assert worksheet["A1"].font.bold is True
    assert worksheet["B2"].fill.fgColor.rgb.endswith("FCE4D6")
