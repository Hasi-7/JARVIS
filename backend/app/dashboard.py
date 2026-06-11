"""
dashboard.py — Read-only aggregate for GET /api/dashboard/summary.

Aggregates counts from staged files, proposals, tasks, calendar candidates,
entities (projects/courses/hackathons/business), backfill, resume pipeline,
escalations, and runtime status (brain CLI path, vault existence, Ollama agent).

Also builds:
- todayPlan — up to 5 active tasks selected deterministically by priority:
  blocked → in-progress → due today/overdue → high priority → open.
- activeWork — up to 3 items per active workflow (backfill, escalations,
  resume, calendar, raw), sorted by status urgency and priority.

Safety: completely read-only.
- No file writes.
- No brain commands.
- No Ollama chat calls.
- No AI classification.
- No vault mutations.
- No config mutations.
"""

import logging
from datetime import date, datetime
from pathlib import Path

from app.agent import get_agent_status
from app.calendar import get_calendar_candidates
from app.config import get_config
from app.escalations import get_escalations
from app.intake import list_proposals, list_staged
from app.vault import (
    get_backfill,
    get_business,
    get_courses,
    get_hackathons,
    get_projects,
    get_resume_pipeline,
    get_tasks,
)

logger = logging.getLogger(__name__)


# ── today plan helpers ───────────────────────────────────────────────────────

_EXCLUDED_STATUSES = frozenset({"done", "completed", "archived", "closed"})
_MAX_PLAN_ITEMS = 5


def _parse_due(due_str: str | None) -> date | None:
    """Try common date formats; return None on any failure."""
    if not due_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(due_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _due_reason(due_str: str | None, today: date) -> str | None:
    """Return 'Due today', 'Overdue', or None."""
    d = _parse_due(due_str)
    if d is None:
        return None
    if d < today:
        return "Overdue"
    if d == today:
        return "Due today"
    return None


def _build_today_plan(task_list: list) -> list:
    """
    Select up to _MAX_PLAN_ITEMS active tasks using deterministic priority buckets.

    Buckets (in order of importance):
      1. blocked
      2. in progress
      3. due today or overdue (any status except excluded)
      4. high priority (any status except excluded)
      5. remaining todo/open tasks

    Each item gets a short `reason` string. Tasks already placed are not repeated.
    Done/completed/archived tasks are always excluded.
    """
    today = date.today()
    seen: set = set()
    result: list = []

    def _add(task: dict, reason: str) -> bool:
        tid = task.get("id", "")
        if tid in seen:
            return False
        seen.add(tid)
        result.append({
            "id":       tid,
            "title":    task.get("title") or "",
            "status":   (task.get("status") or "").lower(),
            "priority": task.get("priority"),
            "due":      task.get("due"),
            "area":     task.get("area"),
            "source":   task.get("source"),
            "reason":   reason,
        })
        return True

    def _active(task: dict) -> bool:
        return (task.get("status") or "").lower() not in _EXCLUDED_STATUSES

    # bucket 1 — blocked
    for t in task_list:
        if len(result) >= _MAX_PLAN_ITEMS:
            break
        if _active(t) and (t.get("status") or "").lower() == "blocked":
            _add(t, "Blocked")

    # bucket 2 — in progress
    for t in task_list:
        if len(result) >= _MAX_PLAN_ITEMS:
            break
        if _active(t) and (t.get("status") or "").lower() == "in progress":
            _add(t, "In progress")

    # bucket 3 — due today or overdue
    for t in task_list:
        if len(result) >= _MAX_PLAN_ITEMS:
            break
        if _active(t):
            dr = _due_reason(t.get("due"), today)
            if dr:
                _add(t, dr)

    # bucket 4 — high priority (not already selected)
    for t in task_list:
        if len(result) >= _MAX_PLAN_ITEMS:
            break
        if _active(t) and (t.get("priority") or "").lower() == "high":
            _add(t, "High priority")

    # bucket 5 — remaining open/todo
    for t in task_list:
        if len(result) >= _MAX_PLAN_ITEMS:
            break
        if _active(t):
            _add(t, "Open task")

    return result


# ── active work helpers ───────────────────────────────────────────────────────

_MAX_ACTIVE_ITEMS = 3
_VALUE_RANK    = {"high": 0, "medium": 1, "low": 2}
_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

_BACKFILL_STATUS_RANK    = {"in-progress": 0, "triaged": 1, "new": 2}
_ESCALATION_STATUS_RANK  = {"blocked": 0, "ready": 1, "in-progress": 2, "new": 3}
_RESUME_STATUS_RANK      = {"interview": 0, "applied": 1, "tailoring": 2, "new": 3}

_BACKFILL_ACTIVE   = frozenset({"new", "triaged", "in-progress"})
_ESCALATION_ACTIVE = frozenset({"new", "ready", "in-progress", "blocked"})
_RESUME_ACTIVE     = frozenset({"new", "tailoring", "applied", "interview"})
_RAW_ACTIVE        = frozenset({"proposed", "edited"})


def _build_active_work(
    staged_entries: list,
    proposals: list,
    calendar_candidates: list,
    backfill_items: list,
    resume_items: list,
    escalation_items: list,
) -> tuple[dict, list]:
    """
    Build per-workflow active item lists for the dashboard drill-down.

    Returns (active_work_dict, errors_list). Each source is wrapped in its own
    try/except so one failure does not poison the others.

    Safety: read-only. No vault writes, no commands, no Ollama calls.
    """
    result: dict = {
        "backfill":    [],
        "escalations": [],
        "resume":      [],
        "calendar":    [],
        "raw":         [],
    }
    errors: list = []

    # ── backfill ──────────────────────────────────────────────────────────────
    try:
        active = [
            (idx, it)
            for idx, it in enumerate(backfill_items)
            if (it.get("status") or "").lower() in _BACKFILL_ACTIVE
        ]
        active.sort(key=lambda t: (
            _BACKFILL_STATUS_RANK.get((t[1].get("status") or "").lower(), 9),
            _VALUE_RANK.get((t[1].get("value") or "").lower(), 9),
            t[0],
        ))
        _STATUS_LABEL = {"in-progress": "In progress", "triaged": "Triaged", "new": "New"}
        for _, it in active[:_MAX_ACTIVE_ITEMS]:
            status = (it.get("status") or "").lower()
            result["backfill"].append({
                "id":       it.get("id", ""),
                "title":    it.get("item") or "",
                "status":   status,
                "priority": it.get("value"),
                "type":     it.get("type"),
                "path":     it.get("path"),
                "reason":   _STATUS_LABEL.get(status, status),
            })
    except Exception as exc:
        logger.warning("Active work backfill failed: %s", exc)
        errors.append({"source": "activeWork.backfill", "message": "Could not build active backfill list."})

    # ── escalations ───────────────────────────────────────────────────────────
    try:
        active = [
            (idx, it)
            for idx, it in enumerate(escalation_items)
            if (it.get("status") or "").lower() in _ESCALATION_ACTIVE
        ]
        active.sort(key=lambda t: (
            _ESCALATION_STATUS_RANK.get((t[1].get("status") or "").lower(), 9),
            _PRIORITY_RANK.get((t[1].get("priority") or "").lower(), 9),
            t[0],
        ))
        _STATUS_LABEL = {"blocked": "Blocked", "ready": "Ready", "in-progress": "In progress", "new": "New"}
        for _, it in active[:_MAX_ACTIVE_ITEMS]:
            status = (it.get("status") or "").lower()
            result["escalations"].append({
                "id":       it.get("id", ""),
                "title":    it.get("task") or "",
                "status":   status,
                "priority": it.get("priority"),
                "target":   it.get("target"),
                "path":     it.get("path"),
                "reason":   _STATUS_LABEL.get(status, status),
            })
    except Exception as exc:
        logger.warning("Active work escalations failed: %s", exc)
        errors.append({"source": "activeWork.escalations", "message": "Could not build active escalations list."})

    # ── resume ────────────────────────────────────────────────────────────────
    try:
        today = date.today()

        def _deadline_days(it: dict) -> int:
            d = _parse_due(it.get("deadline"))
            return (d - today).days if d else 9999

        active = [
            (idx, it)
            for idx, it in enumerate(resume_items)
            if (it.get("status") or "").lower() in _RESUME_ACTIVE
        ]
        active.sort(key=lambda t: (
            _RESUME_STATUS_RANK.get((t[1].get("status") or "").lower(), 9),
            _PRIORITY_RANK.get((t[1].get("priority") or "").lower(), 9),
            _deadline_days(t[1]),
            t[0],
        ))
        _STATUS_LABEL = {"interview": "Interview", "applied": "Applied", "tailoring": "Tailoring", "new": "New"}
        for _, it in active[:_MAX_ACTIVE_ITEMS]:
            status = (it.get("status") or "").lower()
            result["resume"].append({
                "id":       it.get("id", ""),
                "title":    it.get("target") or "",
                "status":   status,
                "priority": it.get("priority"),
                "company":  it.get("company"),
                "role":     it.get("role"),
                "reason":   _STATUS_LABEL.get(status, status),
            })
    except Exception as exc:
        logger.warning("Active work resume failed: %s", exc)
        errors.append({"source": "activeWork.resume", "message": "Could not build active resume list."})

    # ── calendar ──────────────────────────────────────────────────────────────
    try:
        today = date.today()
        pending = [
            (idx, c)
            for idx, c in enumerate(calendar_candidates)
            if (c.get("approved") or "").strip().lower() != "yes"
        ]

        def _cal_sort_key(t: tuple) -> tuple:
            idx, c = t
            d = _parse_due(c.get("date"))
            return (0, (d - today).days, idx) if d else (1, 0, idx)

        pending.sort(key=_cal_sort_key)
        for _, c in pending[:_MAX_ACTIVE_ITEMS]:
            result["calendar"].append({
                "id":     c.get("id", ""),
                "title":  c.get("title") or "",
                "status": "pending",
                "date":   c.get("date"),
                "time":   c.get("time"),
                "reason": "Pending approval",
            })
    except Exception as exc:
        logger.warning("Active work calendar failed: %s", exc)
        errors.append({"source": "activeWork.calendar", "message": "Could not build pending calendar list."})

    # ── raw ───────────────────────────────────────────────────────────────────
    try:
        staged_by_id = {e.id: e.original_name for e in staged_entries}
        active = [
            (idx, p)
            for idx, p in enumerate(proposals)
            if (p.status or "").lower() in _RAW_ACTIVE
        ]
        # edited first, then original order within each group
        active.sort(key=lambda t: (0 if (t[1].status or "").lower() == "edited" else 1, t[0]))
        for _, p in active[:_MAX_ACTIVE_ITEMS]:
            title = (
                staged_by_id.get(p.file_id)
                or (p.entity if p.entity and p.entity != "Unassigned" else None)
                or p.proposed_destination
                or p.file_id
            )
            result["raw"].append({
                "id":     p.file_id,
                "title":  title or "",
                "status": (p.status or "").lower(),
                "reason": "Edited — needs review" if (p.status or "").lower() == "edited" else "Needs review",
            })
    except Exception as exc:
        logger.warning("Active work raw failed: %s", exc)
        errors.append({"source": "activeWork.raw", "message": "Could not build active raw inbox list."})

    return result, errors


# ── zero-value helpers ────────────────────────────────────────────────────────

def _zero_raw() -> dict:
    return {"staged": 0, "proposed": 0, "edited": 0, "approved": 0, "routed": 0, "archived": 0}


def _zero_tasks() -> dict:
    return {"total": 0, "todo": 0, "inProgress": 0, "blocked": 0, "done": 0}


def _zero_calendar() -> dict:
    return {"total": 0, "approved": 0, "pending": 0}


def _zero_entities() -> dict:
    return {"projects": 0, "courses": 0, "hackathons": 0, "business": 0}


def _zero_backfill() -> dict:
    return {"total": 0, "new": 0, "triaged": 0, "inProgress": 0, "done": 0, "skipped": 0}


def _zero_resume() -> dict:
    return {"total": 0, "new": 0, "tailoring": 0, "applied": 0, "interview": 0,
            "offer": 0, "rejected": 0, "archived": 0}


def _zero_escalations() -> dict:
    return {"total": 0, "active": 0, "new": 0, "ready": 0, "inProgress": 0,
            "blocked": 0, "done": 0, "skipped": 0}


# ── aggregation ───────────────────────────────────────────────────────────────

def get_dashboard_summary() -> dict:
    """
    Return a snapshot of all dashboard metrics including activeWork drill-down lists.

    Each subsystem is wrapped individually — a failure in one section
    appends to `errors` and leaves that section at zero counts / empty list.
    The endpoint never raises; it always returns a complete shape.

    Safety: completely read-only. No writes, no brain commands, no Ollama calls.
    """
    cfg = get_config()
    vault_path = cfg.vault_path
    errors: list = []

    # Data captured once and reused for both counts and activeWork
    _staged_entries: list = []
    _proposals:      list = []
    _cal_candidates: list = []
    _backfill_items: list = []
    _resume_items:   list = []
    _escalation_items: list = []

    # ── raw inbox ─────────────────────────────────────────────────────────────
    raw = _zero_raw()
    try:
        _staged_entries = list_staged()
        raw["staged"] = len(_staged_entries)
        _proposals = list_proposals()
        for p in _proposals:
            s = p.status.lower()
            if s == "proposed":
                raw["proposed"] += 1
            elif s == "edited":
                raw["edited"] += 1
            elif s == "approved":
                raw["approved"] += 1
            elif s == "routed":
                raw["routed"] += 1
            elif s == "archived":
                raw["archived"] += 1
    except Exception as exc:
        logger.warning("Dashboard raw aggregation failed: %s", exc)
        errors.append({"source": "raw", "message": "Raw inbox could not be read."})
        raw = _zero_raw()

    # ── tasks + today plan ────────────────────────────────────────────────────
    tasks_counts = _zero_tasks()
    today_plan_items: list = []
    today_plan_source = "tasks"
    try:
        task_list = get_tasks(vault_path).get("tasks", [])
        tasks_counts["total"] = len(task_list)
        for t in task_list:
            s = (t.get("status") or "").lower()
            if s == "todo":
                tasks_counts["todo"] += 1
            elif s == "in progress":
                tasks_counts["inProgress"] += 1
            elif s == "blocked":
                tasks_counts["blocked"] += 1
            elif s == "done":
                tasks_counts["done"] += 1
        today_plan_items = _build_today_plan(task_list)
    except Exception as exc:
        logger.warning("Dashboard tasks aggregation failed: %s", exc)
        errors.append({"source": "tasks", "message": "Task file could not be parsed."})
        tasks_counts = _zero_tasks()

    # ── calendar candidates ───────────────────────────────────────────────────
    calendar = _zero_calendar()
    try:
        _cal_candidates = get_calendar_candidates(vault_path).get("candidates", [])
        calendar["total"] = len(_cal_candidates)
        for c in _cal_candidates:
            if (c.get("approved") or "").strip().lower() == "yes":
                calendar["approved"] += 1
            else:
                calendar["pending"] += 1
    except Exception as exc:
        logger.warning("Dashboard calendar aggregation failed: %s", exc)
        errors.append({"source": "calendar", "message": "Calendar candidates could not be read."})
        calendar = _zero_calendar()

    # ── entities (each counted independently) ─────────────────────────────────
    entities = _zero_entities()
    for key, fn in (
        ("projects",   get_projects),
        ("courses",    get_courses),
        ("hackathons", get_hackathons),
        ("business",   get_business),
    ):
        try:
            entities[key] = len(fn(vault_path))
        except Exception as exc:
            logger.warning("Dashboard %s aggregation failed: %s", key, exc)
            errors.append({"source": f"entities.{key}", "message": f"{key.capitalize()} could not be counted."})

    # ── backfill ──────────────────────────────────────────────────────────────
    backfill = _zero_backfill()
    try:
        _backfill_items = get_backfill(vault_path).get("items", [])
        backfill["total"] = len(_backfill_items)
        for item in _backfill_items:
            s = (item.get("status") or "").lower()
            if s == "new":
                backfill["new"] += 1
            elif s == "triaged":
                backfill["triaged"] += 1
            elif s == "in-progress":
                backfill["inProgress"] += 1
            elif s == "done":
                backfill["done"] += 1
            elif s == "skipped":
                backfill["skipped"] += 1
    except Exception as exc:
        logger.warning("Dashboard backfill aggregation failed: %s", exc)
        errors.append({"source": "backfill", "message": "Backfill file could not be parsed."})
        backfill = _zero_backfill()

    # ── resume pipeline ───────────────────────────────────────────────────────
    resume = _zero_resume()
    try:
        _resume_items = get_resume_pipeline(vault_path).get("items", [])
        resume["total"] = len(_resume_items)
        for item in _resume_items:
            s = (item.get("status") or "").lower()
            if s == "new":
                resume["new"] += 1
            elif s == "tailoring":
                resume["tailoring"] += 1
            elif s == "applied":
                resume["applied"] += 1
            elif s == "interview":
                resume["interview"] += 1
            elif s == "offer":
                resume["offer"] += 1
            elif s == "rejected":
                resume["rejected"] += 1
            elif s == "archived":
                resume["archived"] += 1
    except Exception as exc:
        logger.warning("Dashboard resume aggregation failed: %s", exc)
        errors.append({"source": "resume", "message": "Resume pipeline could not be parsed."})
        resume = _zero_resume()

    # ── escalations ───────────────────────────────────────────────────────────
    escalations = _zero_escalations()
    try:
        _escalation_items = get_escalations(vault_path).get("items", [])
        escalations["total"] = len(_escalation_items)
        for item in _escalation_items:
            s = (item.get("status") or "").lower()
            if s == "new":
                escalations["new"] += 1
            elif s == "ready":
                escalations["ready"] += 1
            elif s == "in-progress":
                escalations["inProgress"] += 1
            elif s == "blocked":
                escalations["blocked"] += 1
            elif s == "done":
                escalations["done"] += 1
            elif s == "skipped":
                escalations["skipped"] += 1
        escalations["active"] = (
            escalations["new"] + escalations["ready"] +
            escalations["inProgress"] + escalations["blocked"]
        )
    except Exception as exc:
        logger.warning("Dashboard escalations aggregation failed: %s", exc)
        errors.append({"source": "escalations", "message": "Escalation queue could not be read."})
        escalations = _zero_escalations()

    # ── runtime ───────────────────────────────────────────────────────────────
    brain_status = "unknown"
    try:
        brain_status = "available" if Path(cfg.brain_cmd).exists() else "unavailable"
    except Exception:
        pass

    vault_exists = False
    try:
        vault_exists = Path(vault_path).is_dir()
    except Exception:
        pass

    agent_avail = "unknown"
    try:
        result = get_agent_status()
        agent_avail = "available" if result.get("available") else "unavailable"
    except Exception:
        pass

    # ── active work ───────────────────────────────────────────────────────────
    active_work, aw_errors = _build_active_work(
        staged_entries=_staged_entries,
        proposals=_proposals,
        calendar_candidates=_cal_candidates,
        backfill_items=_backfill_items,
        resume_items=_resume_items,
        escalation_items=_escalation_items,
    )
    errors.extend(aw_errors)

    return {
        "raw":         raw,
        "tasks":       tasks_counts,
        "calendar":    calendar,
        "entities":    entities,
        "backfill":    backfill,
        "resume":      resume,
        "escalations": escalations,
        "runtime":  {
            "backend":     "connected",
            "brain":       brain_status,
            "agent":       agent_avail,
            "vaultExists": vault_exists,
        },
        "todayPlan": {
            "items":       today_plan_items,
            "source":      today_plan_source,
            "generatedAt": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        },
        "activeWork": active_work,
        "errors": errors,
    }
