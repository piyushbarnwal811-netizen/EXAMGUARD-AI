from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import httpx

from app.config import get_settings
from app.db.models import CodingTestCase

settings = get_settings()


@dataclass(frozen=True)
class LanguageRuntime:
    piston_language: str
    piston_version: str
    file_name: str


@dataclass(frozen=True)
class ExecutionCaseResult:
    case_number: int
    is_visible: bool
    passed: bool
    input_data: str
    expected_output: str
    actual_output: str
    error_logs: str


@dataclass(frozen=True)
class LocalProcessResult:
    stdout: str
    stderr: str
    return_code: int | None
    timed_out: bool = False


LANGUAGE_RUNTIMES: dict[str, LanguageRuntime] = {
    "python": LanguageRuntime("python", "*", "main.py"),
    "cpp": LanguageRuntime("cpp", "*", "main.cpp"),
    "java": LanguageRuntime("java", "*", "Main.java"),
}

_execution_semaphore = asyncio.Semaphore(
    max(1, settings.PISTON_MAX_CONCURRENT_EXECUTIONS)
)


def _normalize_output(value: str) -> str:
    lines = [line.rstrip() for line in value.replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def _stage_failed(stage: dict[str, object] | None) -> bool:
    if not stage:
        return True
    code = stage.get("code")
    return code not in (None, 0) or bool(stage.get("signal")) or bool(stage.get("status"))


def _stage_text(stage: dict[str, object] | None, label: str) -> list[str]:
    if not stage:
        return [f"{label}: missing execution stage"]

    chunks: list[str] = []
    for key in ("stdout", "stderr", "output", "message", "status", "signal"):
        value = stage.get(key)
        if value not in (None, ""):
            chunks.append(f"{label} {key}: {value}")
    return chunks


def _error_logs(data: dict[str, object]) -> str:
    compile_stage = data.get("compile")
    run_stage = data.get("run")
    chunks: list[str] = []

    if isinstance(compile_stage, dict) and _stage_failed(compile_stage):
        chunks.extend(_stage_text(compile_stage, "compile"))
    if isinstance(run_stage, dict) and _stage_failed(run_stage):
        chunks.extend(_stage_text(run_stage, "run"))
    if not isinstance(run_stage, dict):
        chunks.append("run: missing execution stage")

    return "\n".join(chunks)


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = settings.PISTON_API_TOKEN.strip()
    if token:
        scheme = settings.PISTON_AUTH_SCHEME.strip()
        header_value = f"{scheme} {token}" if scheme else token
        headers[settings.PISTON_AUTH_HEADER] = header_value
    return headers


def _failure_result(test_case: CodingTestCase, message: str) -> ExecutionCaseResult:
    return ExecutionCaseResult(
        case_number=test_case.sort_order,
        is_visible=test_case.is_visible,
        passed=False,
        input_data=test_case.input_data,
        expected_output=test_case.expected_output,
        actual_output="",
        error_logs=message,
    )


async def _run_local_process(
    command: Sequence[str],
    stdin: str,
    cwd: Path,
    timeout_ms: int,
) -> LocalProcessResult:
    kwargs: dict[str, object] = {
        "stdin": asyncio.subprocess.PIPE,
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
        "cwd": cwd,
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    process = await asyncio.create_subprocess_exec(*command, **kwargs)
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(stdin.encode()),
            timeout=max(1, timeout_ms / 1000),
        )
        return LocalProcessResult(
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            return_code=process.returncode,
        )
    except asyncio.TimeoutError:
        process.kill()
        stdout, stderr = await process.communicate()
        return LocalProcessResult(
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            return_code=None,
            timed_out=True,
        )


def _local_error(prefix: str, result: LocalProcessResult) -> str:
    if result.timed_out:
        return f"{prefix}: time limit exceeded"
    chunks = []
    if result.stderr.strip():
        chunks.append(result.stderr.strip())
    if result.stdout.strip():
        chunks.append(result.stdout.strip())
    detail = "\n".join(chunks).strip()
    if detail:
        return f"{prefix}: {detail}"
    return f"{prefix}: process exited with code {result.return_code}"


async def _execute_python_locally(
    source_code: str,
    test_case: CodingTestCase,
    workdir: Path,
) -> tuple[str, str, bool]:
    source_path = workdir / "main.py"
    source_path.write_text(source_code, encoding="utf-8")
    result = await _run_local_process(
        [sys.executable, "-I", "-B", str(source_path)],
        test_case.input_data,
        workdir,
        settings.PISTON_RUN_TIMEOUT_MS,
    )
    if result.timed_out or result.return_code not in (0, None):
        return result.stdout, _local_error("run", result), False
    return result.stdout, "", True


async def _execute_cpp_locally(
    source_code: str,
    test_case: CodingTestCase,
    workdir: Path,
) -> tuple[str, str, bool]:
    compiler = shutil.which("g++")
    if not compiler:
        return "", "local fallback: g++ is not installed", False

    source_path = workdir / "main.cpp"
    output_path = workdir / ("main.exe" if os.name == "nt" else "main")
    source_path.write_text(source_code, encoding="utf-8")
    compile_result = await _run_local_process(
        [compiler, str(source_path), "-std=c++17", "-O2", "-o", str(output_path)],
        "",
        workdir,
        settings.PISTON_COMPILE_TIMEOUT_MS,
    )
    if compile_result.timed_out or compile_result.return_code != 0:
        return "", _local_error("compile", compile_result), False

    run_result = await _run_local_process(
        [str(output_path)],
        test_case.input_data,
        workdir,
        settings.PISTON_RUN_TIMEOUT_MS,
    )
    if run_result.timed_out or run_result.return_code not in (0, None):
        return run_result.stdout, _local_error("run", run_result), False
    return run_result.stdout, "", True


async def _execute_java_locally(
    source_code: str,
    test_case: CodingTestCase,
    workdir: Path,
) -> tuple[str, str, bool]:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        return "", "local fallback: Java JDK is not installed", False

    source_path = workdir / "Main.java"
    source_path.write_text(source_code, encoding="utf-8")
    compile_result = await _run_local_process(
        [javac, str(source_path)],
        "",
        workdir,
        settings.PISTON_COMPILE_TIMEOUT_MS,
    )
    if compile_result.timed_out or compile_result.return_code != 0:
        return "", _local_error("compile", compile_result), False

    run_result = await _run_local_process(
        [java, "-cp", str(workdir), "Main"],
        test_case.input_data,
        workdir,
        settings.PISTON_RUN_TIMEOUT_MS,
    )
    if run_result.timed_out or run_result.return_code not in (0, None):
        return run_result.stdout, _local_error("run", run_result), False
    return run_result.stdout, "", True


async def _execute_single_case_locally(
    source_code: str,
    language: str,
    test_case: CodingTestCase,
    service_error: str = "",
) -> ExecutionCaseResult:
    if not settings.LOCAL_CODE_EXECUTION_FALLBACK:
        return _failure_result(test_case, service_error or "Execution service unavailable.")

    with tempfile.TemporaryDirectory(prefix="examguard-code-") as tmp:
        workdir = Path(tmp)
        if language == "python":
            actual_output, error_logs, runnable = await _execute_python_locally(
                source_code, test_case, workdir
            )
        elif language == "cpp":
            actual_output, error_logs, runnable = await _execute_cpp_locally(
                source_code, test_case, workdir
            )
        elif language == "java":
            actual_output, error_logs, runnable = await _execute_java_locally(
                source_code, test_case, workdir
            )
        else:
            return _failure_result(test_case, f"Unsupported language: {language}")

    passed = runnable and _normalize_output(actual_output) == _normalize_output(
        test_case.expected_output
    )
    if not runnable and service_error:
        error_logs = f"{service_error}\n{error_logs}".strip()
    return ExecutionCaseResult(
        case_number=test_case.sort_order,
        is_visible=test_case.is_visible,
        passed=passed,
        input_data=test_case.input_data,
        expected_output=test_case.expected_output,
        actual_output=actual_output,
        error_logs=error_logs,
    )


async def _execute_single_case(
    client: httpx.AsyncClient,
    source_code: str,
    language: str,
    test_case: CodingTestCase,
) -> ExecutionCaseResult:
    runtime = LANGUAGE_RUNTIMES[language]
    payload = {
        "language": runtime.piston_language,
        "version": runtime.piston_version,
        "files": [{"name": runtime.file_name, "content": source_code}],
        "stdin": test_case.input_data,
        "args": [],
        "compile_timeout": settings.PISTON_COMPILE_TIMEOUT_MS,
        "run_timeout": settings.PISTON_RUN_TIMEOUT_MS,
        "compile_cpu_time": settings.PISTON_COMPILE_TIMEOUT_MS,
        "run_cpu_time": settings.PISTON_RUN_TIMEOUT_MS,
        "compile_memory_limit": -1,
        "run_memory_limit": -1,
    }

    try:
        async with _execution_semaphore:
            response = await client.post(
                settings.PISTON_API_URL,
                json=payload,
                headers=_headers(),
            )
    except httpx.HTTPError as exc:
        return await _execute_single_case_locally(
            source_code,
            language,
            test_case,
            service_error=f"Execution service unavailable: {exc}",
        )

    if response.status_code >= 400:
        try:
            detail = response.json().get("message", response.text)
        except ValueError:
            detail = response.text
        return await _execute_single_case_locally(
            source_code,
            language,
            test_case,
            service_error=f"Execution service rejected code: {detail}",
        )

    try:
        data = response.json()
    except ValueError:
        return await _execute_single_case_locally(
            source_code,
            language,
            test_case,
            service_error="Execution service returned invalid JSON.",
        )

    run_stage = data.get("run")
    compile_stage = data.get("compile")
    actual_output = ""
    if isinstance(run_stage, dict):
        actual_output = str(run_stage.get("stdout") or "")

    failed = _stage_failed(run_stage if isinstance(run_stage, dict) else None)
    if isinstance(compile_stage, dict):
        failed = failed or _stage_failed(compile_stage)

    passed = (
        not failed
        and _normalize_output(actual_output) == _normalize_output(test_case.expected_output)
    )
    return ExecutionCaseResult(
        case_number=test_case.sort_order,
        is_visible=test_case.is_visible,
        passed=passed,
        input_data=test_case.input_data,
        expected_output=test_case.expected_output,
        actual_output=actual_output,
        error_logs=_error_logs(data),
    )


async def execute_code_against_cases(
    source_code: str,
    language: str,
    test_cases: Sequence[CodingTestCase],
) -> list[ExecutionCaseResult]:
    if language not in LANGUAGE_RUNTIMES:
        raise ValueError(f"Unsupported language: {language}")

    timeout_seconds = (
        settings.PISTON_COMPILE_TIMEOUT_MS + settings.PISTON_RUN_TIMEOUT_MS
    ) / 1000 + 15
    timeout = httpx.Timeout(timeout_seconds)

    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            _execute_single_case(client, source_code, language, test_case)
            for test_case in test_cases
        ]
        return list(await asyncio.gather(*tasks))
