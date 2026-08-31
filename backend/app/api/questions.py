import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import re
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.config import get_settings
from app.core.security import require_admin

router = APIRouter(prefix="/questions", tags=["questions"])
logger = logging.getLogger(__name__)

DIFFICULTIES = {"Easy", "Medium", "Hard"}
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_GEMINI_TIMEOUT_SECONDS = 90
SYSTEM_PROMPT = """
You are an expert technical examiner creating programming exam questions.

Return ONLY a raw JSON array of objects. Do not include markdown, explanations,
comments, headings, or ```json code blocks.

Each object must match this exact structure:
[
  {
    "title": "Short descriptive title",
    "statement": "Detailed problem description",
    "input_format": "What the program reads from stdin",
    "output_format": "What the program prints to stdout",
    "constraints": "Important limits and assumptions",
    "sample_input": "Sample input value",
    "sample_output": "Sample output value",
    "starter_code_python": "A scaffold, not the full solution",
    "starter_code_cpp": "A scaffold, not the full solution",
    "starter_code_java": "A scaffold, not the full solution",
    "test_cases": [
      {
        "input_data": "stdin input",
        "expected_output": "stdout output",
        "is_visible": true
      }
    ]
  }
]

Each question must include exactly 10 test_cases. Exactly 2 test_cases must have
is_visible true. The sample_input/sample_output must match the first visible
test case. Keep starter code as compilable scaffolding, not a complete answer.
Make the questions clear, technically accurate, and suitable for assessment.
Create original questions for every request. Vary titles, scenarios, constraints,
sample data, and hidden test data instead of reusing common template problems.
""".strip()


class QuestionGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=160)
    difficulty: str
    count: int = Field(default=3, ge=1, le=10)

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("topic cannot be empty.")
        return cleaned

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value: str) -> str:
        normalized = value.strip().title()
        if normalized not in DIFFICULTIES:
            raise ValueError("difficulty must be one of: Easy, Medium, Hard.")
        return normalized


class GeneratedTestCase(BaseModel):
    input_data: str = Field(..., min_length=1, max_length=20_000)
    expected_output: str = Field(..., min_length=1, max_length=20_000)
    is_visible: bool = False


class GeneratedQuestion(BaseModel):
    title: str = Field(..., min_length=1, max_length=180)
    statement: str = Field(..., min_length=1)
    input_format: str = Field(default="", max_length=20_000)
    output_format: str = Field(default="", max_length=20_000)
    constraints: str = Field(default="", max_length=20_000)
    sample_input: str = Field(default="", max_length=20_000)
    sample_output: str = Field(default="", max_length=20_000)
    starter_code_python: str = Field(default="", max_length=100_000)
    starter_code_cpp: str = Field(default="", max_length=100_000)
    starter_code_java: str = Field(default="", max_length=100_000)
    test_cases: list[GeneratedTestCase] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_and_fill_sample_from_cases(self) -> "GeneratedQuestion":
        if len(self.test_cases) != 10:
            raise ValueError("Each generated question must include exactly 10 test_cases.")

        visible_cases = [test_case for test_case in self.test_cases if test_case.is_visible]
        if len(visible_cases) != 2:
            raise ValueError("Each generated question must include exactly 2 visible test_cases.")

        first_case = visible_cases[0] if visible_cases else (self.test_cases[0] if self.test_cases else None)
        if first_case:
            if not self.sample_input:
                self.sample_input = first_case.input_data
            if not self.sample_output:
                self.sample_output = first_case.expected_output
        return self


class QuestionGenerateResponse(BaseModel):
    topic: str
    difficulty: str
    count: int
    source: str = "gemini"
    generation_id: str
    questions: list[GeneratedQuestion]


class GeminiDependencyError(RuntimeError):
    pass


class GeminiResponseError(RuntimeError):
    pass


def _build_prompt(payload: QuestionGenerateRequest, generation_id: str) -> str:
    requested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return (
        f'Generate exactly {payload.count} {payload.difficulty} technical exam '
        f'question(s) for the topic: "{payload.topic}".\n'
        f"Unique generation id: {generation_id}.\n"
        f"Requested at: {requested_at}.\n"
        "Use the unique generation id as a creativity seed. Do not repeat "
        "questions, samples, constraints, or hidden tests from previous requests."
    )


def _bounded_timeout_seconds(value: object) -> int:
    try:
        timeout_seconds = int(value)
    except (TypeError, ValueError):
        timeout_seconds = DEFAULT_GEMINI_TIMEOUT_SECONDS
    return max(30, min(timeout_seconds, 300))


def _clean_ai_json_text(raw_text: str) -> str:
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip().strip("`").strip()

    if not text.startswith("["):
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]

    return text


def _extract_response_text(response: Any) -> str:
    try:
        text = response.text
    except ValueError:
        text = ""

    if text:
        return text

    candidates = getattr(response, "candidates", []) or []
    chunks: list[str] = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", "")
            if part_text:
                chunks.append(part_text)

    return "\n".join(chunks).strip()


def _parse_questions(raw_text: str) -> list[GeneratedQuestion]:
    cleaned_text = _clean_ai_json_text(raw_text)
    try:
        loaded = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise GeminiResponseError("Gemini returned invalid JSON.") from exc

    if not isinstance(loaded, list):
        raise GeminiResponseError("Gemini response must be a JSON array.")

    try:
        return [GeneratedQuestion.model_validate(item) for item in loaded]
    except ValidationError as exc:
        raise GeminiResponseError(
            "Gemini response did not match the expected question schema."
        ) from exc


def _starter_code() -> dict[str, str]:
    return {
        "starter_code_python": (
            "import sys\n\n"
            "def solve():\n"
            "    data = sys.stdin.read().strip().split()\n"
            "    # TODO: parse input and print the answer.\n"
            "    pass\n\n"
            "if __name__ == \"__main__\":\n"
            "    solve()\n"
        ),
        "starter_code_cpp": (
            "#include <bits/stdc++.h>\n"
            "using namespace std;\n\n"
            "int main() {\n"
            "    ios::sync_with_stdio(false);\n"
            "    cin.tie(nullptr);\n"
            "    // TODO: parse input and print the answer.\n"
            "    return 0;\n"
            "}\n"
        ),
        "starter_code_java": (
            "import java.io.*;\n"
            "import java.util.*;\n\n"
            "public class Main {\n"
            "    public static void main(String[] args) throws Exception {\n"
            "        Scanner sc = new Scanner(System.in);\n"
            "        // TODO: parse input and print the answer.\n"
            "    }\n"
            "}\n"
        ),
    }


def _seed_value(generation_id: str, index: int) -> int:
    digest = hashlib.sha256(f"{generation_id}:{index}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _case(input_data: str, expected_output: object, is_visible: bool = False) -> dict[str, object]:
    return {
        "input_data": input_data,
        "expected_output": f"{expected_output}\n",
        "is_visible": is_visible,
    }


def _threshold_counter_cases(seed: int) -> list[dict[str, object]]:
    cases = []
    for idx in range(10):
        n = 5 + (seed + idx) % 5
        threshold = 3 + (seed + idx * 2) % 12
        values = [((seed // (j + 3)) + idx * 5 + j * 3) % 20 for j in range(n)]
        expected = sum(1 for value in values if value >= threshold)
        cases.append(
            _case(
                f"{n} {threshold}\n{' '.join(map(str, values))}\n",
                expected,
                idx < 2,
            )
        )
    return cases


def _pair_sum_cases(seed: int) -> list[dict[str, object]]:
    cases = []
    for idx in range(10):
        n = 5 + (seed + idx) % 5
        values = [((seed // (j + 5)) + idx + j * 2) % 13 for j in range(n)]
        target = values[0] + values[-1] if idx % 2 == 0 else 8 + (seed + idx) % 10
        expected = sum(
            1
            for left in range(n)
            for right in range(left + 1, n)
            if values[left] + values[right] == target
        )
        cases.append(
            _case(
                f"{n}\n{' '.join(map(str, values))}\n{target}\n",
                expected,
                idx < 2,
            )
        )
    return cases


def _unique_token_cases(seed: int) -> list[dict[str, object]]:
    words = ["alpha", "beta", "delta", "logic", "stack", "node", "query", "model"]
    cases = []
    for idx in range(10):
        n = 6 + (seed + idx) % 5
        values = [words[(seed + idx + j) % len(words)] for j in range(n)]
        if idx % 3 != 0:
            values[idx % n] = f"solo{idx}"
        counts = {word: values.count(word) for word in values}
        expected = next((word for word in values if counts[word] == 1), "NONE")
        cases.append(_case(f"{n}\n{' '.join(values)}\n", expected, idx < 2))
    return cases


def _max_prefix_cases(seed: int) -> list[dict[str, object]]:
    cases = []
    for idx in range(10):
        n = 5 + (seed + idx) % 6
        values = [((seed // (j + 7)) + idx * 3 + j) % 17 - 8 for j in range(n)]
        running = 0
        best = values[0]
        for value in values:
            running += value
            best = max(best, running)
        cases.append(
            _case(
                f"{n}\n{' '.join(map(str, values))}\n",
                best,
                idx < 2,
            )
        )
    return cases


def _local_fallback_questions(
    payload: QuestionGenerateRequest,
    generation_id: str,
) -> list[GeneratedQuestion]:
    templates = [
        (
            "Threshold Counter",
            "Given a list of scores from a {topic} practice set, count how many values are greater than or equal to a required threshold.",
            "The first line contains N and T. The second line contains N integers.",
            "Print one integer: the number of values at least T.",
            "1 <= N <= 100000; values fit in signed 32-bit integers.",
            _threshold_counter_cases,
        ),
        (
            "Pair Sum Audit",
            "For a {topic} validation batch, count index pairs whose values add up to a target.",
            "The first line contains N. The second line contains N integers. The third line contains target K.",
            "Print the number of pairs (i, j), i < j, where Ai + Aj = K.",
            "2 <= N <= 5000; use efficient counting for larger inputs.",
            _pair_sum_cases,
        ),
        (
            "First Unique Token",
            "A {topic} logger emits tokens. Find the first token that appears exactly once.",
            "The first line contains N. The second line contains N lowercase tokens.",
            "Print the first unique token, or NONE if every token repeats.",
            "1 <= N <= 100000; token length <= 30.",
            _unique_token_cases,
        ),
        (
            "Best Prefix Balance",
            "During a {topic} simulation, each step changes a running balance. Report the maximum prefix balance.",
            "The first line contains N. The second line contains N integers.",
            "Print the maximum value reached by any non-empty prefix sum.",
            "1 <= N <= 100000; step values fit in signed 32-bit integers.",
            _max_prefix_cases,
        ),
    ]
    starters = _starter_code()
    questions = []
    for index in range(payload.count):
        seed = _seed_value(generation_id, index)
        title, statement, input_format, output_format, constraints, case_builder = (
            templates[index % len(templates)]
        )
        test_cases = case_builder(seed)
        first_visible = next(item for item in test_cases if item["is_visible"])
        questions.append(
            GeneratedQuestion.model_validate(
                {
                    "title": f"{payload.topic} {title}",
                    "statement": statement.format(topic=payload.topic),
                    "input_format": input_format,
                    "output_format": output_format,
                    "constraints": f"{constraints} Difficulty: {payload.difficulty}.",
                    "sample_input": first_visible["input_data"],
                    "sample_output": first_visible["expected_output"],
                    **starters,
                    "test_cases": test_cases,
                }
            )
        )
    return questions


def _generate_questions_with_gemini(
    api_key: str,
    payload: QuestionGenerateRequest,
    generation_id: str,
    model_name: str,
    timeout_seconds: int = DEFAULT_GEMINI_TIMEOUT_SECONDS,
) -> list[GeneratedQuestion]:
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise GeminiDependencyError(
            "Missing dependency: install google-generativeai."
        ) from exc

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name,
        system_instruction=SYSTEM_PROMPT,
    )
    response = model.generate_content(
        _build_prompt(payload, generation_id),
        generation_config={
            "max_output_tokens": min(32768, max(8192, payload.count * 4096)),
            "response_mime_type": "application/json",
        },
        request_options={"timeout": timeout_seconds},
    )
    raw_text = _extract_response_text(response)
    if not raw_text:
        raise GeminiResponseError("Gemini returned an empty response.")
    return _parse_questions(raw_text)


@router.post(
    "/generate",
    response_model=QuestionGenerateResponse,
    response_model_exclude_none=True,
)
async def generate_questions(
    payload: QuestionGenerateRequest,
    _admin: dict[str, object] = Depends(require_admin),
) -> QuestionGenerateResponse:
    settings = get_settings()
    api_key = os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY
    model_name = (
        os.getenv("GEMINI_MODEL")
        or getattr(settings, "GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        or DEFAULT_GEMINI_MODEL
    )
    timeout_seconds = _bounded_timeout_seconds(
        os.getenv("GEMINI_TIMEOUT_SECONDS")
        or getattr(settings, "GEMINI_TIMEOUT_SECONDS", DEFAULT_GEMINI_TIMEOUT_SECONDS)
    )
    remote_enabled_raw = os.getenv("GEMINI_REMOTE_ENABLED")
    remote_enabled = (
        remote_enabled_raw.strip().lower() in {"1", "true", "yes", "on"}
        if remote_enabled_raw is not None
        else bool(getattr(settings, "GEMINI_REMOTE_ENABLED", True))
    )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API key is not configured. Add GEMINI_API_KEY in backend/.env.",
        )

    if not remote_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini question generation is disabled. Set GEMINI_REMOTE_ENABLED=true.",
        )

    generation_id = secrets.token_urlsafe(12)
    source = "gemini"
    try:
        questions = await asyncio.wait_for(
            run_in_threadpool(
                _generate_questions_with_gemini,
                api_key,
                payload,
                generation_id,
                model_name,
                timeout_seconds,
            ),
            timeout=timeout_seconds + 5,
        )
        if len(questions) != payload.count:
            raise GeminiResponseError(
                f"Gemini returned {len(questions)} question(s), expected {payload.count}."
            )
    except asyncio.TimeoutError as exc:
        logger.warning("Gemini question generation timed out; using local fallback.")
        questions = _local_fallback_questions(payload, generation_id)
        source = "local_fallback"
    except GeminiDependencyError as exc:
        logger.warning("%s Using local fallback.", exc)
        questions = _local_fallback_questions(payload, generation_id)
        source = "local_fallback"
    except GeminiResponseError as exc:
        logger.warning("%s Using local fallback.", exc)
        questions = _local_fallback_questions(payload, generation_id)
        source = "local_fallback"
    except Exception as exc:
        logger.exception("Gemini question generation failed.")
        questions = _local_fallback_questions(payload, generation_id)
        source = "local_fallback"

    return QuestionGenerateResponse(
        topic=payload.topic,
        difficulty=payload.difficulty,
        count=len(questions),
        source=source,
        generation_id=generation_id,
        questions=questions,
    )
