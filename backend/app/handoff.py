"""Claude Code / OpenCode handoff packages (PRD §29).

§29 specifies a structured package — task_type, recommended_agent, repo_path,
context_files, vault_context, prompt, reason_for_escalation, expected_output,
approval_required. The app previously had only a hardcoded markdown template
built in the frontend, so the fields could not be tested, could not carry real
vault context, and could not be reused anywhere else.

Deliberately NOT built: a repo-context *picker* UI. For a single user the useful
artifact is a copyable block, and §29's own acceptance criteria are about the
prompt containing enough context to avoid repeated setup — not about a file
browser. Context is derived from what the entity already declares.

This module generates text. It never launches an agent, and §29 is explicit that
Brain UI should not try to.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# §29's task_type vocabulary.
TASK_TYPES = (
    "repo_refactor", "bugfix", "project_closeout", "ui_implementation",
    "archive", "research_to_implementation", "other",
)

RECOMMENDED_AGENTS = ("claude_code", "opencode")

_AGENT_LABELS = {
    "claude_code": "Claude Code",
    "opencode": "OpenCode",
}

# Signals that suggest a task type. Ordered: the first match wins, so the more
# specific patterns come first.
_TASK_TYPE_SIGNALS: List[tuple[str, str]] = [
    (r"\bcloseout|close out|wrap up|archive the project\b", "project_closeout"),
    (r"\barchiv", "archive"),
    (r"\brefactor|restructur|migrat|clean ?up\b", "repo_refactor"),
    (r"\bbug|fix|broken|regression|crash|fails?\b", "bugfix"),
    (r"\bui|frontend|component|page|layout|css\b", "ui_implementation"),
    (r"\bresearch|investigat|spike|evaluate\b", "research_to_implementation"),
]


def _clean(value: Optional[str], limit: int = 2000) -> str:
    if not value:
        return ""
    return " ".join(str(value).split())[:limit]


def infer_task_type(task: str, notes: str = "") -> str:
    """Best-effort task_type. Falls back to "other" rather than guessing wrongly."""
    haystack = f"{task} {notes}".lower()
    for pattern, task_type in _TASK_TYPE_SIGNALS:
        if re.search(pattern, haystack):
            return task_type
    return "other"


def normalize_agent(target: Optional[str]) -> Optional[str]:
    """Map an escalation target to §29's recommended_agent, or None for manual."""
    value = (target or "").strip().lower().replace(" ", "-").replace("_", "-")
    if value == "claude-code":
        return "claude_code"
    if value == "opencode":
        return "opencode"
    return None


def build_handoff_package(
    *,
    task: str,
    target: Optional[str] = None,
    reason: Optional[str] = None,
    repo_path: Optional[str] = None,
    notes: Optional[str] = None,
    source: Optional[str] = None,
    priority: Optional[str] = None,
    context_files: Optional[List[str]] = None,
    vault_context: Optional[List[str]] = None,
    task_type: Optional[str] = None,
    expected_output: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the §29 package. Pure — generates text, runs nothing."""
    task = _clean(task, 500)
    if not task:
        raise ValueError("A task description is required.")

    notes = _clean(notes, 1000)
    resolved_type = (task_type or "").strip().lower()
    if resolved_type not in TASK_TYPES:
        resolved_type = infer_task_type(task, notes)

    agent = normalize_agent(target)
    package: Dict[str, Any] = {
        "task_type": resolved_type,
        "recommended_agent": agent,
        "repo_path": _clean(repo_path, 400) or None,
        "context_files": [_clean(f, 400) for f in (context_files or []) if _clean(f, 400)][:20],
        "vault_context": [_clean(v, 400) for v in (vault_context or []) if _clean(v, 400)][:20],
        "reason_for_escalation": _clean(reason, 500) or _default_reason(resolved_type),
        "expected_output": _clean(expected_output, 500) or _default_expected_output(resolved_type),
        # Always true. This app never launches an agent, so a human runs the
        # prompt — and §29 lists this field precisely so that stays explicit.
        "approval_required": True,
    }
    package["prompt"] = render_prompt(package, task=task, notes=notes,
                                      source=source, priority=priority)
    return package


def _default_reason(task_type: str) -> str:
    if task_type == "repo_refactor":
        return "Multi-file change; exceeds what the local model handles reliably."
    if task_type == "project_closeout":
        return "Repo-wide synthesis needed to produce an accurate closeout."
    if task_type == "bugfix":
        return "Requires reading and running the real code to reproduce."
    return "Escalated for heavy repo work; local agent proposes rather than edits."


def _default_expected_output(task_type: str) -> str:
    if task_type == "project_closeout":
        return "A closeout summary suitable for the wiki note, plus resume-evidence bullets."
    if task_type == "bugfix":
        return "A minimal fix, the reproduction it addresses, and the tests run."
    if task_type == "ui_implementation":
        return "Working UI matching the described behaviour, with the build passing."
    return "A summary of what changed, why, and anything still open."


def render_prompt(
    package: Dict[str, Any],
    *,
    task: str,
    notes: str = "",
    source: Optional[str] = None,
    priority: Optional[str] = None,
) -> str:
    """Render the package as a copyable markdown block."""
    agent_label = _AGENT_LABELS.get(package.get("recommended_agent") or "", "Manual")
    lines: List[str] = [
        f"# {agent_label} handoff — {package['task_type'].replace('_', ' ')}",
        "",
        "## Task",
        "",
        task,
        "",
        "## Context",
        "",
    ]
    if package.get("repo_path"):
        lines.append(f"- Repo: `{package['repo_path']}`")
    for path in package.get("context_files") or []:
        lines.append(f"- File: `{path}`")
    for path in package.get("vault_context") or []:
        lines.append(f"- Vault: `{path}`")
    if source:
        lines.append(f"- Source: {_clean(source, 200)}")
    if priority:
        lines.append(f"- Priority: {_clean(priority, 40)}")
    if notes:
        lines.append(f"- Notes: {notes}")
    if len(lines) and lines[-1] == "":
        lines.append("- (no additional context recorded)")

    lines += [
        "",
        "## Why this was escalated",
        "",
        package["reason_for_escalation"],
        "",
        "## Expected output",
        "",
        package["expected_output"],
        "",
        "## Ground rules",
        "",
        "1. Inspect before changing anything.",
        "2. Make changes only where this task asks for them.",
        "3. Do not delete files without confirming first.",
        "4. Report every command and test you run, including failures.",
        "5. Finish with a summary and anything still open.",
        "",
        "---",
        "",
        "Generated by Brain UI. It does **not** launch this for you — run it yourself in "
        f"{agent_label}.",
    ]
    return "\n".join(lines)
