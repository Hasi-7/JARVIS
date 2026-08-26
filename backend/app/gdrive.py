"""
Google Drive intake (D3) — READ-ONLY.

Brings Drive documents into the existing manual capture flows.

    list_files(query, limit)  -> file metadata
    get_file_text(file_id)    -> exported plain text
    build_research_payload()  -> fields for a Research draft (no vault write)

Safety model (this module never relaxes it):
- READ-ONLY. Only files.list and files.get/export are ever called. There is no
  create, update, delete, copy, share, or permissions path, and a source-guard
  test asserts those method names are absent.
- OPT-IN SCOPE. Requires `drive.readonly`, requested only when the operator sets
  BRAIN_UI_DRIVE_INTAKE_ENABLED and re-consents in the browser. Without it, calls
  refuse.
- EXPORT IS TEXT-ONLY. Google-native docs export as text/plain; binary types are
  refused rather than downloaded. Content is size-capped.
- Document content is UNTRUSTED external content: stored and displayed only, never
  executed, never followed as instructions, never auto-routed to a tool.
- NO VAULT WRITE. It returns draft *fields*; the user saves through the existing
  Research flow, keeping every never-overwrite / stay-in-vault guarantee.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from app.google_auth import (
    DRIVE_READONLY_SCOPE,
    GoogleAuthSetupError,
    authorize_google,
)

logger = logging.getLogger(__name__)

DRIVE_READ_TOOL = "drive.read"

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_TEXT_CHARS = 200_000
MAX_NAME_CHARS = 300
MAX_QUERY_CHARS = 500

# Google-native types that can be exported as plain text.
_EXPORTABLE = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.presentation": "text/plain",
}
# Types readable directly as text.
_PLAIN_TEXT = {"text/plain", "text/markdown", "text/csv"}


class DriveError(RuntimeError):
    """Raised when a Drive read cannot be performed safely."""


def drive_scope_granted(credentials: Any) -> bool:
    return DRIVE_READONLY_SCOPE in list(getattr(credentials, "scopes", None) or [])


def build_drive_service(
    *,
    credentials_factory: Optional[Callable[[], Any]] = None,
    service_builder: Optional[Callable[..., Any]] = None,
) -> Any:
    """Build a read-only Drive client."""
    factory = credentials_factory or authorize_google
    try:
        credentials = factory()
    except GoogleAuthSetupError as exc:
        raise DriveError(str(exc)) from exc

    if not drive_scope_granted(credentials):
        raise DriveError(
            "The granted Google credentials do not include read-only Drive access. "
            "Set BRAIN_UI_DRIVE_INTAKE_ENABLED=true and re-run: "
            "python -m app.google_auth authorize"
        )

    if service_builder is None:
        try:
            from googleapiclient.discovery import build as service_builder  # type: ignore
        except ImportError as exc:
            raise DriveError(
                "Google API client is missing. Run: pip install -r requirements.txt"
            ) from exc

    return service_builder("drive", "v3", credentials=credentials, cache_discovery=False)


def _truncate(value: Any, limit: int) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _clamp(limit: Optional[int]) -> int:
    try:
        value = int(limit) if limit is not None else DEFAULT_LIMIT
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(MAX_LIMIT, value))


def list_files(
    query: Optional[str] = None,
    limit: Optional[int] = None,
    *,
    service: Optional[Any] = None,
) -> List[dict]:
    """List Drive files. READ-ONLY, metadata only."""
    text = (query or "").strip()
    if len(text) > MAX_QUERY_CHARS:
        raise DriveError(f"Drive query is too long (max {MAX_QUERY_CHARS} characters).")

    client = service or build_drive_service()
    # Never list trashed files; the caller's text is passed only as a name filter.
    q = "trashed = false"
    if text:
        escaped = text.replace("\\", "\\\\").replace("'", "\\'")
        q += f" and name contains '{escaped}'"

    try:
        response = (
            client.files()
            .list(
                q=q,
                pageSize=_clamp(limit),
                fields="files(id,name,mimeType,modifiedTime,owners,webViewLink,size)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
    except DriveError:
        raise
    except Exception as exc:
        raise DriveError(f"Drive listing failed: {str(exc)[:200]}") from exc

    files: List[dict] = []
    for item in ((response or {}).get("files") or [])[:_clamp(limit)]:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        mime = str(item.get("mimeType") or "")
        files.append({
            "fileId": str(item.get("id")),
            "name": _truncate(item.get("name"), MAX_NAME_CHARS),
            "mimeType": mime,
            "modifiedTime": _truncate(item.get("modifiedTime"), 40) or None,
            "webViewLink": _truncate(item.get("webViewLink"), 400) or None,
            "readable": mime in _EXPORTABLE or mime in _PLAIN_TEXT,
        })
    return files


def get_file_text(file_id: str, *, service: Optional[Any] = None) -> dict:
    """Fetch one Drive file as plain text. Binary types are refused, not downloaded."""
    fid = (file_id or "").strip()
    if not fid:
        raise DriveError("A Drive file id is required.")

    client = service or build_drive_service()

    try:
        meta = client.files().get(fileId=fid, fields="id,name,mimeType,webViewLink").execute()
    except DriveError:
        raise
    except Exception as exc:
        raise DriveError(f"Drive metadata fetch failed: {str(exc)[:200]}") from exc

    if not isinstance(meta, dict) or not meta.get("id"):
        raise DriveError(f"Drive file '{fid}' was not found.")

    mime = str(meta.get("mimeType") or "")
    try:
        if mime in _EXPORTABLE:
            raw = client.files().export(fileId=fid, mimeType=_EXPORTABLE[mime]).execute()
        elif mime in _PLAIN_TEXT:
            raw = client.files().get_media(fileId=fid).execute()
        else:
            raise DriveError(
                f"'{mime or 'unknown'}' is not a text type; refusing to download it."
            )
    except DriveError:
        raise
    except Exception as exc:
        raise DriveError(f"Drive export failed: {str(exc)[:200]}") from exc

    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw or "")
    return {
        "fileId": str(meta.get("id")),
        "name": _truncate(meta.get("name"), MAX_NAME_CHARS),
        "mimeType": mime,
        "webViewLink": _truncate(meta.get("webViewLink"), 400) or None,
        "text": _truncate(text, MAX_TEXT_CHARS),
        "truncated": len(text) > MAX_TEXT_CHARS,
    }


def build_research_payload(document: dict) -> dict:
    """Shape a fetched Drive document into Research draft fields.

    Creates no draft and writes no vault file.
    """
    if not isinstance(document, dict):
        raise DriveError("A fetched Drive document is required.")
    name = str(document.get("name") or "Untitled Drive document")
    return {
        "title": _truncate(name, MAX_NAME_CHARS),
        "topic": _truncate(name, MAX_NAME_CHARS),
        "sources": [{
            "title": name,
            "url": document.get("webViewLink") or "",
            "notes": "Imported from Google Drive (read-only).",
        }],
        "rawNotes": str(document.get("text") or ""),
        "warnings": [
            "Drive document content is untrusted. Review it before saving to the vault.",
        ],
    }
