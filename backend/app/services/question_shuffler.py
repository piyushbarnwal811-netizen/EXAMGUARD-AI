"""
ExamGuard AI - Deterministic Question & Option Shuffling Engine
Module 2: PRD Specification

Guarantees:
1. Deterministic & reproducible shuffling per student based on studentId / rollNo / sessionId.
2. Shuffles both Question Order and Option Choices (A, B, C, D).
3. Conceals raw answer keys and correct options from the student client payload.
4. Accurately evaluates candidate submissions server-side by reconstructing the student's exact seed.
"""

from __future__ import annotations
import math
from typing import Any


def string_hash_code(s: str) -> int:
    """Computes standard 32-bit unsigned polynomial rolling hash (matches JS String.hashCode)."""
    h = 0
    for char in str(s):
        h = ((h << 5) - h + ord(char)) & 0xFFFFFFFF
    return h


def mulberry32(seed: int):
    """
    Mulberry32 32-bit Seeded PRNG.
    Bit-for-bit identical to JavaScript implementation.
    """
    t = seed & 0xFFFFFFFF

    def next_rand() -> float:
        nonlocal t
        t = (t + 0x6D2B79F5) & 0xFFFFFFFF
        z = t
        z = ((z ^ (z >> 15)) * (z | 1)) & 0xFFFFFFFF
        z = (z ^ (z + (((z ^ (z >> 7)) * (z | 61)) & 0xFFFFFFFF))) & 0xFFFFFFFF
        return ((z ^ (z >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return next_rand


def shuffle_with_seed(items: list[Any], seed_number: int) -> list[Any]:
    """Deterministic Fisher-Yates Shuffle using Mulberry32 PRNG."""
    shuffled = list(items)
    rand = mulberry32(seed_number)
    for i in range(len(shuffled) - 1, 0, -1):
        j = math.floor(rand() * (i + 1))
        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
    return shuffled


def generate_student_paper(raw_questions: list[Any], student_seed: int | str) -> list[dict[str, Any]]:
    """
    Generates a deterministically shuffled exam paper for a specific student.
    
    1. Shuffles Question Sequence with student_seed.
    2. Shuffles Option Choices for each question with derived option_seed.
    3. Strips correct_option / answer keys to prevent client-side answer sniffing.
    """
    seed_num = string_hash_code(str(student_seed)) if isinstance(student_seed, str) else int(student_seed) & 0xFFFFFFFF

    # 1. Shuffle Questions Sequence
    shuffled_questions = shuffle_with_seed(raw_questions, seed_num)

    safe_paper = []
    for idx, q in enumerate(shuffled_questions):
        q_id = getattr(q, "id", None) or q.get("id")
        q_text = getattr(q, "question_text", None) or getattr(q, "question", None) or q.get("question_text") or q.get("question")
        
        # Raw options
        opt_a = getattr(q, "option_a", None) or q.get("option_a", "")
        opt_b = getattr(q, "option_b", None) or q.get("option_b", "")
        opt_c = getattr(q, "option_c", None) or q.get("option_c", "")
        opt_d = getattr(q, "option_d", None) or q.get("option_d", "")

        raw_options = [
            {"id": "A", "text": opt_a},
            {"id": "B", "text": opt_b},
            {"id": "C", "text": opt_c},
            {"id": "D", "text": opt_d},
        ]

        # 2. Shuffle Options deterministically for this question
        option_seed = (seed_num + string_hash_code(str(q_id)) + idx) & 0xFFFFFFFF
        shuffled_options = shuffle_with_seed(raw_options, option_seed)

        # Build client-safe payload (NO correct_option exposed)
        safe_paper.append({
            "id": q_id,
            "displayIndex": idx + 1,
            "question": q_text,
            # Pass shuffled option texts and their internal mapping IDs
            "options": [opt["text"] for opt in shuffled_options],
            "optionItems": shuffled_options,  # [{"id": "C", "text": "..."}, ...]
            "shuffledOrder": [opt["id"] for opt in shuffled_options], # e.g. ["C", "A", "D", "B"]
        })

    return safe_paper


def resolve_submitted_option(
    question_id: int | str,
    selected_value: str,
    student_seed: int | str,
    question_index: int = 0,
) -> str:
    """
    Resolves student submission back to canonical option ('A', 'B', 'C', 'D').
    Handles:
    - Direct Option ID: "A", "B", "C", "D"
    - Display Letter Position: If client submitted by visual position (0 -> first displayed option)
    """
    clean_val = str(selected_value).strip().upper()
    if clean_val in {"A", "B", "C", "D"}:
        return clean_val

    # If display index 0, 1, 2, 3 or '0', '1', '2', '3'
    if clean_val.isdigit():
        pos = int(clean_val)
        seed_num = string_hash_code(str(student_seed)) if isinstance(student_seed, str) else int(student_seed) & 0xFFFFFFFF
        option_seed = (seed_num + string_hash_code(str(question_id)) + question_index) & 0xFFFFFFFF
        raw = ["A", "B", "C", "D"]
        shuffled = shuffle_with_seed(raw, option_seed)
        if 0 <= pos < len(shuffled):
            return shuffled[pos]

    return clean_val

