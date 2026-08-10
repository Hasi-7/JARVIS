import json
import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.vault import (
    get_vault_summary,
    get_projects,
    get_courses,
    get_hackathons,
    get_business,
    get_ops_file,
    get_tasks,
    update_task_status,
    create_task,
    get_backfill,
    update_backfill_status,
    update_backfill_item,
    create_backfill_file,
    create_backfill_item,
    get_resume_pipeline,
    update_resume_pipeline_status,
    create_resume_pipeline_file,
    create_resume_pipeline_item,
    update_resume_pipeline_item,
)
from app.calendar import (
    create_calendar_candidate,
    create_calendar_candidates_file,
    get_calendar_candidates,
    update_calendar_candidate,
    approve_calendar_candidate,
)
from app.agent import (
    chat_with_agent,
    get_agent_status,
    stream_ollama_chat,
    LOCAL_MODEL,
    CONTEXT_WINDOW_MESSAGES,
)
from app.brain import run_brain_command, run_brain_command_args
from app.agent_tool_requests import (
    create_request as create_agent_tool_request,
    list_requests as list_agent_tool_requests,
)
from app.agent_structured_output import evaluate_structured_output, parse_structured_output
from app.agent_modes import (
    normalize_mode,
    can_evaluate_tool_requests,
    list_modes as list_agent_modes,
    blocked_message as mode_blocked_message,
)
from app.dashboard import get_dashboard_summary
from app.proposals import list_normalized_proposals
from app.tools import list_tool_connections
from app.runtime_status import list_runtime_status
from app.runtime_probe import probe_nemoclaw, read_last_probe
from app.runtime_policy import inspect_nemoclaw_policy
from app.guardrail_readiness import get_guardrail_readiness
from app.runtime_bridge_contract import validate_bridge_request
from app.permission_gateway import (
    list_policies,
    evaluate_tool_request,
    log_evaluation,
    log_execution,
    list_logs,
    is_executable,
    brain_command_for,
)
from app.consolidation import (
    create_draft as create_consolidation_draft,
    list_drafts as list_consolidation_drafts,
    get_draft as get_consolidation_draft,
    update_draft as update_consolidation_draft,
    save_draft as save_consolidation_draft,
)
from app.research import (
    create_draft as create_research_draft,
    list_drafts as list_research_drafts,
    get_draft as get_research_draft,
    update_draft as update_research_draft,
    save_draft as save_research_draft,
)
from app.email_intake import (
    create_draft as create_email_draft,
    list_drafts as list_email_drafts,
    get_draft as get_email_draft,
    update_draft as update_email_draft,
    save_draft as save_email_draft,
)
from app.escalations import (
    add_escalation_item,
    create_escalation_queue_file,
    get_escalations,
    update_escalation_item,
    update_escalation_status,
)
from app.config import get_config, update_config
from app.conversations import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    save_chat_turn,
)
from app.entities import BusinessAreaPartialFailure, create_business_area
from app.intake import (
    ai_classify_proposal,
    batch_ai_classify_proposals,
    approve_proposal,
    archive_staged_file,
    batch_approve_proposals,
    delete_staged,
    list_archived,
    list_proposals,
    list_staged,
    route_proposal,
    skip_proposal,
    stage_file,
    update_proposal,
    validate_destination,
)
from app.models import (
    AgentChatRequest,
    AgentChatResponse,
    AgentStatusResponse,
    ArchiveInfo,
    BackfillItem,
    BackfillResponse,
    UpdateBackfillStatusRequest,
    UpdateBackfillStatusResponse,
    UpdateBackfillItemRequest,
    UpdateBackfillItemResponse,
    CreateBackfillItemRequest,
    CreateBackfillItemResponse,
    ResumePipelineItem,
    ResumePipelineResponse,
    UpdateResumePipelineStatusRequest,
    UpdateResumePipelineStatusResponse,
    CreateResumePipelineItemRequest,
    CreateResumePipelineItemResponse,
    UpdateResumePipelineItemRequest,
    UpdateResumePipelineItemResponse,
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    CreateConversationRequest,
    DeleteConversationResponse,
    ArchiveResponse,
    ArchivedFilesResponse,
    BatchAiClassifyRequest,
    BatchAiClassifyResponse,
    BatchApproveRequest,
    VaultSummaryResponse,
    VaultProjectsResponse,
    VaultProjectItem,
    VaultCoursesResponse,
    VaultCourseItem,
    VaultHackathonsResponse,
    VaultHackathonItem,
    VaultBusinessResponse,
    VaultBusinessItem,
    VaultOpsFileResponse,
    VaultTask,
    VaultTasksResponse,
    TaskStatusUpdateRequest,
    TaskStatusUpdateResponse,
    CreateVaultTaskRequest,
    CalendarCandidate,
    CalendarCandidatesResponse,
    CreateCalendarCandidateRequest,
    UpdateCalendarCandidateRequest,
    UpdateCalendarCandidateResponse,
    BatchApproveResponse,
    BatchSkippedItem,
    BrainRunRequest,
    BrainRunResponse,
    ClassificationProposalResponse,
    ConfigResponse,
    ConfigUpdateRequest,
    CreateBusinessRequest,
    DeleteStagedResponse,
    CreateCourseRequest,
    CreateHackathonRequest,
    CreateProjectRequest,
    EntityCreateResponse,
    EntityPaths,
    CreateEscalationItemRequest,
    DashboardSummaryResponse,
    ProposalItem,
    ProposalListError,
    ProposalListResponse,
    ToolConnectionStatus,
    ToolConnectionStatusResponse,
    RuntimeStatusItem,
    RuntimeStatusResponse,
    NemoclawProbeRequest,
    NemoclawProbeResponse,
    NemoclawLastProbeResponse,
    NemoclawPolicyResponse,
    GuardrailReadinessResponse,
    RuntimeBridgeValidationRequest,
    RuntimeBridgeValidationResponse,
    PermissionPolicy,
    PermissionPolicyResponse,
    ToolRequestEvaluationRequest,
    ToolRequestEvaluationResponse,
    PermissionEvaluationLog,
    PermissionEvaluationLogsResponse,
    ToolExecutionResponse,
    CreateAgentToolRequestRequest,
    AgentToolRequestResponse,
    AgentToolRequestListResponse,
    AgentChatStructured,
    AgentModePolicy,
    AgentModesResponse,
    AgentModeBlockedResponse,
    ConsolidationDraftResponse,
    ConsolidationDraftsResponse,
    CreateConsolidationDraftRequest,
    UpdateConsolidationDraftRequest,
    SaveConsolidationDraftResponse,
    ResearchSource,
    ResearchDraftResponse,
    ResearchDraftsResponse,
    CreateResearchDraftRequest,
    UpdateResearchDraftRequest,
    SaveResearchDraftResponse,
    EmailIntakeDraftResponse,
    EmailIntakeDraftsResponse,
    CreateEmailIntakeDraftRequest,
    UpdateEmailIntakeDraftRequest,
    SaveEmailIntakeDraftResponse,
    EscalationItem,
    EscalationResponse,
    UpdateEscalationItemRequest,
    UpdateEscalationItemResponse,
    UpdateEscalationStatusRequest,
    UpdateEscalationStatusResponse,
    HealthResponse,
    ProposalUpdateRequest,
    ProposalsResponse,
    RouteInfo,
    RouteResponse,
    StagedFileInfo,
    StagedFilesResponse,
    UploadResponse,
)
from app.security import ALLOWED_COMMANDS, is_allowed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Brain UI Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


# ── shared helpers ────────────────────────────────────────────────────────────

def _config_response(cfg=None) -> ConfigResponse:
    if cfg is None:
        cfg = get_config()
    return ConfigResponse(
        vaultPath=cfg.vault_path,
        brainCmd=cfg.brain_cmd,
        backendReady=True,
        brainCmdExists=Path(cfg.brain_cmd).exists(),
        vaultPathExists=Path(cfg.vault_path).exists(),
        configSource=cfg.source,
        configPersisted=cfg.persisted,
        configWarning=cfg.warning,
    )


def _entry_to_info(e) -> StagedFileInfo:
    return StagedFileInfo(
        id=e.id, originalName=e.original_name, storedName=e.stored_name,
        sizeBytes=e.size_bytes, contentType=e.content_type,
        uploadedAt=e.uploaded_at, status=e.status,
    )


def _proposal_to_response(p) -> ClassificationProposalResponse:
    return ClassificationProposalResponse(
        fileId=p.file_id, domain=p.domain, entity=p.entity,
        sourceType=p.source_type, proposedDestination=p.proposed_destination,
        confidence=p.confidence, needsReview=p.needs_review,
        reason=p.reason, status=p.status,
        routedAt=p.routed_at, routedPath=p.routed_path, routedName=p.routed_name,
        archivedAt=p.archived_at, archivePath=p.archived_path, archiveName=p.archived_name,
        classifiedBy=p.classified_by, aiModel=p.ai_model, aiClassifiedAt=p.ai_classified_at,
    )


def _entity_command_response(entity_type: str, name: str, result: BrainRunResponse) -> EntityCreateResponse:
    return EntityCreateResponse(
        ok=result.ok,
        entityType=entity_type,
        name=name,
        command=result.command,
        stdout=result.stdout,
        stderr=result.stderr,
        paths=EntityPaths(wikiPath=None, rawPath=None),
    )


def _entity_scaffold_response(data: dict) -> EntityCreateResponse:
    return EntityCreateResponse(
        ok=data["ok"],
        entityType=data["entityType"],
        name=data["name"],
        command=data.get("command"),
        stdout=data.get("stdout"),
        stderr=data.get("stderr"),
        paths=EntityPaths(**data["paths"]),
    )


# ── health / config ───────────────────────────────────────────────────────────

@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(ok=True, service="brain-ui-backend", version="0.1.0")


@app.get("/api/config", response_model=ConfigResponse)
def config_get() -> ConfigResponse:
    return _config_response()


@app.put("/api/config", response_model=ConfigResponse)
def config_put(req: ConfigUpdateRequest) -> ConfigResponse:
    vault = req.vaultPath.strip()
    brain = req.brainCmd.strip()
    if not vault:
        raise HTTPException(status_code=422, detail="vaultPath cannot be empty.")
    if not brain:
        raise HTTPException(status_code=422, detail="brainCmd cannot be empty.")
    logger.info("Config updated: vault=%r  brain_cmd=%r", vault, brain)
    cfg = update_config(vault_path=vault, brain_cmd=brain)
    return _config_response(cfg)


# ── dashboard summary ─────────────────────────────────────────────────────────

@app.get("/api/dashboard/summary", response_model=DashboardSummaryResponse)
def dashboard_summary() -> DashboardSummaryResponse:
    data = get_dashboard_summary()
    return DashboardSummaryResponse(**data)


# ── proposal queue (read-only aggregation; v1 = Raw Inbox proposals) ───────────

@app.get("/api/proposals", response_model=ProposalListResponse)
def proposals_list() -> ProposalListResponse:
    """
    Read-only, normalized aggregation of proposal-like items. v1 includes only
    Raw Inbox classification proposals. Listing never mutates anything.
    """
    items, errors = list_normalized_proposals()
    return ProposalListResponse(
        proposals=[ProposalItem(**it) for it in items],
        errors=[ProposalListError(**e) for e in errors],
    )


# ── tool / MCP connections (read-only readiness inventory; v0) ─────────────────

@app.get("/api/tools/status", response_model=ToolConnectionStatusResponse)
def tools_status() -> ToolConnectionStatusResponse:
    """
    Read-only inventory of planned tool systems and their readiness.

    Honest status/config surface only — performs no external calls, runs no shell
    commands, never invokes `brain`, reads no credentials, and launches no
    OpenClaw/NemoClaw/OpenShell runtime or tool. Nothing is executed.
    """
    items = list_tool_connections()
    return ToolConnectionStatusResponse(
        items=[ToolConnectionStatus(**it) for it in items],
    )


# ── OpenClaw / NemoClaw runtime status (read-only readiness; v0) ────────────────

@app.get("/api/runtime/status", response_model=RuntimeStatusResponse)
def runtime_status() -> RuntimeStatusResponse:
    """
    Read-only readiness for the privileged agent runtimes (OpenClaw, NemoClaw/
    OpenShell, browser harness, computer-use, MCP gateway).

    Honest config/readiness surface only — reads environment config, performs no
    network/health call, launches no runtime, runs no shell/`brain`, reads no
    credentials, writes no vault files, and executes no tool. No runtime is reported
    `available` (no verified check exists), so browser/computer-use stay blocked.
    """
    return RuntimeStatusResponse(
        items=[RuntimeStatusItem(**it) for it in list_runtime_status()],
    )


@app.post("/api/runtime/probe/nemoclaw", response_model=NemoclawProbeResponse)
def runtime_probe_nemoclaw(req: Optional[NemoclawProbeRequest] = None) -> NemoclawProbeResponse:
    """
    Explicit, opt-in reachability check for a configured LOCAL NemoClaw/OpenShell
    runtime URL. Runs only when the user triggers it.

    Bounded HTTP GET to NEMOCLAW_RUNTIME_URL only (loopback hosts by default; remote
    blocked unless NEMOCLAW_ALLOW_REMOTE_PROBE=true). No URL configured / not enabled →
    `not_configured` with NO network call. Never sends credentials/cookies/auth headers,
    follows no redirects, starts no process, runs no shell/`brain`, writes no vault, and
    UNLOCKS NOTHING — browser/computer-use stay disabled even if the runtime is reachable.
    """
    timeout_ms = req.timeoutMs if req else None
    return NemoclawProbeResponse(**probe_nemoclaw(timeout_ms=timeout_ms))


@app.get("/api/runtime/probe/nemoclaw/last", response_model=NemoclawLastProbeResponse)
def runtime_probe_nemoclaw_last() -> NemoclawLastProbeResponse:
    """
    Read-only: return the cached last NemoClaw/OpenShell probe result (or null).
    This performs NO network call — loading it is not a probe.
    """
    last = read_last_probe()
    return NemoclawLastProbeResponse(
        lastProbe=NemoclawProbeResponse(**last) if last else None,
    )


@app.get("/api/runtime/policy/nemoclaw", response_model=NemoclawPolicyResponse)
def runtime_policy_nemoclaw() -> NemoclawPolicyResponse:
    """
    Read-only inspection of the configured NemoClaw/OpenShell policy file.

    Reads ONLY the operator-configured NEMOCLAW_POLICY_PATH (never a frontend-supplied
    path), parses it defensively (JSON always, YAML only if PyYAML is present), and
    returns a safe summarized view of declared scopes. Enforcement is NOT wired: this
    does not enforce the policy, start the runtime, make a network call, execute/import
    the policy file, run shell/`brain`, write the vault, or unlock any capability.
    """
    return NemoclawPolicyResponse(**inspect_nemoclaw_policy())


@app.get("/api/runtime/guardrail-readiness", response_model=GuardrailReadinessResponse)
def runtime_guardrail_readiness() -> GuardrailReadinessResponse:
    """
    Read-only Guardrail Readiness v0. Correlates runtime status + the cached last
    NemoClaw/OpenShell probe + policy inspection + agent mode policy into one honest
    readiness view for FUTURE bridge design.

    Pure/read-only: runs NO fresh health probe (reads the cached last probe only),
    makes no network call, launches no runtime, runs no shell/`brain`, reads no
    credentials, writes no vault, executes no tool, and UNLOCKS NOTHING — every
    capability stays disabled and `ready_for_bridge_design` never means execution-ready.
    """
    return GuardrailReadinessResponse(**get_guardrail_readiness())


@app.post("/api/runtime/bridge/validate", response_model=RuntimeBridgeValidationResponse)
def runtime_bridge_validate(req: RuntimeBridgeValidationRequest) -> RuntimeBridgeValidationResponse:
    """
    Dry-run validator for a FUTURE NemoClaw/OpenShell bridge request. Validates the
    request shape, checks agent mode policy, reads guardrail readiness (cached — no
    fresh probe), maps the action kind to a conservative risk, and runs a Permission
    Gateway DRY-RUN classification — then logs a sanitized audit entry.

    Executes NOTHING: never calls NemoClaw/OpenShell/OpenClaw, never runs browser/
    computer-use/MCP/Gmail/Calendar/vault/brain actions, never runs shell/`brain`,
    starts no runtime/process, reads no credentials, writes no vault, and UNLOCKS
    NOTHING. `allowed`/`executionEnabled` are always False — a valid request is not an
    approval to run it.
    """
    result = validate_bridge_request(
        source=req.source,
        mode=req.mode,
        action_kind=req.requestedAction.kind,
        target=req.requestedAction.target,
        args=req.requestedAction.args,
        reason=req.reason,
        conversation_id=req.conversationId,
    )
    return RuntimeBridgeValidationResponse(**result)


# ── permission gateway (deny-by-default classification; v0 — no execution) ──────

@app.get("/api/permissions/policies", response_model=PermissionPolicyResponse)
def permissions_policies() -> PermissionPolicyResponse:
    """
    Read-only list of tool policies. executionEnabled is False for every entry —
    the gateway classifies requests but executes nothing in v0.
    """
    return PermissionPolicyResponse(
        policies=[PermissionPolicy(**p) for p in list_policies()],
    )


@app.post("/api/permissions/evaluate", response_model=ToolRequestEvaluationResponse)
def permissions_evaluate(req: ToolRequestEvaluationRequest) -> ToolRequestEvaluationResponse:
    """
    Classify a simulated tool request. Deny-by-default. NOTHING is executed: no
    tool runs, no external call is made, no shell/brain runs, no vault write
    occurs. Args are untrusted — summarized for display only, with secrets
    redacted and long values truncated.
    """
    try:
        result = evaluate_tool_request(
            tool=req.tool,
            args=req.args,
            reason=req.reason,
            requested_by=req.requestedBy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Record one redacted backend-local audit entry (no vault write, no execution).
    entry = log_evaluation(result, requested_by=req.requestedBy, reason=req.reason)
    return ToolRequestEvaluationResponse(**result, logId=entry["id"])


@app.get("/api/permissions/logs", response_model=PermissionEvaluationLogsResponse)
def permissions_logs(
    limit: int = 50,
    tool: str | None = None,
    decision: str | None = None,
) -> PermissionEvaluationLogsResponse:
    """
    Read-only list of Permission Gateway evaluation log entries, newest first.
    Backend-local app-data only (never the vault). limit clamped to [1, 200].
    """
    entries = list_logs(limit=limit, tool=tool, decision=decision)
    return PermissionEvaluationLogsResponse(
        logs=[PermissionEvaluationLog(**e) for e in entries],
    )


@app.post("/api/permissions/execute", response_model=ToolExecutionResponse)
def permissions_execute(req: ToolRequestEvaluationRequest) -> ToolExecutionResponse:
    """
    Safe-local Tool Execution v0. Evaluates + logs every request, then executes ONLY
    the allowlisted low-risk brain status tools (brain.status / brain.raw_status /
    brain.vault_path) via the existing safe brain wrapper. All other tools return a
    safe non-execution response (no 500). Never runs shell, arbitrary brain commands,
    or any privileged/external tool; never writes the vault.
    """
    try:
        result = evaluate_tool_request(
            tool=req.tool, args=req.args, reason=req.reason, requested_by=req.requestedBy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Always evaluate + log first.
    eval_entry = log_evaluation(result, requested_by=req.requestedBy, reason=req.reason)

    tool = result["tool"]
    if not is_executable(tool):
        # Safe non-execution response for denied/not-wired/disabled/non-executable tools.
        return ToolExecutionResponse(
            tool=tool,
            allowed=False,
            decision=result["decision"],
            riskLevel=result["riskLevel"],
            requiresApproval=result["requiresApproval"],
            executionEnabled=result["executionEnabled"],
            evaluationLogId=eval_entry["id"],
            executionLogId=None,
            ok=False,
            error="Tool is not executable in this build.",
        )

    # Executable safe-local tool → run via the existing safe brain wrapper only.
    brain_cmd = brain_command_for(tool)            # status | raw-status | vault-path
    brain_result = run_brain_command(brain_cmd)    # allowlisted, shell=False, no args
    exec_entry = log_execution(result, brain_result, requested_by=req.requestedBy, reason=req.reason)

    return ToolExecutionResponse(
        tool=tool,
        allowed=True,
        decision="executed",
        riskLevel=result["riskLevel"],
        requiresApproval=result["requiresApproval"],
        executionEnabled=True,
        evaluationLogId=eval_entry["id"],
        executionLogId=exec_entry["id"],
        ok=brain_result.ok,
        exitCode=brain_result.exitCode,
        stdout=brain_result.stdout,
        stderr=brain_result.stderr,
        durationMs=brain_result.durationMs,
    )


# ── chat / AI consolidation (v1: manual paste/import) ──────────────────────────

def _consolidation_to_response(d) -> ConsolidationDraftResponse:
    return ConsolidationDraftResponse(
        id                     = d.id,
        sourceTool             = d.source_tool,
        conversationTitle      = d.conversation_title,
        domain                 = d.domain,
        entity                 = d.entity,
        transcript             = d.transcript,
        summary                = d.summary,
        decisions              = d.decisions,
        actionItems            = d.action_items,
        codeOrFilesReferenced  = d.code_or_files_referenced,
        status                 = d.status,
        proposedDestination    = d.proposed_destination,
        savedPath              = d.saved_path,
        createdAt              = d.created_at,
        updatedAt              = d.updated_at,
    )


@app.post("/api/consolidation/drafts", response_model=ConsolidationDraftResponse)
def consolidation_create(req: CreateConsolidationDraftRequest) -> ConsolidationDraftResponse:
    """
    Create a consolidation draft from a manually pasted transcript. Stores backend
    metadata only — no vault write, no AI call, no brain, no external tool.
    """
    try:
        draft = create_consolidation_draft(
            source_tool              = req.sourceTool,
            conversation_title       = req.conversationTitle,
            domain                   = req.domain,
            entity                   = req.entity,
            transcript               = req.transcript,
            summary                  = req.summary,
            decisions                = req.decisions,
            action_items             = req.actionItems,
            code_or_files_referenced = req.codeOrFilesReferenced,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _consolidation_to_response(draft)


@app.get("/api/consolidation/drafts", response_model=ConsolidationDraftsResponse)
def consolidation_list() -> ConsolidationDraftsResponse:
    return ConsolidationDraftsResponse(
        drafts=[_consolidation_to_response(d) for d in list_consolidation_drafts()]
    )


@app.get("/api/consolidation/drafts/{draft_id}", response_model=ConsolidationDraftResponse)
def consolidation_get(draft_id: str) -> ConsolidationDraftResponse:
    draft = get_consolidation_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Consolidation draft '{draft_id}' not found.")
    return _consolidation_to_response(draft)


@app.patch("/api/consolidation/drafts/{draft_id}", response_model=ConsolidationDraftResponse)
def consolidation_update(draft_id: str, req: UpdateConsolidationDraftRequest) -> ConsolidationDraftResponse:
    # Map provided (non-None) camelCase fields to the module's snake_case editable keys.
    field_map = {
        "conversationTitle":     "conversation_title",
        "domain":                "domain",
        "entity":                "entity",
        "summary":               "summary",
        "decisions":             "decisions",
        "actionItems":           "action_items",
        "codeOrFilesReferenced": "code_or_files_referenced",
    }
    payload = req.model_dump(exclude_unset=True)
    updates = {field_map[k]: v for k, v in payload.items() if k in field_map}
    try:
        draft = update_consolidation_draft(draft_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Consolidation draft '{draft_id}' not found.")
    return _consolidation_to_response(draft)


@app.post("/api/consolidation/drafts/{draft_id}/save", response_model=SaveConsolidationDraftResponse)
def consolidation_save(draft_id: str) -> SaveConsolidationDraftResponse:
    """
    Write one Markdown summary under raw/chats/<sourceTool>/. Never overwrites,
    never escapes the vault, never runs brain/AI, never touches tasks/calendar/resume.
    """
    cfg = get_config()
    try:
        draft, info = save_consolidation_draft(draft_id, cfg.vault_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SaveConsolidationDraftResponse(
        ok=True,
        draft=_consolidation_to_response(draft),
        relativePath=info["relativePath"],
        absolutePath=info["absolutePath"],
    )


# ── research (v1: manual capture) ──────────────────────────────────────────────

def _research_to_response(d) -> ResearchDraftResponse:
    return ResearchDraftResponse(
        id                     = d.id,
        title                  = d.title,
        topic                  = d.topic,
        domain                 = d.domain,
        entity                 = d.entity,
        researchQuestion       = d.research_question,
        summary                = d.summary,
        keyFindings            = d.key_findings,
        sources                = [ResearchSource(**s) for s in d.sources],
        openQuestions          = d.open_questions,
        recommendedNextActions = d.recommended_next_actions,
        rawNotes               = d.raw_notes,
        status                 = d.status,
        proposedDestination    = d.proposed_destination,
        savedPath              = d.saved_path,
        createdAt              = d.created_at,
        updatedAt              = d.updated_at,
    )


@app.post("/api/research/drafts", response_model=ResearchDraftResponse)
def research_create(req: CreateResearchDraftRequest) -> ResearchDraftResponse:
    """
    Create a research draft from manually captured notes/links/findings. Stores backend
    metadata only — no vault write, no AI call, no URL fetch, no brain, no external tool.
    """
    try:
        draft = create_research_draft(
            title                    = req.title,
            topic                    = req.topic,
            domain                   = req.domain,
            entity                   = req.entity,
            research_question        = req.researchQuestion,
            summary                  = req.summary,
            key_findings             = req.keyFindings,
            sources                  = [s.model_dump() for s in req.sources],
            open_questions           = req.openQuestions,
            recommended_next_actions = req.recommendedNextActions,
            raw_notes                = req.rawNotes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _research_to_response(draft)


@app.get("/api/research/drafts", response_model=ResearchDraftsResponse)
def research_list() -> ResearchDraftsResponse:
    return ResearchDraftsResponse(
        drafts=[_research_to_response(d) for d in list_research_drafts()]
    )


@app.get("/api/research/drafts/{draft_id}", response_model=ResearchDraftResponse)
def research_get(draft_id: str) -> ResearchDraftResponse:
    draft = get_research_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Research draft '{draft_id}' not found.")
    return _research_to_response(draft)


@app.patch("/api/research/drafts/{draft_id}", response_model=ResearchDraftResponse)
def research_update(draft_id: str, req: UpdateResearchDraftRequest) -> ResearchDraftResponse:
    field_map = {
        "title":                  "title",
        "topic":                  "topic",
        "domain":                 "domain",
        "entity":                 "entity",
        "researchQuestion":       "research_question",
        "summary":                "summary",
        "keyFindings":            "key_findings",
        "sources":                "sources",
        "openQuestions":          "open_questions",
        "recommendedNextActions": "recommended_next_actions",
        "rawNotes":               "raw_notes",
    }
    payload = req.model_dump(exclude_unset=True)
    updates = {field_map[k]: v for k, v in payload.items() if k in field_map}
    try:
        draft = update_research_draft(draft_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Research draft '{draft_id}' not found.")
    return _research_to_response(draft)


@app.post("/api/research/drafts/{draft_id}/save", response_model=SaveResearchDraftResponse)
def research_save(draft_id: str) -> SaveResearchDraftResponse:
    """
    Write one Markdown research note under raw/research/. Never overwrites, never escapes
    the vault, never fetches URLs, never runs brain/AI, never touches tasks/calendar/resume.
    """
    cfg = get_config()
    try:
        draft, info = save_research_draft(draft_id, cfg.vault_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SaveResearchDraftResponse(
        ok=True,
        draft=_research_to_response(draft),
        relativePath=info["relativePath"],
        absolutePath=info["absolutePath"],
    )


# ── email intake (v1: manual paste/import) ─────────────────────────────────────

def _email_to_response(d) -> EmailIntakeDraftResponse:
    return EmailIntakeDraftResponse(
        id                   = d.id,
        subject              = d.subject,
        sender               = d.sender,
        receivedAt           = d.received_at,
        domain               = d.domain,
        entity               = d.entity,
        summary              = d.summary,
        actionRequired       = d.action_required,
        dueDate              = d.due_date,
        confidence           = d.confidence,
        rawEmail             = d.raw_email,
        proposedTaskRows     = d.proposed_task_rows,
        proposedCalendarRows = d.proposed_calendar_rows,
        status               = d.status,
        proposedDestination  = d.proposed_destination,
        savedPath            = d.saved_path,
        createdAt            = d.created_at,
        updatedAt            = d.updated_at,
    )


@app.post("/api/email-intake/drafts", response_model=EmailIntakeDraftResponse)
def email_intake_create(req: CreateEmailIntakeDraftRequest) -> EmailIntakeDraftResponse:
    """
    Create an email intake draft from manually pasted email content. Stores backend
    metadata only — no vault write, no AI call, no Gmail/MCP, no external tool.
    """
    try:
        draft = create_email_draft(
            subject                = req.subject,
            sender                 = req.sender,
            received_at            = req.receivedAt,
            domain                 = req.domain,
            entity                 = req.entity,
            summary                = req.summary,
            action_required        = req.actionRequired,
            due_date               = req.dueDate,
            confidence             = req.confidence,
            raw_email              = req.rawEmail,
            proposed_task_rows     = req.proposedTaskRows,
            proposed_calendar_rows = req.proposedCalendarRows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _email_to_response(draft)


@app.get("/api/email-intake/drafts", response_model=EmailIntakeDraftsResponse)
def email_intake_list() -> EmailIntakeDraftsResponse:
    return EmailIntakeDraftsResponse(
        drafts=[_email_to_response(d) for d in list_email_drafts()]
    )


@app.get("/api/email-intake/drafts/{draft_id}", response_model=EmailIntakeDraftResponse)
def email_intake_get(draft_id: str) -> EmailIntakeDraftResponse:
    draft = get_email_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Email intake draft '{draft_id}' not found.")
    return _email_to_response(draft)


@app.patch("/api/email-intake/drafts/{draft_id}", response_model=EmailIntakeDraftResponse)
def email_intake_update(draft_id: str, req: UpdateEmailIntakeDraftRequest) -> EmailIntakeDraftResponse:
    field_map = {
        "subject":              "subject",
        "sender":               "sender",
        "receivedAt":           "received_at",
        "domain":               "domain",
        "entity":               "entity",
        "summary":              "summary",
        "actionRequired":       "action_required",
        "dueDate":              "due_date",
        "confidence":           "confidence",
        "proposedTaskRows":     "proposed_task_rows",
        "proposedCalendarRows": "proposed_calendar_rows",
    }
    payload = req.model_dump(exclude_unset=True)
    updates = {field_map[k]: v for k, v in payload.items() if k in field_map}
    try:
        draft = update_email_draft(draft_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if draft is None:
        raise HTTPException(status_code=404, detail=f"Email intake draft '{draft_id}' not found.")
    return _email_to_response(draft)


@app.post("/api/email-intake/drafts/{draft_id}/save", response_model=SaveEmailIntakeDraftResponse)
def email_intake_save(draft_id: str) -> SaveEmailIntakeDraftResponse:
    """
    Write one Markdown summary under an allowlisted raw email path. Never overwrites,
    never escapes the vault, never connects to Gmail, never runs brain/AI, never
    creates tasks/calendar rows.
    """
    cfg = get_config()
    try:
        draft, info = save_email_draft(draft_id, cfg.vault_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SaveEmailIntakeDraftResponse(
        ok=True,
        draft=_email_to_response(draft),
        relativePath=info["relativePath"],
        absolutePath=info["absolutePath"],
    )


# ── brain commands ────────────────────────────────────────────────────────────

@app.get("/api/brain/commands")
def brain_commands() -> list:
    return sorted(ALLOWED_COMMANDS)


@app.get("/api/brain/vault-path", response_model=BrainRunResponse)
def brain_vault_path() -> BrainRunResponse:
    return run_brain_command("vault-path")


@app.get("/api/brain/status", response_model=BrainRunResponse)
def brain_status() -> BrainRunResponse:
    return run_brain_command("status")


@app.post("/api/brain/run", response_model=BrainRunResponse)
def brain_run(req: BrainRunRequest) -> BrainRunResponse:
    if not is_allowed(req.command):
        raise HTTPException(
            status_code=400,
            detail=f"Command '{req.command}' is not in the allowlist.",
        )
    if req.command in {"new-project", "new-course", "new-hackathon"}:
        raise HTTPException(
            status_code=400,
            detail=f"Command '{req.command}' requires the entity-specific creation endpoint.",
        )
    return run_brain_command(req.command)


# ── entity creation ───────────────────────────────────────────────────────────

@app.post("/api/entities/projects", response_model=EntityCreateResponse)
def entity_project_create(req: CreateProjectRequest) -> EntityCreateResponse:
    result = run_brain_command_args("new-project", {"name": req.name})
    return _entity_command_response("project", req.name.strip(), result)


@app.post("/api/entities/courses", response_model=EntityCreateResponse)
def entity_course_create(req: CreateCourseRequest) -> EntityCreateResponse:
    result = run_brain_command_args("new-course", {
        "code": req.code,
        "name": req.name,
    })
    return _entity_command_response("course", req.code.strip(), result)


@app.post("/api/entities/hackathons", response_model=EntityCreateResponse)
def entity_hackathon_create(req: CreateHackathonRequest) -> EntityCreateResponse:
    result = run_brain_command_args("new-hackathon", {"name": req.name})
    return _entity_command_response("hackathon", req.name.strip(), result)


@app.post("/api/entities/business", response_model=EntityCreateResponse)
def entity_business_create(req: CreateBusinessRequest) -> EntityCreateResponse:
    cfg = get_config()
    try:
        data = create_business_area(cfg.vault_path, req.name, req.description)
    except BusinessAreaPartialFailure as exc:
        return _entity_scaffold_response(exc.data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _entity_scaffold_response(data)


# ── intake / staging ──────────────────────────────────────────────────────────

@app.post("/api/intake/upload", response_model=UploadResponse)
async def intake_upload(files: list[UploadFile] = File(...)) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")
    uploaded = []
    for f in files:
        content = await f.read()
        entry = stage_file(
            original_name=f.filename or "unknown",
            content=content,
            content_type=f.content_type,
        )
        uploaded.append(_entry_to_info(entry))
    return UploadResponse(uploaded=uploaded)


@app.get("/api/intake/staged", response_model=StagedFilesResponse)
def intake_staged() -> StagedFilesResponse:
    return StagedFilesResponse(files=[_entry_to_info(e) for e in list_staged()])


@app.delete("/api/intake/staged/{file_id}", response_model=DeleteStagedResponse)
def intake_delete(file_id: str) -> DeleteStagedResponse:
    try:
        deleted = delete_staged(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if deleted is None:
        raise HTTPException(status_code=404, detail=f"Staged file '{file_id}' not found.")
    return DeleteStagedResponse(ok=True, deletedId=file_id)


# ── intake / proposals ────────────────────────────────────────────────────────

@app.get("/api/intake/proposals", response_model=ProposalsResponse)
def intake_proposals() -> ProposalsResponse:
    return ProposalsResponse(proposals=[_proposal_to_response(p) for p in list_proposals()])


@app.put("/api/intake/proposals/{file_id}", response_model=ClassificationProposalResponse)
def intake_update_proposal(file_id: str, req: ProposalUpdateRequest) -> ClassificationProposalResponse:
    # Verify the staged file still exists
    if not any(e.id == file_id for e in list_staged()):
        raise HTTPException(status_code=404, detail=f"Staged file '{file_id}' not found.")

    # Build snake_case updates dict for intake layer
    updates: dict = {}
    if req.domain               is not None: updates["domain"]               = req.domain.strip()
    if req.entity               is not None: updates["entity"]               = req.entity.strip()
    if req.sourceType           is not None: updates["source_type"]          = req.sourceType.strip()
    if req.confidence           is not None: updates["confidence"]           = req.confidence.strip()
    if req.needsReview          is not None: updates["needs_review"]         = req.needsReview
    if req.proposedDestination  is not None: updates["proposed_destination"] = req.proposedDestination.strip()
    updates["status"] = "edited"

    try:
        proposal = update_proposal(file_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal for '{file_id}' not found.")
    return _proposal_to_response(proposal)


@app.post("/api/intake/proposals/approve-batch", response_model=BatchApproveResponse)
def intake_approve_batch(req: BatchApproveRequest) -> BatchApproveResponse:
    if not req.fileIds:
        raise HTTPException(status_code=400, detail="fileIds cannot be empty.")
    approved, skipped_raw = batch_approve_proposals(req.fileIds)
    return BatchApproveResponse(
        approved=[_proposal_to_response(p) for p in approved],
        skipped=[BatchSkippedItem(fileId=s["fileId"], reason=s["reason"]) for s in skipped_raw],
    )


@app.post("/api/intake/proposals/{file_id}/approve", response_model=ClassificationProposalResponse)
def intake_approve(file_id: str) -> ClassificationProposalResponse:
    if not any(e.id == file_id for e in list_staged()):
        raise HTTPException(status_code=404, detail=f"Staged file '{file_id}' not found.")
    proposal = approve_proposal(file_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal for '{file_id}' not found.")
    logger.info(
        "Proposal approved (no file moved): id=%s  dest=%r",
        file_id, proposal.proposed_destination,
    )
    return _proposal_to_response(proposal)


@app.post("/api/intake/proposals/{file_id}/skip", response_model=ClassificationProposalResponse)
def intake_skip(file_id: str) -> ClassificationProposalResponse:
    if not any(e.id == file_id for e in list_staged()):
        raise HTTPException(status_code=404, detail=f"Staged file '{file_id}' not found.")
    proposal = skip_proposal(file_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal for '{file_id}' not found.")
    return _proposal_to_response(proposal)


@app.post("/api/intake/proposals/{file_id}/route", response_model=RouteResponse)
def intake_route(file_id: str) -> RouteResponse:
    cfg = get_config()
    try:
        proposal, route_info = route_proposal(file_id, cfg.vault_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RouteResponse(
        ok=True,
        proposal=_proposal_to_response(proposal),
        route=RouteInfo(
            copied=route_info["copied"],
            relativePath=route_info["relativePath"],
            absolutePath=route_info["absolutePath"],
        ),
    )


# ── intake / archive ──────────────────────────────────────────────────────────

@app.post("/api/intake/staged/{file_id}/archive", response_model=ArchiveResponse)
def intake_archive(file_id: str) -> ArchiveResponse:
    try:
        proposal, archive_info = archive_staged_file(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ArchiveResponse(
        ok=True,
        fileId=file_id,
        archived=ArchiveInfo(
            archiveName=archive_info["archiveName"],
            archivePath=archive_info["archivePath"],
            archivedAt=archive_info["archivedAt"],
        ),
        proposal=_proposal_to_response(proposal),
    )


@app.get("/api/intake/archived", response_model=ArchivedFilesResponse)
def intake_archived() -> ArchivedFilesResponse:
    proposals = list_archived()
    return ArchivedFilesResponse(
        count=len(proposals),
        archived=[_proposal_to_response(p) for p in proposals],
    )


@app.post("/api/intake/proposals/ai-classify-batch", response_model=BatchAiClassifyResponse)
def intake_ai_classify_batch(req: BatchAiClassifyRequest) -> BatchAiClassifyResponse:
    """
    POST /api/intake/proposals/ai-classify-batch

    Classify multiple staged files with the local AI model in one request.

    Batch behavior:
    - Processes each file independently; one failure does not abort the rest.
    - Routed, archived, and approved proposals are skipped.
    - Missing files or proposals are skipped with a reason.
    - Failed Ollama calls are skipped with a reason; existing proposals unchanged.
    - Successful items are updated with classifiedBy: local-ai, status: proposed.
    - All changes are written in a single atomic write.

    Safety: metadata only, no file contents, no vault writes, no tools.
    """
    if not req.fileIds:
        raise HTTPException(status_code=400, detail="fileIds cannot be empty.")
    classified_proposals, skipped_raw = batch_ai_classify_proposals(req.fileIds)
    return BatchAiClassifyResponse(
        classified=[_proposal_to_response(p) for p in classified_proposals],
        skipped=[BatchSkippedItem(fileId=s["fileId"], reason=s["reason"]) for s in skipped_raw],
    )


@app.post("/api/intake/proposals/{file_id}/ai-classify", response_model=ClassificationProposalResponse)
def intake_ai_classify(file_id: str) -> ClassificationProposalResponse:
    """
    POST /api/intake/proposals/{file_id}/ai-classify

    Uses the local Ollama model to reclassify a staged file.

    Safety:
    - Sends metadata only (filename, extension, size, content type).
    - File contents are never read or sent.
    - Vault is never written.
    - No tools are exposed to the model.
    - AI output is strictly validated; invalid output returns HTTP 503.
    - Proposal status is left as 'proposed' (still requires user approval before routing).
    - Available for proposed, edited, or skipped proposals.
    - Not available for routed or archived proposals.
    """
    if not any(e.id == file_id for e in list_staged()):
        raise HTTPException(status_code=404, detail=f"Staged file '{file_id}' not found.")
    try:
        proposal = ai_classify_proposal(file_id)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal for '{file_id}' not found.")
    if proposal.status in ("routed", "archived"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot AI-classify a proposal with status '{proposal.status}'.",
        )
    logger.info("AI classify done: %s  domain=%s  classified_by=%s", file_id, proposal.domain, proposal.classified_by)
    return _proposal_to_response(proposal)


# ── vault (read-only) ────────────────────────────────────────────────────────

@app.get("/api/vault/summary", response_model=VaultSummaryResponse)
def vault_summary() -> VaultSummaryResponse:
    cfg  = get_config()
    data = get_vault_summary(cfg.vault_path)
    return VaultSummaryResponse(
        ok=data["ok"], vaultPath=data["vaultPath"], exists=data["exists"],
        folders=data["folders"],
    )


@app.get("/api/vault/projects", response_model=VaultProjectsResponse)
def vault_projects() -> VaultProjectsResponse:
    cfg   = get_config()
    items = get_projects(cfg.vault_path)
    return VaultProjectsResponse(projects=[VaultProjectItem(**i) for i in items])


@app.get("/api/vault/courses", response_model=VaultCoursesResponse)
def vault_courses() -> VaultCoursesResponse:
    cfg   = get_config()
    items = get_courses(cfg.vault_path)
    return VaultCoursesResponse(courses=[VaultCourseItem(**i) for i in items])


@app.get("/api/vault/hackathons", response_model=VaultHackathonsResponse)
def vault_hackathons() -> VaultHackathonsResponse:
    cfg   = get_config()
    items = get_hackathons(cfg.vault_path)
    return VaultHackathonsResponse(hackathons=[VaultHackathonItem(**i) for i in items])


@app.get("/api/vault/business", response_model=VaultBusinessResponse)
def vault_business() -> VaultBusinessResponse:
    cfg   = get_config()
    items = get_business(cfg.vault_path)
    return VaultBusinessResponse(entities=[VaultBusinessItem(**i) for i in items])


@app.get("/api/vault/tasks", response_model=VaultTasksResponse)
def vault_tasks() -> VaultTasksResponse:
    """
    GET /api/vault/tasks

    Reads ops/task-db.md (priority) or ops/tasks.md from the configured vault.
    Parses Markdown tables and checklists; falls back to preview-only.

    Read-only. No vault writes occur. Preview capped at 2000 chars.
    """
    cfg  = get_config()
    data = get_tasks(cfg.vault_path)
    return VaultTasksResponse(
        path=data["path"],
        exists=data["exists"],
        lastModified=data["lastModified"],
        preview=data["preview"],
        tasks=[VaultTask(**t) for t in data["tasks"]],
        parseMode=data["parseMode"],
    )


@app.post("/api/vault/tasks", response_model=TaskStatusUpdateResponse)
def vault_task_create(req: CreateVaultTaskRequest) -> TaskStatusUpdateResponse:
    """
    POST /api/vault/tasks

    Append a new task to the vault task file.

    File selection:
    - ops/task-db.md (priority) → ops/tasks.md → creates ops/task-db.md if neither exists.

    Supported formats:
    - markdown-table: appends a new pipe-delimited row.
    - checklist:      appends a new checkbox item.
    - preview-only:   returns HTTP 400 — safe append not possible.

    Safety:
    - Validates title (required), status (allowlist), priority (allowlist if set).
    - Rejects fields containing raw newlines.
    - Sanitizes pipe characters in table cells.
    - Creates a backup under backend/data/backups/tasks/ before writing.
    - Aborts and returns 400 if backup fails.
    - Never writes outside ops/task-db.md or ops/tasks.md.
    - Creates ops/ only when creating the default ops/task-db.md.
    - Never deletes, moves, or rewrites existing tasks.
    """
    cfg = get_config()
    try:
        result = create_task(
            vault_path=cfg.vault_path,
            title=req.title,
            status=req.status,
            area=req.area,
            priority=req.priority,
            due=req.due,
            source=req.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info(
        "Task created via API: id=%s  status=%r  path=%s",
        result["task"]["id"], result["task"]["status"], result["path"],
    )
    return TaskStatusUpdateResponse(
        ok=result["ok"],
        task=VaultTask(**result["task"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


@app.patch("/api/vault/tasks/{task_id}/status", response_model=TaskStatusUpdateResponse)
def vault_task_update_status(task_id: str, req: TaskStatusUpdateRequest) -> TaskStatusUpdateResponse:
    """
    PATCH /api/vault/tasks/{task_id}/status

    Update a single task's status in the vault task file.

    Allowed statuses: todo | in progress | blocked | done

    Safety:
    - Only writes to ops/task-db.md or ops/tasks.md.
    - Creates a backup under backend/data/backups/tasks/ before writing.
    - Re-reads and re-parses the file on every call (no stale state).
    - Verifies task location and title before writing (conflict detection).
    - Returns 400 on any validation or conflict error; file is not modified.
    - No other vault files are touched.
    """
    cfg = get_config()
    try:
        result = update_task_status(cfg.vault_path, task_id, req.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info(
        "Task status patched: id=%s  status=%r  path=%s",
        task_id, req.status, result["path"],
    )
    return TaskStatusUpdateResponse(
        ok=result["ok"],
        task=VaultTask(**result["task"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


@app.get("/api/vault/calendar-candidates", response_model=CalendarCandidatesResponse)
def vault_calendar_candidates() -> CalendarCandidatesResponse:
    """
    GET /api/vault/calendar-candidates

    Reads ops/calendar-candidates.md from the configured vault.
    Parses Markdown table candidates; falls back to preview-only or missing.

    Read-only. No vault writes. Preview capped at 2000 chars.
    parseMode: "markdown-table" | "preview-only" | "missing"
    """
    cfg  = get_config()
    data = get_calendar_candidates(cfg.vault_path)
    return CalendarCandidatesResponse(
        path=data["path"],
        exists=data["exists"],
        lastModified=data["lastModified"],
        preview=data["preview"],
        parseMode=data["parseMode"],
        candidates=[CalendarCandidate(**c) for c in data["candidates"]],
    )


@app.post("/api/vault/calendar-candidates/create", response_model=CalendarCandidatesResponse)
def vault_calendar_candidates_create_file() -> CalendarCandidatesResponse:
    """
    POST /api/vault/calendar-candidates/create

    Create ops/calendar-candidates.md with the default starter table only when
    missing. Existing files are never overwritten.
    """
    cfg = get_config()
    try:
        data = create_calendar_candidates_file(cfg.vault_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CalendarCandidatesResponse(
        path=data["path"],
        exists=data["exists"],
        lastModified=data["lastModified"],
        preview=data["preview"],
        parseMode=data["parseMode"],
        candidates=[CalendarCandidate(**c) for c in data["candidates"]],
    )


@app.post("/api/vault/calendar-candidates", response_model=UpdateCalendarCandidateResponse)
def vault_calendar_candidate_create(
    req: CreateCalendarCandidateRequest,
) -> UpdateCalendarCandidateResponse:
    """
    POST /api/vault/calendar-candidates

    Append one candidate to an existing parseable Markdown table.

    Safety:
    - Missing file is rejected; use the explicit starter-file endpoint first.
    - Backup created under backend/data/backups/calendar/ before append.
    - Rejects raw newlines; sanitizes pipe characters.
    - Only writes ops/calendar-candidates.md.
    - No Google Calendar writes or command execution.
    """
    cfg = get_config()
    payload = {
        "date":     req.date,
        "time":     req.time,
        "duration": req.duration,
        "title":    req.title,
        "reason":   req.reason,
        "source":   req.source,
        "approved": req.approved,
    }
    try:
        result = create_calendar_candidate(cfg.vault_path, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info(
        "Calendar candidate created: id=%s  path=%s",
        result["candidate"]["id"], result["path"],
    )
    return UpdateCalendarCandidateResponse(
        ok=result["ok"],
        candidate=CalendarCandidate(**result["candidate"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


@app.patch(
    "/api/vault/calendar-candidates/{candidate_id}",
    response_model=UpdateCalendarCandidateResponse,
)
def vault_calendar_candidate_update(
    candidate_id: str,
    req: UpdateCalendarCandidateRequest,
) -> UpdateCalendarCandidateResponse:
    """
    PATCH /api/vault/calendar-candidates/{candidate_id}

    Update all editable fields in a single calendar candidate row.

    Safety:
    - Re-reads and re-parses file on every call.
    - Backup created under backend/data/backups/calendar/ before writing.
    - Rejects raw newlines; sanitizes pipe characters.
    - Only writes ops/calendar-candidates.md.
    - No Google Calendar writes.
    """
    cfg = get_config()
    updates = {
        "date":     req.date,
        "time":     req.time,
        "duration": req.duration,
        "title":    req.title,
        "reason":   req.reason,
        "source":   req.source,
        "approved": req.approved,
    }
    try:
        result = update_calendar_candidate(cfg.vault_path, candidate_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info(
        "Calendar candidate patched: id=%s  approved=%r  path=%s",
        candidate_id, req.approved, result["path"],
    )
    return UpdateCalendarCandidateResponse(
        ok=result["ok"],
        candidate=CalendarCandidate(**result["candidate"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


@app.post(
    "/api/vault/calendar-candidates/{candidate_id}/approve",
    response_model=UpdateCalendarCandidateResponse,
)
def vault_calendar_candidate_approve(candidate_id: str) -> UpdateCalendarCandidateResponse:
    """
    POST /api/vault/calendar-candidates/{candidate_id}/approve

    Set Approved = Yes for one calendar candidate.
    Only the Approved cell is modified; all other cells are preserved.

    Safety: same as PATCH endpoint. Backup created before write.
    No Google Calendar writes.
    """
    cfg = get_config()
    try:
        result = approve_calendar_candidate(cfg.vault_path, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info(
        "Calendar candidate approved: id=%s  path=%s",
        candidate_id, result["path"],
    )
    return UpdateCalendarCandidateResponse(
        ok=result["ok"],
        candidate=CalendarCandidate(**result["candidate"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


@app.get("/api/vault/ops/{kind}", response_model=VaultOpsFileResponse)
def vault_ops_file(kind: str) -> VaultOpsFileResponse:
    cfg = get_config()
    try:
        data = get_ops_file(cfg.vault_path, kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return VaultOpsFileResponse(**data)


@app.get("/api/vault/backfill", response_model=BackfillResponse)
def vault_backfill() -> BackfillResponse:
    """
    GET /api/vault/backfill

    Reads ops/backfill.md (priority) or ops/backfill-last-year.md from the vault.
    Parses the Markdown table; falls back to preview-only or missing.

    parseMode: "markdown-table" | "preview-only" | "missing"

    Read-only. No vault writes. Preview capped at 2000 chars.
    Internal location metadata is never exposed.
    """
    cfg  = get_config()
    data = get_backfill(cfg.vault_path)
    return BackfillResponse(
        path=data["path"],
        exists=data["exists"],
        lastModified=data["lastModified"],
        preview=data["preview"],
        parseMode=data["parseMode"],
        items=[BackfillItem(**it) for it in data["items"]],
    )


@app.post("/api/vault/backfill/create", response_model=BackfillResponse)
def vault_backfill_create_file() -> BackfillResponse:
    """
    POST /api/vault/backfill/create

    Create ops/backfill.md with the default starter table only when missing.
    Existing files are never overwritten.

    Safety:
    - Never overwrites an existing file.
    - Only creates ops/backfill.md — never ops/backfill-last-year.md.
    - No repo files modified. No Claude Code/OpenCode launched.
    """
    cfg = get_config()
    try:
        data = create_backfill_file(cfg.vault_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return BackfillResponse(
        path=data["path"],
        exists=data["exists"],
        lastModified=data["lastModified"],
        preview=data["preview"],
        parseMode=data["parseMode"],
        items=[BackfillItem(**it) for it in data["items"]],
    )


@app.post("/api/vault/backfill", response_model=CreateBackfillItemResponse)
def vault_backfill_add_item(req: CreateBackfillItemRequest) -> CreateBackfillItemResponse:
    """
    POST /api/vault/backfill

    Append one backfill item to ops/backfill.md.

    Safety:
    - File must already exist. Call /create first if needed.
    - item is required.
    - type, status, value, agent must be from their respective allowlists.
    - Pipe chars and newlines rejected in all fields.
    - Backup created before every write.
    - Only appends; never modifies existing rows.
    - Never writes ops/backfill-last-year.md.
    - No shell commands. No Claude Code/OpenCode launched. No repo files modified.
    """
    cfg = get_config()
    try:
        result = create_backfill_item(
            vault_path=cfg.vault_path,
            item=req.item,
            item_type=req.type,
            status=req.status,
            value=req.value,
            path=req.path,
            agent=req.agent,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info(
        "Backfill item created via API: id=%s  item=%r  path=%s",
        result["item"]["id"], result["item"]["item"], result["path"],
    )
    return CreateBackfillItemResponse(
        ok=result["ok"],
        item=BackfillItem(**result["item"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


@app.patch(
    "/api/vault/backfill/{item_id}/status",
    response_model=UpdateBackfillStatusResponse,
)
def vault_backfill_update_status(
    item_id: str,
    req: UpdateBackfillStatusRequest,
) -> UpdateBackfillStatusResponse:
    """
    PATCH /api/vault/backfill/{item_id}/status

    Update a single backfill item's status.

    Allowed statuses: new | triaged | in-progress | done | skipped

    Safety:
    - Only writes to ops/backfill.md or ops/backfill-last-year.md.
    - Re-reads and re-parses the file on every call (no stale state).
    - Verifies item name before writing (conflict detection).
    - Creates a backup under backend/data/backups/backfill/ before writing.
    - Returns 400 on any validation or conflict error; file is not modified.
    - No other vault files are touched.
    - No repo files are modified.
    - No Claude/OpenCode process is launched.
    """
    cfg = get_config()
    try:
        result = update_backfill_status(cfg.vault_path, item_id, req.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info(
        "Backfill status patched: id=%s  status=%r  path=%s",
        item_id, req.status, result["path"],
    )
    return UpdateBackfillStatusResponse(
        ok=result["ok"],
        item=BackfillItem(**result["item"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


@app.patch(
    "/api/vault/backfill/{item_id}",
    response_model=UpdateBackfillItemResponse,
)
def vault_backfill_update_item(
    item_id: str,
    req: UpdateBackfillItemRequest,
) -> UpdateBackfillItemResponse:
    """
    PATCH /api/vault/backfill/{item_id}

    Update the non-status fields of a single backfill item in ops/backfill.md.

    Editable: item, type, value, path, agent, notes.
    Preserved: status, unknown columns.

    Safety:
    - Only writes to ops/backfill.md — never ops/backfill-last-year.md.
    - Re-reads and re-parses the file on every call (no stale state).
    - Verifies item name before writing (conflict detection).
    - Creates a backup under backend/data/backups/backfill/ before writing.
    - Returns 400 on any validation or conflict error; file is not modified.
    - No other vault files are touched.
    - No repo files are modified.
    - No Claude/OpenCode process is launched.
    """
    cfg = get_config()
    try:
        result = update_backfill_item(
            vault_path=cfg.vault_path,
            item_id=item_id,
            item=req.item,
            item_type=req.type,
            value=req.value,
            path=req.path,
            agent=req.agent,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info(
        "Backfill item patched: id=%s  item=%r  path=%s",
        item_id, req.item, result["path"],
    )
    return UpdateBackfillItemResponse(
        ok=result["ok"],
        item=BackfillItem(**result["item"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


@app.get("/api/vault/resume-pipeline", response_model=ResumePipelineResponse)
def vault_resume_pipeline() -> ResumePipelineResponse:
    """
    GET /api/vault/resume-pipeline

    Reads ops/resume-pipeline.md from the vault.
    Parses the Markdown table; falls back to preview-only or missing.

    parseMode: "markdown-table" | "preview-only" | "missing"

    Read-only. No vault writes. Preview capped at 2000 chars.
    """
    cfg  = get_config()
    data = get_resume_pipeline(cfg.vault_path)
    return ResumePipelineResponse(
        path=data["path"],
        exists=data["exists"],
        lastModified=data["lastModified"],
        preview=data["preview"],
        parseMode=data["parseMode"],
        items=[ResumePipelineItem(**it) for it in data["items"]],
    )


@app.patch(
    "/api/vault/resume-pipeline/{item_id}/status",
    response_model=UpdateResumePipelineStatusResponse,
)
def vault_resume_pipeline_update_status(
    item_id: str,
    req: UpdateResumePipelineStatusRequest,
) -> UpdateResumePipelineStatusResponse:
    """
    PATCH /api/vault/resume-pipeline/{item_id}/status

    Update a single resume-pipeline item's status.

    Allowed statuses: new | tailoring | applied | interview | offer | rejected | archived

    Safety:
    - Only writes to ops/resume-pipeline.md.
    - Re-reads and re-parses the file on every call (no stale state).
    - Verifies target name before writing (conflict detection).
    - Creates a backup under backend/data/backups/resume/ before writing.
    - Returns 400 on any validation or conflict error; file is not modified.
    - No other vault files are touched.
    - No browser automation or application submission occurs.
    """
    cfg = get_config()
    try:
        result = update_resume_pipeline_status(cfg.vault_path, item_id, req.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info(
        "Resume pipeline status patched: id=%s  status=%r  path=%s",
        item_id, req.status, result["path"],
    )
    return UpdateResumePipelineStatusResponse(
        ok=result["ok"],
        item=ResumePipelineItem(**result["item"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


@app.post("/api/vault/resume-pipeline/create", response_model=ResumePipelineResponse)
def vault_resume_pipeline_create_file() -> ResumePipelineResponse:
    """
    POST /api/vault/resume-pipeline/create

    Create ops/resume-pipeline.md with a starter Markdown table if it does not exist.
    Returns the full resume-pipeline response (same shape as GET).

    Safety:
    - Never overwrites an existing file.
    - Only creates ops/resume-pipeline.md.
    - No shell commands, AI calls, or browser automation.
    """
    cfg = get_config()
    try:
        data = create_resume_pipeline_file(cfg.vault_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ResumePipelineResponse(
        path=data["path"],
        exists=data["exists"],
        lastModified=data.get("lastModified"),
        preview=data.get("preview"),
        parseMode=data["parseMode"],
        items=[ResumePipelineItem(**it) for it in data["items"]],
    )


@app.post("/api/vault/resume-pipeline", response_model=CreateResumePipelineItemResponse)
def vault_resume_pipeline_create_item(
    req: CreateResumePipelineItemRequest,
) -> CreateResumePipelineItemResponse:
    """
    POST /api/vault/resume-pipeline

    Append a new resume-pipeline item row to ops/resume-pipeline.md.

    Safety:
    - File must already exist and contain a Markdown table.
    - Rejects raw newlines in all fields.
    - Sanitizes pipe characters in all table cells.
    - Creates a backup before appending.
    - No AI calls, no browser automation, no application submission.
    """
    cfg = get_config()
    try:
        result = create_resume_pipeline_item(
            vault_path=cfg.vault_path,
            target=req.target,
            company=req.company,
            role=req.role,
            status=req.status,
            priority=req.priority,
            deadline=req.deadline,
            link=req.link,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CreateResumePipelineItemResponse(
        ok=result["ok"],
        item=ResumePipelineItem(**result["item"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


@app.patch(
    "/api/vault/resume-pipeline/{item_id}",
    response_model=UpdateResumePipelineItemResponse,
)
def vault_resume_pipeline_update_item(
    item_id: str,
    req: UpdateResumePipelineItemRequest,
) -> UpdateResumePipelineItemResponse:
    """
    PATCH /api/vault/resume-pipeline/{item_id}

    Update the non-status fields of a single resume-pipeline item.
    Editable: target, company, role, priority, deadline, link, notes.
    Status is always preserved (use /status endpoint to change it).

    Safety:
    - Only writes to ops/resume-pipeline.md.
    - Re-reads and re-parses the file on every call (no stale state).
    - Verifies target name before writing (conflict detection).
    - Creates a backup before writing.
    - No AI calls, no browser automation, no application submission.
    """
    cfg = get_config()
    try:
        result = update_resume_pipeline_item(
            vault_path=cfg.vault_path,
            item_id=item_id,
            target=req.target,
            company=req.company,
            role=req.role,
            priority=req.priority,
            deadline=req.deadline,
            link=req.link,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return UpdateResumePipelineItemResponse(
        ok=result["ok"],
        item=ResumePipelineItem(**result["item"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


# ── escalation queue ─────────────────────────────────────────────────────────

@app.get("/api/vault/escalations", response_model=EscalationResponse)
def vault_escalations() -> EscalationResponse:
    """
    GET /api/vault/escalations

    Reads ops/escalation-queue.md from the vault.
    Parses the Markdown table; falls back to preview-only or missing.

    parseMode: "markdown-table" | "preview-only" | "missing"

    Read-only. No vault writes. Preview capped at 2000 chars.
    No Claude Code/OpenCode processes launched.
    """
    cfg  = get_config()
    data = get_escalations(cfg.vault_path)
    return EscalationResponse(
        path=data["path"],
        exists=data["exists"],
        lastModified=data["lastModified"],
        preview=data["preview"],
        parseMode=data["parseMode"],
        items=[EscalationItem(**it) for it in data["items"]],
    )


@app.post("/api/vault/escalations/create", response_model=EscalationResponse)
def vault_escalations_create_file() -> EscalationResponse:
    """
    POST /api/vault/escalations/create

    Create ops/escalation-queue.md with the starter table if it is missing.
    If the file already exists, returns the current state without modifying it.

    Safety:
    - Never overwrites an existing file.
    - No Claude Code/OpenCode processes launched.
    - No repo files modified.
    """
    cfg = get_config()
    try:
        data = create_escalation_queue_file(cfg.vault_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return EscalationResponse(
        path=data["path"],
        exists=data["exists"],
        lastModified=data["lastModified"],
        preview=data["preview"],
        parseMode=data["parseMode"],
        items=[EscalationItem(**it) for it in data["items"]],
    )


@app.post("/api/vault/escalations", response_model=EscalationResponse)
def vault_escalations_add(req: CreateEscalationItemRequest) -> EscalationResponse:
    """
    POST /api/vault/escalations

    Append one escalation item to ops/escalation-queue.md.

    Safety:
    - File must already exist. Call /create first if needed.
    - task is required.
    - target must be claude-code | opencode | manual.
    - priority must be high | medium | low or omitted.
    - Pipe chars and newlines rejected in all fields.
    - Backup created before every write.
    - Only appends; never modifies existing rows.
    - No shell commands. No Claude Code/OpenCode launched. No repo files modified.
    """
    cfg = get_config()
    try:
        data = add_escalation_item(
            vault_path=cfg.vault_path,
            task=req.task,
            target=req.target,
            priority=req.priority,
            source=req.source,
            path=req.path,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info("Escalation item added: task=%r  target=%r", req.task, req.target)
    return EscalationResponse(
        path=data["path"],
        exists=data["exists"],
        lastModified=data["lastModified"],
        preview=data["preview"],
        parseMode=data["parseMode"],
        items=[EscalationItem(**it) for it in data["items"]],
    )


@app.patch(
    "/api/vault/escalations/{item_id}/status",
    response_model=UpdateEscalationStatusResponse,
)
def vault_escalations_update_status(
    item_id: str,
    req: UpdateEscalationStatusRequest,
) -> UpdateEscalationStatusResponse:
    """
    PATCH /api/vault/escalations/{item_id}/status

    Update a single escalation item's status.

    Allowed statuses: new | ready | in-progress | done | blocked | skipped

    Safety:
    - Only writes to ops/escalation-queue.md.
    - Re-reads and re-parses the file on every call (no stale state).
    - Verifies task title before writing (conflict detection).
    - Creates a backup under backend/data/backups/escalations/ before writing.
    - Returns 400 on any validation or conflict error; file is not modified.
    - No other vault files are touched.
    - No shell commands. No Claude Code/OpenCode launched. No repo files modified.
    """
    cfg = get_config()
    try:
        result = update_escalation_status(cfg.vault_path, item_id, req.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info(
        "Escalation status patched: id=%s  status=%r  path=%s",
        item_id, req.status, result["path"],
    )
    return UpdateEscalationStatusResponse(
        ok=result["ok"],
        item=EscalationItem(**result["item"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


@app.patch(
    "/api/vault/escalations/{item_id}",
    response_model=UpdateEscalationItemResponse,
)
def vault_escalations_update_item(
    item_id: str,
    req: UpdateEscalationItemRequest,
) -> UpdateEscalationItemResponse:
    """
    PATCH /api/vault/escalations/{item_id}

    Update the editable fields of an existing escalation item.
    Editable: task, target, priority, source, path, notes.
    Preserved: status, created, and any unknown columns.

    Safety:
    - Only writes to ops/escalation-queue.md.
    - Re-reads and re-parses file on every call (no stale state).
    - Verifies task title before writing (conflict detection).
    - Backup created before write; aborted if backup fails.
    - Returns 400 on any validation or conflict error; file not modified.
    - No shell commands. No Claude Code/OpenCode launched. No repo files modified.
    """
    cfg = get_config()
    try:
        result = update_escalation_item(
            vault_path=cfg.vault_path,
            item_id=item_id,
            task=req.task,
            target=req.target,
            priority=req.priority,
            source=req.source,
            path=req.path,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    logger.info(
        "Escalation item patched: id=%s  task=%r  target=%r  path=%s",
        item_id, req.task, req.target, result["path"],
    )
    return UpdateEscalationItemResponse(
        ok=result["ok"],
        item=EscalationItem(**result["item"]),
        path=result["path"],
        updatedAt=result["updatedAt"],
    )


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── agent helpers ─────────────────────────────────────────────────────────────

def _prior_messages(conv_id: str) -> tuple[list[dict], int]:
    """
    Load the last CONTEXT_WINDOW_MESSAGES user/assistant messages from a
    conversation and return them as Ollama-formatted dicts plus a usage count.

    Safety: only 'user' and 'assistant' roles are included — system messages
    and any unexpected roles are excluded. The system prompt is NEVER included.
    No vault, file, or tool content is added here.
    """
    data = get_conversation(conv_id)
    if not data:
        return [], 0
    eligible = [
        {"role": m["role"], "content": m["content"]}
        for m in data.get("messages", [])
        if m.get("role") in ("user", "assistant")
    ]
    window = eligible[-CONTEXT_WINDOW_MESSAGES:] if eligible else []
    return window, len(window)


# ── local agent ───────────────────────────────────────────────────────────────

@app.get("/api/agent/status", response_model=AgentStatusResponse)
def agent_status() -> AgentStatusResponse:
    return AgentStatusResponse(**get_agent_status())


# ── agent modes (v0: backend-enforced policy; read-only) ────────────────────────

@app.get("/api/agent/modes", response_model=AgentModesResponse)
def agent_modes_list() -> AgentModesResponse:
    """
    Read-only list of agent modes with availability + permissions. Lets the frontend
    show honest, backend-enforced mode behavior. No tool runs; nothing is mutated.
    """
    return AgentModesResponse(modes=[AgentModePolicy(**m) for m in list_agent_modes()])


# ── agent tool requests (v0: evaluate-only via Permission Gateway; no execution) ─

@app.post("/api/agent/tool-request", response_model=None)
def agent_tool_request_create(req: CreateAgentToolRequestRequest):
    """
    Evaluate a structured agent tool-request proposal through the Permission Gateway
    and log the evaluation. NEVER executes the tool, never calls /execute, the brain
    wrapper, any external service, or the vault. args/reason are untrusted.

    Agent Mode Enforcement v0: the request is gated by the selected mode. In
    locked / observe / computer_use (and any mode that cannot evaluate tool requests)
    it is BLOCKED — nothing is evaluated, stored, or logged — and a clear
    blocked_by_mode response is returned.
    """
    mode = normalize_mode(req.mode)
    if not can_evaluate_tool_requests(mode):
        # Blocked by mode: do not evaluate, store, or log anything.
        return AgentModeBlockedResponse(mode=mode, message=mode_blocked_message(mode))

    try:
        record = create_agent_tool_request(
            tool=req.tool,
            args=req.args,
            reason=req.reason,
            requested_by=req.requestedBy,
            conversation_id=req.conversationId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return AgentToolRequestResponse(**record)


@app.get("/api/agent/tool-requests", response_model=AgentToolRequestListResponse)
def agent_tool_requests_list(limit: int = 50) -> AgentToolRequestListResponse:
    """Read-only list of recent agent tool requests, newest first."""
    return AgentToolRequestListResponse(
        requests=[AgentToolRequestResponse(**r) for r in list_agent_tool_requests(limit=limit)],
    )


@app.post("/api/agent/chat", response_model=AgentChatResponse)
def agent_chat(req: AgentChatRequest) -> AgentChatResponse:
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty.")

    # Resolve or create the conversation for this turn.
    conv_id = req.conversationId
    if conv_id:
        if get_conversation(conv_id) is None:
            raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found.")
    else:
        conv_id = create_conversation()["id"]

    # Load bounded prior context from the existing conversation.
    prior, context_used = _prior_messages(conv_id)

    try:
        result = chat_with_agent(
            message=req.message,
            mode=req.mode,
            context=req.context.model_dump() if req.context else None,
            prior_messages=prior,
        )
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Persist the chat turn (user + assistant messages) on success.
    save_chat_turn(
        conversation_id=conv_id,
        user_message=req.message,
        assistant_content=result["message"],
        provider=result["provider"],
        model=result["model"],
        duration_ms=result["durationMs"],
    )

    # Agent Mode Enforcement v0: only EVALUATE structured tool requests when the mode
    # allows it. In locked / observe / computer_use we still parse for visibility, but
    # nothing is evaluated, stored, or logged — a clear blocked-by-mode notice is
    # returned instead. No mode executes anything.
    mode = normalize_mode(req.mode)
    structured_model = None
    if can_evaluate_tool_requests(mode):
        structured = evaluate_structured_output(result["message"], conv_id)
        if structured["toolRequests"] or structured["parseErrors"]:
            structured_model = AgentChatStructured(
                toolRequests=[AgentToolRequestResponse(**r) for r in structured["toolRequests"]],
                parseErrors=structured["parseErrors"],
                mode=mode,
                blockedByMode=False,
            )
    else:
        parsed = parse_structured_output(result["message"])  # visibility only — not stored/evaluated
        if parsed["requests"] or parsed["parseErrors"]:
            structured_model = AgentChatStructured(
                toolRequests=[],
                parseErrors=[],
                mode=mode,
                blockedByMode=True,
                message=mode_blocked_message(mode),
            )

    return AgentChatResponse(
        ok=result["ok"],
        provider=result["provider"],
        model=result["model"],
        message=result["message"],
        durationMs=result["durationMs"],
        conversationId=conv_id,
        contextWindowMessages=CONTEXT_WINDOW_MESSAGES,
        contextMessagesUsed=context_used,
        structured=structured_model,
    )


# ── conversations ─────────────────────────────────────────────────────────────

@app.post("/api/conversations", response_model=ConversationSummary)
def conversations_create(req: CreateConversationRequest) -> ConversationSummary:
    data = create_conversation(req.title)
    return ConversationSummary(
        id=data["id"], title=data["title"],
        createdAt=data["createdAt"], updatedAt=data["updatedAt"],
        messageCount=0,
    )


@app.get("/api/conversations", response_model=ConversationListResponse)
def conversations_list() -> ConversationListResponse:
    summaries = list_conversations()
    return ConversationListResponse(
        conversations=[ConversationSummary(**s) for s in summaries]
    )


@app.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
def conversations_get(conversation_id: str) -> ConversationDetail:
    data = get_conversation(conversation_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found.")
    from app.models import ConversationMessage as CM  # local import avoids circular at module top
    return ConversationDetail(
        id=data["id"], title=data["title"],
        createdAt=data["createdAt"], updatedAt=data["updatedAt"],
        messages=[CM(**m) for m in data.get("messages", [])],
    )


@app.delete("/api/conversations/{conversation_id}", response_model=DeleteConversationResponse)
def conversations_delete(conversation_id: str) -> DeleteConversationResponse:
    deleted = delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found.")
    return DeleteConversationResponse(ok=True, deletedId=conversation_id)


# ── streaming agent chat ──────────────────────────────────────────────────────

@app.post("/api/agent/chat/stream")
def agent_chat_stream(req: AgentChatRequest) -> StreamingResponse:
    """
    POST /api/agent/chat/stream

    Streams SSE events:
      event: meta  — {conversationId, provider, model}
      event: token — {text}        (one per Ollama chunk)
      event: done  — {ok, durationMs}
      event: error — {message}     (then stream terminates)

    Conversation is saved only on successful completion.
    No tools, no vault, no brain commands.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty.")

    # Resolve or create conversation before streaming begins.
    conv_id = req.conversationId
    if conv_id:
        if get_conversation(conv_id) is None:
            raise HTTPException(status_code=404, detail=f"Conversation '{conv_id}' not found.")
    else:
        conv_id = create_conversation()["id"]

    message = req.message
    # Agent Mode Enforcement v0 — resolved once, used to gate structured-output
    # evaluation after streaming completes.
    mode = normalize_mode(req.mode)

    # Load bounded prior context before entering the generator.
    prior, context_used = _prior_messages(conv_id)

    def generate():
        # meta event — sent before any tokens so the client knows the conv id
        yield _sse("meta", {
            "conversationId":        conv_id,
            "provider":              "ollama",
            "model":                 LOCAL_MODEL,
            "contextWindowMessages": CONTEXT_WINDOW_MESSAGES,
            "contextMessagesUsed":   context_used,
        })

        accumulated: list[str] = []
        t0 = time.monotonic()

        try:
            for token in stream_ollama_chat(message, prior_messages=prior):
                accumulated.append(token)
                yield _sse("token", {"text": token})
        except ValueError as exc:
            yield _sse("error", {"message": str(exc)})
            return
        except Exception as exc:
            yield _sse("error", {"message": f"Unexpected error: {exc}"})
            return

        duration_ms = round((time.monotonic() - t0) * 1000, 1)
        full_content = "".join(accumulated)

        if full_content:
            save_chat_turn(
                conversation_id=conv_id,
                user_message=message,
                assistant_content=full_content,
                provider="ollama",
                model=LOCAL_MODEL,
                duration_ms=duration_ms,
            )

            # After streaming completes, handle structured tool requests under the
            # current mode (evaluate-only — nothing is ever executed). In modes that
            # cannot evaluate (locked / observe / computer_use) we parse for visibility
            # only and emit a blocked-by-mode notice; nothing is stored or logged.
            # Failures here must never break the stream, so guard defensively.
            try:
                if can_evaluate_tool_requests(mode):
                    structured = evaluate_structured_output(full_content, conv_id)
                    if structured["toolRequests"] or structured["parseErrors"]:
                        yield _sse("structured", {
                            **structured,
                            "mode": mode,
                            "blockedByMode": False,
                            "message": None,
                        })
                else:
                    parsed = parse_structured_output(full_content)
                    if parsed["requests"] or parsed["parseErrors"]:
                        yield _sse("structured", {
                            "toolRequests": [],
                            "parseErrors": [],
                            "mode": mode,
                            "blockedByMode": True,
                            "message": mode_blocked_message(mode),
                        })
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Structured-output evaluation failed (non-fatal): %s", exc)

        yield _sse("done", {"ok": True, "durationMs": duration_ms})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
