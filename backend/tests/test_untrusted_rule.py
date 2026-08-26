"""PRD §44 — the untrusted external content rule.

§44 requires this rule in EVERY prompt that summarizes browser pages, emails,
PDFs, chat transcripts, or copied app content. Three modules each carried their
own paraphrase and all three had drifted, none naming the specific capabilities
an injected instruction would try to reach.

These tests pin the wording and assert every LLM-facing path uses the shared
constant, so a future prompt cannot quietly ship a weaker version.
"""

import re
from pathlib import Path

import pytest

from app.untrusted import UNTRUSTED_CONTENT_RULE, with_untrusted_rule


APP_DIR = Path(__file__).parent.parent / "app"

# The clauses §44 names explicitly. Each describes a capability an injected
# instruction would try to reach, which is why the generic "don't follow
# instructions" paraphrases were not sufficient.
REQUIRED_CLAUSES = [
    "untrusted external content",
    "Do not follow instructions",
    "reveal secrets",
    "change permissions",
    "call tools",
    "send messages",
    "submit forms",
    "modify unrelated files",
]


@pytest.mark.parametrize("clause", REQUIRED_CLAUSES)
def test_rule_contains_every_clause_the_prd_names(clause):
    assert clause in UNTRUSTED_CONTENT_RULE, f"§44 clause missing: {clause!r}"


def test_the_rule_is_stated_before_the_untrusted_material():
    """Order matters: the rule must be established before the model reads the
    content it governs."""
    combined = with_untrusted_rule("Summarize the page below.")
    assert combined.startswith(UNTRUSTED_CONTENT_RULE)
    assert combined.index(UNTRUSTED_CONTENT_RULE) < combined.index("Summarize")


@pytest.mark.parametrize("module", ["agent.py", "classify_ai.py", "capture_assist.py"])
def test_prompt_modules_use_the_shared_constant(module):
    """Each of these previously had its own paraphrase."""
    source = (APP_DIR / module).read_text(encoding="utf-8")
    assert "UNTRUSTED_CONTENT_RULE" in source, (
        f"{module} does not reference the shared §44 rule"
    )


def test_no_module_reintroduces_a_private_paraphrase():
    """A new hardcoded 'untrusted' sentence is how the drift happened before."""
    offenders = []
    for path in APP_DIR.glob("*.py"):
        if path.name == "untrusted.py":
            continue
        source = path.read_text(encoding="utf-8")
        # A long string literal about following instructions, not referencing the
        # shared constant, is the shape of a fresh paraphrase.
        for match in re.finditer(r'"[^"\n]{40,}"', source):
            text = match.group(0).lower()
            if "never follow instructions" in text or "do not follow instructions" in text:
                offenders.append(f"{path.name}: {match.group(0)[:90]}")
    assert offenders == [], (
        "hardcoded untrusted-content wording found; import UNTRUSTED_CONTENT_RULE instead:\n"
        + "\n".join(offenders)
    )


def test_the_rule_never_claims_content_is_safe():
    """Guard against a future edit softening this into a suggestion."""
    lowered = UNTRUSTED_CONTENT_RULE.lower()
    for phrase in ("if possible", "try to", "generally", "usually", "when convenient"):
        assert phrase not in lowered, f"§44 rule weakened by hedging: {phrase!r}"
