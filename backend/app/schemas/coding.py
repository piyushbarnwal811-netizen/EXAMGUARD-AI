from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

CodeLanguage = Literal["python", "cpp", "java"]
ContestStatus = Literal["LOCKED", "ACTIVE", "ENDED"]
CaseVisibility = Literal["VISIBLE", "HIDDEN"]
CaseStatus = Literal["PASSED", "FAILED"]


class VisibleSampleOut(BaseModel):
    case_number: int
    input_data: str
    expected_output: str


class CodingProblemOut(BaseModel):
    id: int
    title: str
    statement: str
    input_format: str
    output_format: str
    constraints: str
    enabled_languages: list[CodeLanguage]
    starter_code: dict[str, str]
    visible_samples: list[VisibleSampleOut]


class ContestFinalResultOut(BaseModel):
    submission_id: int
    problem_id: int
    language: CodeLanguage
    score: float
    passed_cases: int
    total_cases: int
    submitted_at: datetime
    auto_submitted: bool = False


class ContestGateOut(BaseModel):
    status: ContestStatus
    server_time: datetime
    start_time: datetime | None
    end_time: datetime | None
    remaining_seconds: int
    problem: CodingProblemOut | None = None
    problems: list[CodingProblemOut] = Field(default_factory=list)
    submitted_problem_ids: list[int] = Field(default_factory=list)
    final_result: ContestFinalResultOut | None = None
    final_results: list[ContestFinalResultOut] = Field(default_factory=list)
    message: str | None = None


class ContestScheduleIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    start_time: datetime
    end_time: datetime
    is_published: bool = True

    @model_validator(mode="after")
    def validate_window(self) -> "ContestScheduleIn":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        return self


class ContestScheduleOut(BaseModel):
    id: int
    title: str
    start_time: datetime
    end_time: datetime
    is_published: bool
    server_time: datetime
    status: ContestStatus
    remaining_seconds: int


class ExamHistoryOut(BaseModel):
    id: int
    title: str
    start_time: datetime
    end_time: datetime
    is_published: bool
    status: ContestStatus
    total_submissions: int
    students_submitted: int


class CodeRunRequest(BaseModel):
    problem_id: int
    language: CodeLanguage
    source_code: str = Field(..., min_length=1, max_length=100_000)

    @field_validator("source_code")
    @classmethod
    def validate_source_code(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source_code cannot be empty.")
        return value


class CodeDebugRequest(BaseModel):
    language: CodeLanguage
    source_code: str = Field(..., min_length=1, max_length=100_000)
    error_logs: str = Field(..., min_length=1, max_length=8_000)

    @field_validator("source_code", "error_logs")
    @classmethod
    def validate_debug_input(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Debug input cannot be empty.")
        return value


class CodeDebugOut(BaseModel):
    has_error: bool = True
    error_line: int | None = Field(default=None, ge=1)
    error_summary: str = Field(..., min_length=1, max_length=240)
    detailed_explanation: str = Field(..., min_length=1, max_length=2_000)
    fix_hint: str = Field(..., min_length=1, max_length=600)


class CodeSubmitRequest(CodeRunRequest):
    auto_submitted: bool = False


class CodeDraftSaveRequest(BaseModel):
    problem_id: int
    language: CodeLanguage
    source_code: str = Field(default="", max_length=100_000)


class CodeDraftOut(BaseModel):
    problem_id: int
    language: CodeLanguage
    updated_at: datetime
    saved: bool


class CodeDraftAutoSubmitRequest(BaseModel):
    problem_id: int
    reason: str = Field(default="emergency_exit", max_length=80)


class TestCaseResultOut(BaseModel):
    case_number: int
    visibility: CaseVisibility
    status: CaseStatus
    input_data: str | None = None
    expected_output: str | None = None
    actual_output: str | None = None
    error_logs: str | None = None


class CodingTestCaseAdminOut(BaseModel):
    id: int | None = None
    sort_order: int
    input_data: str
    expected_output: str
    is_visible: bool = False


class CodingTestCaseIn(BaseModel):
    input_data: str = Field(..., min_length=1, max_length=20_000)
    expected_output: str = Field(..., min_length=1, max_length=20_000)
    is_visible: bool = False


class CodingProblemAdminOut(BaseModel):
    id: int
    contest_id: int
    order_index: int = 1
    title: str
    statement: str
    input_format: str
    output_format: str
    constraints: str
    enabled_languages: list[CodeLanguage]
    starter_code_python: str
    starter_code_cpp: str
    starter_code_java: str
    test_cases: list[CodingTestCaseAdminOut]


class CodingProblemUpdateIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=180)
    statement: str = Field(..., min_length=1, max_length=50_000)
    input_format: str = Field(..., min_length=1, max_length=20_000)
    output_format: str = Field(..., min_length=1, max_length=20_000)
    constraints: str = Field(..., min_length=1, max_length=20_000)
    starter_code_python: str = Field(default="", min_length=0, max_length=100_000)
    starter_code_cpp: str = Field(default="", min_length=0, max_length=100_000)
    starter_code_java: str = Field(default="", min_length=0, max_length=100_000)
    enabled_languages: list[CodeLanguage] = Field(default_factory=lambda: ["python", "cpp", "java"])
    test_cases: list[CodingTestCaseIn] = Field(..., min_length=10, max_length=10)

    @model_validator(mode="after")
    def validate_test_cases(self) -> "CodingProblemUpdateIn":
        visible_count = sum(1 for test_case in self.test_cases if test_case.is_visible)
        if visible_count != 2:
            raise ValueError("Exactly 2 test cases must be marked visible.")
        if not self.enabled_languages:
            raise ValueError("At least one language must be enabled.")
        allowed = {"python", "cpp", "java"}
        if set(self.enabled_languages) - allowed:
            raise ValueError("Unsupported language selected.")

        starter_map = {
            "python": self.starter_code_python,
            "cpp": self.starter_code_cpp,
            "java": self.starter_code_java,
        }
        for language in self.enabled_languages:
            code = starter_map.get(language, "")
            if not code.strip():
                raise ValueError(f"Starter code is required for enabled language: {language}.")
        return self


class CodingProblemSaveIn(CodingProblemUpdateIn):
    id: int | None = Field(default=None, ge=1)


class CodingProblemsUpdateIn(BaseModel):
    problems: list[CodingProblemSaveIn] = Field(..., min_length=1, max_length=25)


class CodeExecutionOut(BaseModel):
    problem_id: int
    language: CodeLanguage
    score: float
    passed_cases: int
    total_cases: int
    visible_results: list[TestCaseResultOut]
    hidden_results: list[TestCaseResultOut]
    submitted: bool = False
    submission_id: int | None = None
