import json
import logging
import time
from pathlib import Path

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
)
from app.agent import (
    chat_with_agent,
    get_agent_status,
    stream_ollama_chat,
    LOCAL_MODEL,
    CONTEXT_WINDOW_MESSAGES,
)
from app.brain import run_brain_command
from app.config import get_config, update_config
from app.conversations import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    save_chat_turn,
)
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
    BatchApproveResponse,
    BatchSkippedItem,
    BrainRunRequest,
    BrainRunResponse,
    ClassificationProposalResponse,
    ConfigResponse,
    ConfigUpdateRequest,
    DeleteStagedResponse,
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
    allow_methods=["GET", "POST", "PUT", "DELETE"],
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
    return run_brain_command(req.command)


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


@app.get("/api/vault/ops/{kind}", response_model=VaultOpsFileResponse)
def vault_ops_file(kind: str) -> VaultOpsFileResponse:
    cfg = get_config()
    try:
        data = get_ops_file(cfg.vault_path, kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return VaultOpsFileResponse(**data)


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

    return AgentChatResponse(
        ok=result["ok"],
        provider=result["provider"],
        model=result["model"],
        message=result["message"],
        durationMs=result["durationMs"],
        conversationId=conv_id,
        contextWindowMessages=CONTEXT_WINDOW_MESSAGES,
        contextMessagesUsed=context_used,
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

        yield _sse("done", {"ok": True, "durationMs": duration_ms})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
