"""
Deterministic heuristic file classifier — no I/O, no AI, no external calls.

Returns a ClassificationResult based on filename and content_type only.
This is a scaffold; OpenClaw classification replaces it in a later run.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ClassificationResult:
    domain: str               # project|hackathon|course|business|research|personal|chat/session|backfill|unknown
    source_type: str          # syllabus|lecture|assignment|past-exam|notes|screenshots|...
    confidence: str           # High|Medium|Low
    reason: str
    proposed_destination: str # always starts with raw/


def classify_file(original_name: str, content_type: Optional[str]) -> ClassificationResult:
    """
    Pure function. Given filename + MIME type, return a best-guess classification.
    Rules are checked in priority order; first match wins.
    """
    name = original_name.lower()

    # ── images → screenshots / unknown ───────────────────────────────────────
    if content_type and content_type.startswith("image/"):
        return ClassificationResult(
            domain="unknown", source_type="screenshots",
            confidence="Low", reason="Image file — domain undetermined",
            proposed_destination="raw/inbox/unclassified/",
        )

    # ── course: syllabus ─────────────────────────────────────────────────────
    if "syllabus" in name:
        return ClassificationResult(
            domain="course", source_type="syllabus",
            confidence="Medium", reason='Filename contains "syllabus"',
            proposed_destination="raw/courses/Unassigned/syllabus/",
        )

    # ── course: lecture / slides ─────────────────────────────────────────────
    if any(kw in name for kw in ("lecture", "lec-", "lec_", "slides")):
        return ClassificationResult(
            domain="course", source_type="lecture",
            confidence="Medium", reason="Filename contains lecture/slides keyword",
            proposed_destination="raw/courses/Unassigned/lectures/",
        )

    # ── course: assignment / problem set ─────────────────────────────────────
    if any(kw in name for kw in ("assignment", "homework", "problem-set", "problem_set", "pset")):
        return ClassificationResult(
            domain="course", source_type="assignment",
            confidence="Medium", reason="Filename contains assignment/homework keyword",
            proposed_destination="raw/courses/Unassigned/assignments/",
        )

    # ── course: exam ─────────────────────────────────────────────────────────
    if any(kw in name for kw in ("past-exam", "past_exam", "midterm", "final-exam", "exam")):
        return ClassificationResult(
            domain="course", source_type="past-exam",
            confidence="Medium", reason="Filename contains exam keyword",
            proposed_destination="raw/courses/Unassigned/exams/",
        )

    # ── personal: resume / CV ────────────────────────────────────────────────
    if any(kw in name for kw in ("resume", "curriculum-vitae", "cv-", "cv_")):
        return ClassificationResult(
            domain="personal", source_type="other",
            confidence="Medium", reason="Filename contains resume/CV keyword",
            proposed_destination="raw/personal/Unassigned/other/",
        )

    # ── business: pitch ──────────────────────────────────────────────────────
    if any(kw in name for kw in ("pitch", "pitch-deck", "investor", "startup")):
        return ClassificationResult(
            domain="business", source_type="pitch",
            confidence="Medium", reason="Filename contains pitch/investor keyword",
            proposed_destination="raw/business/Unassigned/pitch/",
        )

    # ── business: finance ────────────────────────────────────────────────────
    if any(kw in name for kw in ("invoice", "receipt", "finance", "budget", "financial")):
        return ClassificationResult(
            domain="business", source_type="finance",
            confidence="Medium", reason="Filename contains finance keyword",
            proposed_destination="raw/business/Unassigned/finance/",
        )

    # ── hackathon ────────────────────────────────────────────────────────────
    if any(kw in name for kw in ("hackathon", "devpost", "hack-the-north", "htn", "mlh")):
        return ClassificationResult(
            domain="hackathon", source_type="submission",
            confidence="Medium", reason="Filename contains hackathon keyword",
            proposed_destination="raw/hackathons/Unassigned/submission/",
        )

    # ── research ─────────────────────────────────────────────────────────────
    if any(kw in name for kw in ("research", "paper", "survey", "literature-review")):
        return ClassificationResult(
            domain="research", source_type="other",
            confidence="Low", reason="Filename contains research/paper keyword",
            proposed_destination="raw/research/Unassigned/other/",
        )

    # ── chat / AI session ────────────────────────────────────────────────────
    if any(kw in name for kw in ("chat", "session", "claude", "chatgpt", "conversation")):
        return ClassificationResult(
            domain="chat/session", source_type="session-summaries",
            confidence="Low", reason="Filename contains chat/session keyword",
            proposed_destination="raw/chats/Unassigned/",
        )

    # ── project (generic) ────────────────────────────────────────────────────
    if any(kw in name for kw in ("project", "proposal", "spec", "requirements", "readme")):
        return ClassificationResult(
            domain="project", source_type="repo-docs",
            confidence="Low", reason="Filename contains project/spec keyword",
            proposed_destination="raw/projects/Unassigned/docs/",
        )

    # ── default ──────────────────────────────────────────────────────────────
    return ClassificationResult(
        domain="unknown", source_type="other",
        confidence="Low", reason="No matching heuristic rule",
        proposed_destination="raw/inbox/unclassified/",
    )
