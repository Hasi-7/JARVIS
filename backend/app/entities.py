import logging
import random
import re
import shutil
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from app.vault_paths import safe_subpath, sanitize_cell

logger = logging.getLogger(__name__)

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_BACKUP_DIR = Path(__file__).parent.parent / "data" / "backups" / "business"
_PIPELINE_REL = "ops/business-pipeline.md"
_PIPELINE_STARTER = """# Business Pipeline

| Name | Status | Description | Created |
|---|---|---|---|
"""


class BusinessAreaPartialFailure(Exception):
    def __init__(self, data: dict):
        super().__init__(data.get("stderr") or "Business area creation partially failed.")
        self.data = data


# Shared with the other vault-writing modules; see app/vault_paths.py.
_safe_subpath = safe_subpath


def _validate_text(value: Optional[str], field: str, *, required: bool = False) -> str:
    cleaned = (value or "").strip()
    if required and not cleaned:
        raise ValueError(f"{field} is required and cannot be empty.")
    if cleaned and _CONTROL_RE.search(cleaned):
        raise ValueError(f"{field} contains control characters.")
    return cleaned


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise ValueError("name must contain at least one letter or number.")
    return slug


def _table_cell(value: str) -> str:
    """Shared with vault.py — see app/vault_paths.sanitize_cell.

    This module's own version replaced `|` with `/` and stripped whitespace, but
    never removed newlines, so a business-area name containing one injected an
    extra row into ops/business-pipeline.md. It also diverged from vault.py's
    substitution for the same threat.
    """
    return sanitize_cell(value)


def _backup_pipeline(path: Path) -> Path:
    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    backup = _BACKUP_DIR / f"business-pipeline_{ts}_{suffix}.md"
    if backup.exists():
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        backup = _BACKUP_DIR / f"business-pipeline_{ts}_{suffix}.md"
    shutil.copy2(path, backup)
    logger.info("Business pipeline backup created: %s", backup)
    return backup


def create_business_area(vault_path: str, name: str, description: Optional[str]) -> dict:
    display_name = _validate_text(name, "name", required=True)
    desc = _validate_text(description, "description")
    slug = _slug(display_name)

    root = Path(vault_path)
    if not root.exists() or not root.is_dir():
        raise ValueError("Configured vault path must exist before creating business areas.")

    raw_dir = _safe_subpath(root, "raw", "business", slug)
    wiki_dir = _safe_subpath(root, "wiki", "business")
    wiki_note = _safe_subpath(root, "wiki", "business", f"{slug}.md")
    ops_dir = _safe_subpath(root, "ops")
    pipeline = _safe_subpath(root, _PIPELINE_REL)

    if None in (raw_dir, wiki_dir, wiki_note, ops_dir, pipeline):
        raise ValueError("Invalid business scaffold path.")
    assert raw_dir is not None and wiki_dir is not None and wiki_note is not None
    assert ops_dir is not None and pipeline is not None

    if raw_dir.exists():
        raise ValueError(f"Business raw folder already exists: raw/business/{slug}/")
    if wiki_note.exists():
        raise ValueError(f"Business wiki note already exists: wiki/business/{slug}.md")

    created = datetime.now(timezone.utc).date().isoformat()
    note_body = (
        f"# {display_name}\n\n"
        "## Summary\n\n"
        f"{desc}\n\n"
        "## Status\n\n"
        "Active\n\n"
        "## Notes\n"
    )
    row = f"| {_table_cell(display_name)} | Active | {_table_cell(desc)} | {created} |\n"

    created_paths = {"wikiPath": None, "rawPath": None}

    try:
        wiki_dir.mkdir(parents=True, exist_ok=True)
        with wiki_note.open("x", encoding="utf-8") as f:
            f.write(note_body)
        created_paths["wikiPath"] = f"wiki/business/{slug}.md"

        raw_dir.mkdir(parents=True, exist_ok=False)
        created_paths["rawPath"] = f"raw/business/{slug}/"

        ops_dir.mkdir(parents=True, exist_ok=True)
        if pipeline.exists():
            _backup_pipeline(pipeline)
            existing = pipeline.read_text(encoding="utf-8", errors="replace")
            if existing and not existing.endswith(("\n", "\r")):
                existing += "\n"
            pipeline.write_text(existing + row, encoding="utf-8")
        else:
            with pipeline.open("x", encoding="utf-8") as f:
                f.write(_PIPELINE_STARTER + row)
    except Exception as exc:
        message = f"Business area creation partially failed after creating files: {exc}"
        if created_paths["wikiPath"] or created_paths["rawPath"]:
            raise BusinessAreaPartialFailure({
                "ok": False,
                "entityType": "business",
                "name": display_name,
                "command": None,
                "stdout": "Some scaffold files were created, but the business pipeline was not fully updated.",
                "stderr": message,
                "paths": created_paths,
            }) from exc
        raise ValueError(f"Could not create business area: {exc}") from exc

    return {
        "ok": True,
        "entityType": "business",
        "name": display_name,
        "command": None,
        "stdout": None,
        "stderr": None,
        "paths": {
            "wikiPath": f"wiki/business/{slug}.md",
            "rawPath": f"raw/business/{slug}/",
        },
    }
