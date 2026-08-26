"""Claude Code / OpenCode handoff packages (PRD §29).

The app previously had only a hardcoded markdown template built in the frontend,
so the §29 fields could not be tested and could not carry real context.
"""

import pytest

from app.handoff import (
    TASK_TYPES,
    build_handoff_package,
    infer_task_type,
    normalize_agent,
)


def test_package_carries_every_field_the_prd_names():
    p = build_handoff_package(task="Refactor the command broker", target="claude-code")
    for field in ("task_type", "recommended_agent", "repo_path", "context_files",
                  "vault_context", "prompt", "reason_for_escalation",
                  "expected_output", "approval_required"):
        assert field in p, f"§29 field missing: {field}"


def test_approval_is_always_required():
    """This app never launches an agent, so a human always runs the prompt."""
    p = build_handoff_package(task="anything", target="opencode")
    assert p["approval_required"] is True


@pytest.mark.parametrize("target,expected", [
    ("claude-code", "claude_code"),
    ("Claude Code", "claude_code"),
    ("claude_code", "claude_code"),
    ("opencode", "opencode"),
    ("manual", None),
    ("", None),
    (None, None),
])
def test_agent_normalization(target, expected):
    assert normalize_agent(target) == expected


@pytest.mark.parametrize("task,expected", [
    ("Refactor the brain CLI command broker", "repo_refactor"),
    ("Fix the crash when the vault path is missing", "bugfix"),
    ("Project closeout for robotics-arm-2024", "project_closeout"),
    ("Build the settings page layout", "ui_implementation"),
    ("Investigate options for sandboxing", "research_to_implementation"),
    ("Do the thing", "other"),
])
def test_task_type_inference(task, expected):
    assert infer_task_type(task) == expected


def test_inferred_type_is_always_in_the_declared_vocabulary():
    for task in ("", "aaa", "refactor and fix and archive", "UI bug in the archive page"):
        assert infer_task_type(task) in TASK_TYPES


def test_explicit_task_type_wins_over_inference():
    p = build_handoff_package(task="Fix the crash", target="claude-code", task_type="archive")
    assert p["task_type"] == "archive"


def test_a_nonsense_task_type_falls_back_to_inference():
    p = build_handoff_package(task="Fix the crash", target="claude-code", task_type="wat")
    assert p["task_type"] == "bugfix"


def test_context_appears_in_the_prompt():
    """§29's acceptance criterion: enough context to avoid repeated setup."""
    p = build_handoff_package(
        task="Refactor the gateway", target="claude-code",
        repo_path="D:/dev/JARVIS",
        context_files=["backend/app/permission_gateway.py"],
        vault_context=["wiki/projects/Brain UI.md"],
    )
    for fragment in ("D:/dev/JARVIS", "permission_gateway.py", "wiki/projects/Brain UI.md"):
        assert fragment in p["prompt"], fragment


def test_the_prompt_says_it_does_not_launch_anything():
    """§29: Brain UI does not attempt to replace coding agents."""
    p = build_handoff_package(task="anything", target="claude-code")
    assert "run it yourself" in p["prompt"].lower()
    assert "does **not** launch" in p["prompt"]


def test_an_empty_task_is_refused():
    with pytest.raises(ValueError, match="task description is required"):
        build_handoff_package(task="   ", target="claude-code")


def test_context_lists_are_bounded_and_flattened():
    """Untrusted-ish values must not be able to break the markdown block."""
    p = build_handoff_package(
        task="x", target="opencode",
        context_files=[f"file{i}.py" for i in range(50)] + ["a\nb.py", "  "],
    )
    assert len(p["context_files"]) <= 20
    assert all("\n" not in f for f in p["context_files"])
    assert all(f.strip() for f in p["context_files"])


def test_manual_target_still_produces_a_usable_prompt():
    p = build_handoff_package(task="Write this up by hand", target="manual")
    assert p["recommended_agent"] is None
    assert "Manual handoff" in p["prompt"]


def test_defaults_differ_by_task_type():
    """A generic expected-output for every task would be filler."""
    closeout = build_handoff_package(task="Project closeout for X", target="claude-code")
    bugfix = build_handoff_package(task="Fix the crash", target="claude-code")
    assert closeout["expected_output"] != bugfix["expected_output"]
    assert "resume" in closeout["expected_output"].lower()
