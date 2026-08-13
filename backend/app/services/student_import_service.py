from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator

from app.schemas.student import normalize_roll_no

SUPPORTED_STUDENT_IMPORT_EXTENSIONS = {".csv", ".xlsx", ".xlsm", ".xls"}


class StudentSheetValidationError(Exception):
    def __init__(self, message: str, errors: list[dict[str, object]]) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors


class ImportedStudentRow(BaseModel):
    row_number: int
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    roll_no: str | None = Field(default=None, max_length=50)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("roll_no", mode="before")
    @classmethod
    def validate_roll_no(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = normalize_roll_no(str(value))
        return normalized or None


def _normalize_header(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _cell(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _column_for(
    columns_by_header: dict[str, object],
    aliases: tuple[str, ...],
) -> object | None:
    for alias in aliases:
        column = columns_by_header.get(alias)
        if column is not None:
            return column
    return None


def _clean_validation_errors(exc: ValidationError) -> list[dict[str, object]]:
    return [
        {
            "loc": list(error.get("loc", [])),
            "msg": error.get("msg", "Invalid value."),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]


def _read_sheet(content: bytes, filename: str) -> pd.DataFrame:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_STUDENT_IMPORT_EXTENSIONS:
        raise ValueError("Please upload a .csv, .xlsx, .xlsm, or .xls file.")

    buffer = io.BytesIO(content)
    try:
        if suffix == ".csv":
            return pd.read_csv(buffer, dtype=str, encoding="utf-8-sig")
        return pd.read_excel(buffer, dtype=str)
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be encoded as UTF-8.") from exc
    except ImportError as exc:
        raise ValueError(
            "This Excel format requires an optional parser dependency. "
            "Use .xlsx or install the missing Excel reader."
        ) from exc
    except Exception as exc:
        raise ValueError("The student sheet could not be read.") from exc


def parse_student_sheet(content: bytes, filename: str) -> list[ImportedStudentRow]:
    dataframe = _read_sheet(content, filename)
    if dataframe.empty:
        raise ValueError("Sheet does not contain any student rows.")

    columns_by_header = {
        _normalize_header(column): column for column in dataframe.columns
    }
    name_column = _column_for(
        columns_by_header,
        ("name", "student_name", "full_name"),
    )
    email_column = _column_for(
        columns_by_header,
        ("email", "email_id", "student_email"),
    )
    roll_no_column = _column_for(
        columns_by_header,
        ("roll_no", "roll", "roll_number", "student_id"),
    )

    missing = []
    if name_column is None:
        missing.append("name")
    if email_column is None:
        missing.append("email")
    if missing:
        raise ValueError(f"Sheet is missing required columns: {', '.join(missing)}.")

    students: list[ImportedStudentRow] = []
    errors: list[dict[str, object]] = []
    seen_emails: dict[str, int] = {}
    seen_roll_numbers: dict[str, int] = {}

    for index, raw_row in dataframe.iterrows():
        row_number = int(index) + 2
        row = {
            "row_number": row_number,
            "name": _cell(raw_row[name_column]),
            "email": _cell(raw_row[email_column]),
            "roll_no": _cell(raw_row[roll_no_column]) if roll_no_column is not None else None,
        }

        if not row["name"] and not row["email"] and not row["roll_no"]:
            continue

        try:
            student = ImportedStudentRow(**row)
        except ValidationError as exc:
            errors.append(
                {
                    "row": row_number,
                    "errors": _clean_validation_errors(exc),
                }
            )
            continue

        email = str(student.email)
        duplicate_row = seen_emails.get(email)
        if duplicate_row is not None:
            errors.append(
                {
                    "row": row_number,
                    "errors": [
                        {
                            "loc": ["email"],
                            "msg": f"Duplicate email also appears on row {duplicate_row}.",
                            "type": "duplicate_email",
                        }
                    ],
                }
            )
            continue

        if student.roll_no:
            duplicate_roll_row = seen_roll_numbers.get(student.roll_no)
            if duplicate_roll_row is not None:
                errors.append(
                    {
                        "row": row_number,
                        "errors": [
                            {
                                "loc": ["roll_no"],
                                "msg": (
                                    "Duplicate roll_no also appears on row "
                                    f"{duplicate_roll_row}."
                                ),
                                "type": "duplicate_roll_no",
                            }
                        ],
                    }
                )
                continue
            seen_roll_numbers[student.roll_no] = row_number

        seen_emails[email] = row_number
        students.append(student)

    if errors:
        raise StudentSheetValidationError("Invalid student sheet rows.", errors)
    if not students:
        raise ValueError("Sheet does not contain any student rows.")

    return students
