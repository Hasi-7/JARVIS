from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


# ── config ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    ok: bool
    service: str
    version: str


class ConfigResponse(BaseModel):
    vaultPath: str
    brainCmd: str
    backendReady: bool
    brainCmdExists: bool
    vaultPathExists: bool
    configSource: Optional[str] = None
    configPersisted: Optional[bool] = None
    configWarning: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    vaultPath: str
    brainCmd: str


# ── brain command runner ──────────────────────────────────────────────────────

class BrainRunRequest(BaseModel):
    command: str


class BrainRunResponse(BaseModel):
    command: str
    ok: bool
    exitCode: int
    stdout: str
    stderr: str
    durationMs: float


# ── entity creation ───────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class CreateCourseRequest(BaseModel):
    code: str
    name: Optional[str] = None


class CreateHackathonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class CreateBusinessRequest(BaseModel):
    name: str
    description: Optional[str] = None


class EntityPaths(BaseModel):
    wikiPath: Optional[str] = None
    rawPath: Optional[str] = None


class EntityCreateResponse(BaseModel):
    ok: bool
    entityType: str
    name: str
    command: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    paths: EntityPaths


# ── intake / staging ──────────────────────────────────────────────────────────

class StagedFileInfo(BaseModel):
    id: str
    originalName: str
    storedName: str
    sizeBytes: int
    contentType: Optional[str]
    uploadedAt: str
    status: str


class UploadResponse(BaseModel):
    uploaded: List[StagedFileInfo]


class StagedFilesResponse(BaseModel):
    files: List[StagedFileInfo]


class DeleteStagedResponse(BaseModel):
    ok: bool
    deletedId: str


# ── classification proposals ──────────────────────────────────────────────────

class ClassificationProposalResponse(BaseModel):
    fileId: str
    domain: str
    entity: str
    sourceType: str
    proposedDestination: str
    confidence: str
    needsReview: bool
    reason: str
    status: str
    # Populated after routing
    routedAt:   Optional[str] = None
    routedPath: Optional[str] = None
    routedName: Optional[str] = None
    # Populated after archiving
    archivedAt:   Optional[str] = None
    archivePath:  Optional[str] = None
    archiveName:  Optional[str] = None
    # Populated after AI classification
    classifiedBy:    Optional[str] = None
    aiModel:         Optional[str] = None
    aiClassifiedAt:  Optional[str] = None


class RouteInfo(BaseModel):
    copied: bool
    relativePath: str
    absolutePath: str


class RouteResponse(BaseModel):
    ok: bool
    proposal: ClassificationProposalResponse
    route: RouteInfo


class ProposalsResponse(BaseModel):
    proposals: List[ClassificationProposalResponse]


class ProposalUpdateRequest(BaseModel):
    domain: Optional[str] = None
    entity: Optional[str] = None
    sourceType: Optional[str] = None
    proposedDestination: Optional[str] = None
    confidence: Optional[str] = None
    needsReview: Optional[bool] = None


class BatchApproveRequest(BaseModel):
    fileIds: List[str]


class BatchSkippedItem(BaseModel):
    fileId: str
    reason: str


class BatchApproveResponse(BaseModel):
    approved: List[ClassificationProposalResponse]
    skipped: List[BatchSkippedItem]


class BatchAiClassifyRequest(BaseModel):
    fileIds: List[str]


class BatchAiClassifyResponse(BaseModel):
    classified: List[ClassificationProposalResponse]
    skipped: List[BatchSkippedItem]


# ── local agent ──────────────────────────────────────────────────────────────

class AgentStatusResponse(BaseModel):
    ok: bool
    provider: str
    baseUrl: str
    model: str
    available: bool
    message: str


class AgentChatContext(BaseModel):
    screen: Optional[str] = None
    vaultPath: Optional[str] = None


class AgentChatRequest(BaseModel):
    message: str
    mode: Optional[str] = None
    conversationId: Optional[str] = None
    context: Optional[AgentChatContext] = None


class AgentChatResponse(BaseModel):
    ok: bool
    provider: str
    model: str
    message: str
    durationMs: float
    conversationId: str
    contextWindowMessages: Optional[int] = None
    contextMessagesUsed: Optional[int] = None
    # Optional structured tool requests parsed from the assistant reply (evaluate-only).
    structured: Optional["AgentChatStructured"] = None


# ── conversations ─────────────────────────────────────────────────────────────

class CreateConversationRequest(BaseModel):
    title: Optional[str] = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str
    messageCount: int


class ConversationMessage(BaseModel):
    id: str
    role: str
    content: str
    createdAt: str
    provider: Optional[str] = None
    model: Optional[str] = None
    durationMs: Optional[float] = None


class ConversationDetail(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str
    messages: List[ConversationMessage]


class ConversationListResponse(BaseModel):
    conversations: List[ConversationSummary]


class DeleteConversationResponse(BaseModel):
    ok: bool
    deletedId: str


# ── archive ───────────────────────────────────────────────────────────────────

# ── vault (read-only) ────────────────────────────────────────────────────────

class VaultFolders(BaseModel):
    raw:       Optional[bool] = None
    wiki:      Optional[bool] = None
    ops:       Optional[bool] = None
    schema:    Optional[bool] = None
    templates: Optional[bool] = None


class VaultSummaryResponse(BaseModel):
    ok:        bool
    vaultPath: str
    exists:    bool
    folders:   VaultFolders


class VaultProjectItem(BaseModel):
    id:           str
    name:         str
    wikiPath:     Optional[str] = None
    rawPath:      Optional[str] = None
    status:       str = "unknown"
    lastModified: Optional[str] = None
    preview:      Optional[str] = None


class VaultProjectsResponse(BaseModel):
    projects: List[VaultProjectItem]


class VaultCourseItem(BaseModel):
    id:           str
    name:         str
    wikiPath:     Optional[str] = None
    rawPath:      Optional[str] = None
    lastModified: Optional[str] = None
    preview:      Optional[str] = None


class VaultCoursesResponse(BaseModel):
    courses: List[VaultCourseItem]


class VaultHackathonItem(BaseModel):
    id:           str
    name:         str
    wikiPath:     Optional[str] = None
    rawPath:      Optional[str] = None
    lastModified: Optional[str] = None
    preview:      Optional[str] = None


class VaultHackathonsResponse(BaseModel):
    hackathons: List[VaultHackathonItem]


class VaultBusinessItem(BaseModel):
    id:           str
    name:         str
    wikiPath:     Optional[str] = None
    rawPath:      Optional[str] = None
    lastModified: Optional[str] = None
    preview:      Optional[str] = None


class VaultBusinessResponse(BaseModel):
    entities: List[VaultBusinessItem]


class VaultOpsFileResponse(BaseModel):
    path:         str
    exists:       bool
    preview:      Optional[str] = None
    lastModified: Optional[str] = None


class VaultTask(BaseModel):
    id:       str
    title:    str
    status:   str = ""
    area:     Optional[str] = None
    priority: Optional[str] = None
    due:      Optional[str] = None
    source:   Optional[str] = None
    raw:      str = ""


class VaultTasksResponse(BaseModel):
    path:         str
    exists:       bool
    lastModified: Optional[str] = None
    preview:      Optional[str] = None
    tasks:        List[VaultTask]
    parseMode:    str  # "markdown-table" | "checklist" | "preview-only"


class TaskStatusUpdateRequest(BaseModel):
    status: str  # must be one of: todo | in progress | blocked | done


class TaskStatusUpdateResponse(BaseModel):
    ok:        bool
    task:      VaultTask
    path:      str
    updatedAt: str


class CreateVaultTaskRequest(BaseModel):
    title:    str
    status:   str              # todo | in progress | blocked | done
    area:     Optional[str] = None
    priority: Optional[str] = None  # low | medium | high
    due:      Optional[str] = None
    source:   Optional[str] = None


# ── calendar candidates ───────────────────────────────────────────────────────

class CalendarCandidate(BaseModel):
    id:       str
    date:     str        = ""
    time:     Optional[str] = None
    duration: Optional[str] = None
    title:    str        = ""
    reason:   Optional[str] = None
    source:   Optional[str] = None
    approved: str        = "No"
    raw:      str        = ""


class CalendarCandidatesResponse(BaseModel):
    path:         str
    exists:       bool
    lastModified: Optional[str] = None
    preview:      Optional[str] = None
    parseMode:    str   # "markdown-table" | "preview-only" | "missing"
    candidates:   List[CalendarCandidate]


class UpdateCalendarCandidateRequest(BaseModel):
    date:     str        = ""
    time:     Optional[str] = None
    duration: Optional[str] = None
    title:    str
    reason:   Optional[str] = None
    source:   Optional[str] = None
    approved: str        = "No"   # "Yes" | "No"


class CreateCalendarCandidateRequest(BaseModel):
    date:     str
    time:     Optional[str] = None
    duration: Optional[str] = None
    title:    str
    reason:   Optional[str] = None
    source:   Optional[str] = None
    approved: str        = "No"   # "Yes" | "No"


class UpdateCalendarCandidateResponse(BaseModel):
    ok:        bool
    candidate: CalendarCandidate
    path:      str
    updatedAt: str


# ── backfill ──────────────────────────────────────────────────────────────────

class BackfillItem(BaseModel):
    id:     str
    item:   str
    type:   Optional[str] = None
    status: str           = "new"
    value:  Optional[str] = None
    path:   Optional[str] = None
    notes:  Optional[str] = None
    agent:  Optional[str] = None
    raw:    str           = ""


class BackfillResponse(BaseModel):
    path:         str
    exists:       bool
    lastModified: Optional[str] = None
    preview:      Optional[str] = None
    parseMode:    str            # "markdown-table" | "preview-only" | "missing"
    items:        List[BackfillItem]


class UpdateBackfillStatusRequest(BaseModel):
    status: str  # new | triaged | in-progress | done | skipped


class UpdateBackfillStatusResponse(BaseModel):
    ok:        bool
    item:      BackfillItem
    path:      str
    updatedAt: str


class CreateBackfillItemRequest(BaseModel):
    item:   str
    type:   Optional[str] = None   # project|repo|hackathon|course|business|other
    status: Optional[str] = None   # new|triaged|in-progress|done|skipped
    value:  Optional[str] = None   # high|medium|low
    path:   Optional[str] = None
    agent:  Optional[str] = None   # claude-code|opencode|manual
    notes:  Optional[str] = None


class CreateBackfillItemResponse(BaseModel):
    ok:        bool
    item:      BackfillItem
    path:      str
    updatedAt: str


class UpdateBackfillItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item:  str
    type:  Optional[str] = None   # project|repo|hackathon|course|business|other
    value: Optional[str] = None   # high|medium|low|null
    path:  Optional[str] = None
    agent: Optional[str] = None   # claude-code|opencode|manual|null
    notes: Optional[str] = None


class UpdateBackfillItemResponse(BaseModel):
    ok:        bool
    item:      BackfillItem
    path:      str
    updatedAt: str


# ── resume pipeline ───────────────────────────────────────────────────────────

class ResumePipelineItem(BaseModel):
    id:       str
    target:   str
    company:  Optional[str] = None
    role:     Optional[str] = None
    status:   str           = "new"
    priority: Optional[str] = None
    deadline: Optional[str] = None
    link:     Optional[str] = None
    notes:    Optional[str] = None
    raw:      str           = ""


class ResumePipelineResponse(BaseModel):
    path:         str
    exists:       bool
    lastModified: Optional[str] = None
    preview:      Optional[str] = None
    parseMode:    str            # "markdown-table" | "preview-only" | "missing"
    items:        List[ResumePipelineItem]


class UpdateResumePipelineStatusRequest(BaseModel):
    status: str  # new | tailoring | applied | interview | offer | rejected | archived


class UpdateResumePipelineStatusResponse(BaseModel):
    ok:        bool
    item:      ResumePipelineItem
    path:      str
    updatedAt: str


class CreateResumePipelineItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target:   str
    company:  Optional[str] = None
    role:     Optional[str] = None
    status:   Optional[str] = None   # new|tailoring|applied|interview|offer|rejected|archived
    priority: Optional[str] = None   # high|medium|low
    deadline: Optional[str] = None
    link:     Optional[str] = None
    notes:    Optional[str] = None


class CreateResumePipelineItemResponse(BaseModel):
    ok:        bool
    item:      ResumePipelineItem
    path:      str
    updatedAt: str


class UpdateResumePipelineItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target:   str
    company:  Optional[str] = None
    role:     Optional[str] = None
    priority: Optional[str] = None   # high|medium|low|null
    deadline: Optional[str] = None
    link:     Optional[str] = None
    notes:    Optional[str] = None


class UpdateResumePipelineItemResponse(BaseModel):
    ok:        bool
    item:      ResumePipelineItem
    path:      str
    updatedAt: str


# ── archive ───────────────────────────────────────────────────────────────────

class ArchiveInfo(BaseModel):
    archiveName: str
    archivePath: str
    archivedAt: str


class ArchiveResponse(BaseModel):
    ok: bool
    fileId: str
    archived: ArchiveInfo
    proposal: ClassificationProposalResponse


class ArchivedFilesResponse(BaseModel):
    count: int
    archived: List[ClassificationProposalResponse]


# ── escalation queue ─────────────────────────────────────────────────────────

class EscalationItem(BaseModel):
    id:       str
    task:     str
    target:   Optional[str] = None
    status:   str           = "new"
    priority: Optional[str] = None
    source:   Optional[str] = None
    path:     Optional[str] = None
    notes:    Optional[str] = None
    created:  Optional[str] = None
    raw:      str           = ""


class EscalationResponse(BaseModel):
    path:         str
    exists:       bool
    lastModified: Optional[str] = None
    preview:      Optional[str] = None
    parseMode:    str            # "markdown-table" | "preview-only" | "missing"
    items:        List[EscalationItem]


class CreateEscalationItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task:     str
    target:   str
    priority: Optional[str] = None
    source:   Optional[str] = None
    path:     Optional[str] = None
    notes:    Optional[str] = None


class UpdateEscalationStatusRequest(BaseModel):
    status: str  # new | ready | in-progress | done | blocked | skipped


class UpdateEscalationStatusResponse(BaseModel):
    ok:        bool
    item:      EscalationItem
    path:      str
    updatedAt: str


class UpdateEscalationItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task:     str
    target:   str
    priority: Optional[str] = None
    source:   Optional[str] = None
    path:     Optional[str] = None
    notes:    Optional[str] = None


class UpdateEscalationItemResponse(BaseModel):
    ok:        bool
    item:      EscalationItem
    path:      str
    updatedAt: str


# ── dashboard summary ─────────────────────────────────────────────────────────

class DashboardRawSummary(BaseModel):
    staged: int = 0
    proposed: int = 0
    edited: int = 0
    approved: int = 0
    routed: int = 0
    archived: int = 0


class DashboardTaskSummary(BaseModel):
    total: int = 0
    todo: int = 0
    inProgress: int = 0
    blocked: int = 0
    done: int = 0


class DashboardCalendarSummary(BaseModel):
    total: int = 0
    approved: int = 0
    pending: int = 0


class DashboardEntitySummary(BaseModel):
    projects: int = 0
    courses: int = 0
    hackathons: int = 0
    business: int = 0


class DashboardBackfillSummary(BaseModel):
    total: int = 0
    new: int = 0
    triaged: int = 0
    inProgress: int = 0
    done: int = 0
    skipped: int = 0


class DashboardResumeSummary(BaseModel):
    total: int = 0
    new: int = 0
    tailoring: int = 0
    applied: int = 0
    interview: int = 0
    offer: int = 0
    rejected: int = 0
    archived: int = 0


class DashboardRuntimeSummary(BaseModel):
    backend: str = "connected"
    brain: str = "unknown"
    agent: str = "unknown"
    vaultExists: bool = False


class DashboardSummaryError(BaseModel):
    source: str
    message: str


class DashboardEscalationSummary(BaseModel):
    total:      int = 0
    active:     int = 0
    new:        int = 0
    ready:      int = 0
    inProgress: int = 0
    blocked:    int = 0
    done:       int = 0
    skipped:    int = 0


class DashboardTodayPlanItem(BaseModel):
    id: str
    title: str
    status: str
    priority: Optional[str] = None
    due: Optional[str] = None
    area: Optional[str] = None
    source: Optional[str] = None
    reason: str


class DashboardTodayPlan(BaseModel):
    items: List[DashboardTodayPlanItem] = []
    source: str = "tasks"
    generatedAt: str = ""


# ── active work drill-down ────────────────────────────────────────────────────

class DashboardActiveWorkBackfillItem(BaseModel):
    id:       str
    title:    str
    status:   str
    priority: Optional[str] = None
    type:     Optional[str] = None
    path:     Optional[str] = None
    reason:   str


class DashboardActiveWorkEscalationItem(BaseModel):
    id:       str
    title:    str
    status:   str
    priority: Optional[str] = None
    target:   Optional[str] = None
    path:     Optional[str] = None
    reason:   str


class DashboardActiveWorkResumeItem(BaseModel):
    id:       str
    title:    str
    status:   str
    priority: Optional[str] = None
    company:  Optional[str] = None
    role:     Optional[str] = None
    reason:   str


class DashboardActiveWorkCalendarItem(BaseModel):
    id:     str
    title:  str
    status: str
    date:   Optional[str] = None
    time:   Optional[str] = None
    reason: str


class DashboardActiveWorkRawItem(BaseModel):
    id:     str
    title:  str
    status: str
    reason: str


class DashboardActiveWork(BaseModel):
    backfill:    List[DashboardActiveWorkBackfillItem]    = []
    escalations: List[DashboardActiveWorkEscalationItem] = []
    resume:      List[DashboardActiveWorkResumeItem]      = []
    calendar:    List[DashboardActiveWorkCalendarItem]    = []
    raw:         List[DashboardActiveWorkRawItem]         = []


class DashboardSummaryResponse(BaseModel):
    raw: DashboardRawSummary = DashboardRawSummary()
    tasks: DashboardTaskSummary = DashboardTaskSummary()
    calendar: DashboardCalendarSummary = DashboardCalendarSummary()
    entities: DashboardEntitySummary = DashboardEntitySummary()
    backfill: DashboardBackfillSummary = DashboardBackfillSummary()
    resume: DashboardResumeSummary = DashboardResumeSummary()
    escalations: DashboardEscalationSummary = DashboardEscalationSummary()
    runtime: DashboardRuntimeSummary = DashboardRuntimeSummary()
    todayPlan: DashboardTodayPlan = DashboardTodayPlan()
    activeWork: DashboardActiveWork = DashboardActiveWork()
    errors: List[DashboardSummaryError] = []


# ── proposal queue (v1: aggregates Raw Inbox classification proposals) ──────────

class ProposalDetails(BaseModel):
    filename:   Optional[str] = None
    domain:     Optional[str] = None
    entity:     Optional[str] = None
    sourceType: Optional[str] = None
    reason:     Optional[str] = None


class ProposalItem(BaseModel):
    id:         str
    source:     str                      # raw-inbox (future: research | consolidation | email | mcp | agent)
    type:       str                      # file_route
    riskLevel:  str                      # low | medium | high
    title:      str
    summary:    str
    status:     str                      # pending | approved | rejected | applied | skipped
    confidence: Optional[str] = None     # High | Medium | Low | null
    targetPath: Optional[str] = None
    createdAt:  Optional[str] = None
    updatedAt:  Optional[str] = None
    relatedId:  str
    actions:    List[str] = []           # e.g. ["open_raw_inbox"]
    details:    ProposalDetails = ProposalDetails()


class ProposalListError(BaseModel):
    source:  str
    message: str


class ProposalListResponse(BaseModel):
    proposals: List[ProposalItem] = []
    errors:    List[ProposalListError] = []


# ── tool / MCP connections (v0: read-only readiness inventory) ─────────────────

class ToolConnectionStatus(BaseModel):
    id:            str                  # e.g. obsidian-mcp
    name:          str                  # e.g. Obsidian MCP
    category:      str                  # runtime | mcp | browser | external | developer
    status:        str                  # available | unavailable | not_configured | disabled | planned | error
    enabled:       bool
    riskLevel:     str                  # low | medium | high
    capabilities:  List[str] = []
    allowedNow:    List[str] = []
    blockedNow:    List[str] = []
    requires:      List[str] = []
    lastCheckedAt: Optional[str] = None
    lastError:     Optional[str] = None
    notes:         Optional[str] = None


class ToolConnectionStatusResponse(BaseModel):
    items: List[ToolConnectionStatus] = []


# ── permission gateway (v0: deny-by-default classification, no execution) ───────

class PermissionPolicy(BaseModel):
    tool:             str                  # e.g. gmail.search
    category:         str                  # obsidian | gmail | calendar | browser | computer | brain | filesystem
    riskLevel:        str                  # low | medium | high | disabled
    status:           str                  # not_wired | available | disabled
    requiresApproval: bool
    executionEnabled: bool                 # always False in v0
    notes:            Optional[str] = None


class PermissionPolicyResponse(BaseModel):
    policies: List[PermissionPolicy] = []


class ToolRequestEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool:        str
    args:        Optional[Dict[str, Any]] = None
    reason:      Optional[str] = None
    requestedBy: Optional[str] = None


class ToolRequestEvaluationResponse(BaseModel):
    allowed:              bool             # always False in v0
    decision:             str             # denied | requires_approval | not_wired | disabled
    riskLevel:            str             # low | medium | high | disabled
    tool:                 str
    requiresApproval:     bool
    executionEnabled:     bool            # always False in v0
    reason:               str
    policyNotes:          Optional[str] = None
    sanitizedArgsSummary: str
    wouldLog:             bool
    logId:                Optional[str] = None   # id of the backend-local audit entry


class PermissionEvaluationLog(BaseModel):
    id:                   str
    timestamp:            str
    source:               Optional[str] = "gateway_eval"   # gateway_eval | gateway_execution
    tool:                 str
    requestedBy:          Optional[str] = None
    reason:               Optional[str] = None
    decision:             str
    riskLevel:            str
    allowed:              bool
    requiresApproval:     bool
    executionEnabled:     bool
    sanitizedArgsSummary: str
    policyNotes:          Optional[str] = None
    result:               str             # evaluated_only | success | failure
    # Execution-only fields (null for evaluation entries)
    exitCode:             Optional[int]   = None
    stdoutPreview:        Optional[str]   = None
    stderrPreview:        Optional[str]   = None
    durationMs:           Optional[float] = None


class PermissionEvaluationLogsResponse(BaseModel):
    logs: List[PermissionEvaluationLog] = []


class ToolExecutionResponse(BaseModel):
    tool:             str
    allowed:          bool
    decision:         str             # executed | denied | requires_approval | not_wired | disabled
    riskLevel:        str
    requiresApproval: bool
    executionEnabled: bool
    evaluationLogId:  str
    executionLogId:   Optional[str] = None
    ok:               bool
    exitCode:         Optional[int]   = None
    stdout:           Optional[str]   = None
    stderr:           Optional[str]   = None
    durationMs:       Optional[float] = None
    error:            Optional[str]   = None


# ── agent tool request (v0: evaluate-only; never executes) ─────────────────────

class CreateAgentToolRequestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool:           str
    args:           Optional[Dict[str, Any]] = None
    reason:         Optional[str] = None
    requestedBy:    Optional[str] = None
    conversationId: Optional[str] = None


class AgentToolRequestEvaluation(BaseModel):
    allowed:          bool
    decision:         str             # allowed | denied | requires_approval | not_wired | disabled
    riskLevel:        str
    requiresApproval: bool
    executionEnabled: bool
    reason:           str
    policyNotes:      Optional[str] = None
    logId:            str             # references the gateway evaluation log entry


class AgentToolRequestResponse(BaseModel):
    id:             str
    tool:           str
    argsSummary:    str
    reason:         Optional[str] = None
    requestedBy:    str
    conversationId: Optional[str] = None
    evaluation:     AgentToolRequestEvaluation
    createdAt:      str
    status:         str             # evaluated_only in v0


class AgentToolRequestListResponse(BaseModel):
    requests: List[AgentToolRequestResponse] = []


class AgentChatStructured(BaseModel):
    toolRequests: List[AgentToolRequestResponse] = []
    parseErrors:  List[str] = []


# Resolve the forward reference on AgentChatResponse now that AgentChatStructured exists.
AgentChatResponse.model_rebuild()


# ── chat / AI consolidation (v1: manual paste/import) ──────────────────────────

class ConsolidationDraftResponse(BaseModel):
    id:                     str
    sourceTool:             str   # chatgpt | claude | claude-code | opencode | other
    conversationTitle:      str
    domain:                 str   # project | course | business | research | personal | unknown
    entity:                 Optional[str] = None
    transcript:             str
    summary:                str
    decisions:              List[str] = []
    actionItems:            List[str] = []
    codeOrFilesReferenced:  List[str] = []
    status:                 str   # draft | saved
    proposedDestination:    str
    savedPath:              Optional[str] = None
    createdAt:              str
    updatedAt:              str


class ConsolidationDraftsResponse(BaseModel):
    drafts: List[ConsolidationDraftResponse] = []


class CreateConsolidationDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourceTool:             str
    conversationTitle:      str
    domain:                 str = "unknown"
    entity:                 Optional[str] = None
    transcript:             str
    summary:                Optional[str] = None
    decisions:              List[str] = []
    actionItems:            List[str] = []
    codeOrFilesReferenced:  List[str] = []


class UpdateConsolidationDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversationTitle:      Optional[str] = None
    domain:                 Optional[str] = None
    entity:                 Optional[str] = None
    summary:                Optional[str] = None
    decisions:              Optional[List[str]] = None
    actionItems:            Optional[List[str]] = None
    codeOrFilesReferenced:  Optional[List[str]] = None


class SaveConsolidationDraftResponse(BaseModel):
    ok:           bool
    draft:        ConsolidationDraftResponse
    relativePath: str
    absolutePath: str


# ── research (v1: manual capture) ──────────────────────────────────────────────

class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Optional[str] = None
    url:    Optional[str] = None
    notes:  Optional[str] = None


class ResearchDraftResponse(BaseModel):
    id:                     str
    title:                  str
    topic:                  Optional[str] = None
    domain:                 str   # project | course | business | personal | technical | market | general | unknown
    entity:                 Optional[str] = None
    researchQuestion:       Optional[str] = None
    summary:                str
    keyFindings:            List[str] = []
    sources:                List[ResearchSource] = []
    openQuestions:          List[str] = []
    recommendedNextActions: List[str] = []
    rawNotes:               str
    status:                 str   # draft | saved
    proposedDestination:    str
    savedPath:              Optional[str] = None
    createdAt:              str
    updatedAt:              str


class ResearchDraftsResponse(BaseModel):
    drafts: List[ResearchDraftResponse] = []


class CreateResearchDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title:                  str
    topic:                  Optional[str] = None
    domain:                 str = "unknown"
    entity:                 Optional[str] = None
    researchQuestion:       Optional[str] = None
    summary:                Optional[str] = None
    keyFindings:            List[str] = []
    sources:                List[ResearchSource] = []
    openQuestions:          List[str] = []
    recommendedNextActions: List[str] = []
    rawNotes:               str = ""


class UpdateResearchDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title:                  Optional[str] = None
    topic:                  Optional[str] = None
    domain:                 Optional[str] = None
    entity:                 Optional[str] = None
    researchQuestion:       Optional[str] = None
    summary:                Optional[str] = None
    keyFindings:            Optional[List[str]] = None
    sources:                Optional[List[ResearchSource]] = None
    openQuestions:          Optional[List[str]] = None
    recommendedNextActions: Optional[List[str]] = None
    rawNotes:               Optional[str] = None


class SaveResearchDraftResponse(BaseModel):
    ok:           bool
    draft:        ResearchDraftResponse
    relativePath: str
    absolutePath: str


# ── email intake (v1: manual paste/import) ─────────────────────────────────────

class EmailIntakeDraftResponse(BaseModel):
    id:                   str
    subject:              str
    sender:               Optional[str] = None
    receivedAt:           Optional[str] = None
    domain:               str   # course | business | personal | unknown
    entity:               Optional[str] = None
    summary:              str
    actionRequired:       Optional[str] = None
    dueDate:              Optional[str] = None
    confidence:           Optional[str] = None   # High | Medium | Low | null
    rawEmail:             str
    proposedTaskRows:     List[str] = []
    proposedCalendarRows: List[str] = []
    status:               str   # draft | saved
    proposedDestination:  str
    savedPath:            Optional[str] = None
    createdAt:            str
    updatedAt:            str


class EmailIntakeDraftsResponse(BaseModel):
    drafts: List[EmailIntakeDraftResponse] = []


class CreateEmailIntakeDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject:              str
    sender:               Optional[str] = None
    receivedAt:           Optional[str] = None
    domain:               str
    entity:               Optional[str] = None
    summary:              Optional[str] = None
    actionRequired:       Optional[str] = None
    dueDate:              Optional[str] = None
    confidence:           Optional[str] = None
    rawEmail:             str
    proposedTaskRows:     Optional[List[str]] = None
    proposedCalendarRows: Optional[List[str]] = None


class UpdateEmailIntakeDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject:              Optional[str] = None
    sender:               Optional[str] = None
    receivedAt:           Optional[str] = None
    domain:               Optional[str] = None
    entity:               Optional[str] = None
    summary:              Optional[str] = None
    actionRequired:       Optional[str] = None
    dueDate:              Optional[str] = None
    confidence:           Optional[str] = None
    proposedTaskRows:     Optional[List[str]] = None
    proposedCalendarRows: Optional[List[str]] = None


class SaveEmailIntakeDraftResponse(BaseModel):
    ok:           bool
    draft:        EmailIntakeDraftResponse
    relativePath: str
    absolutePath: str
