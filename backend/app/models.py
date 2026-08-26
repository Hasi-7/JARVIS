from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ── config ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    ok: bool
    service: str
    version: str


class ConfigResponse(BaseModel):
    vaultPath: str
    brainCmd: str
    # PRD §8.4/§43 reference path. Displayed only; no code path reads inside it.
    oldRepoPath: str = ""
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
    model_config = ConfigDict(extra="forbid")

    command: str
    # Optional, and only accepted for commands that declare an argument schema in
    # brain.py. Values are validated for control characters and shell
    # metacharacters, then passed as separate argv elements with shell=False.
    args: Optional[Dict[str, Optional[str]]] = None


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
    everydayModel: Optional[str] = None
    heavyModel: Optional[str] = None
    everydayAvailable: Optional[bool] = None
    heavyAvailable: Optional[bool] = None


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


class VaultEntityMetadata(BaseModel):
    """PRD §35.1 Work Item fields, read from the note's YAML frontmatter.

    All optional: a note without frontmatter — which is every note in the vault
    today — yields None for each, and the entity pages render as they did before.
    `frontmatterError` reports a note whose YAML could not be parsed, so one bad
    note degrades one card instead of failing the whole endpoint.
    """
    domain:    Optional[str] = None
    status:    Optional[str] = None
    repoPath:  Optional[str] = None
    githubUrl: Optional[str] = None
    demoUrl:   Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    frontmatterError: Optional[str] = None
    # Opaque mtime+size token used as a write precondition. Obsidian autosaves,
    # so a write must prove it read the version it is replacing.
    version:   Optional[str] = None


class VaultProjectItem(VaultEntityMetadata):
    id:           str
    name:         str
    wikiPath:     Optional[str] = None
    rawPath:      Optional[str] = None
    status:       str = "unknown"
    lastModified: Optional[str] = None
    preview:      Optional[str] = None


class VaultProjectsResponse(BaseModel):
    projects: List[VaultProjectItem]


class VaultCourseItem(VaultEntityMetadata):
    id:           str
    name:         str
    wikiPath:     Optional[str] = None
    rawPath:      Optional[str] = None
    lastModified: Optional[str] = None
    preview:      Optional[str] = None


class VaultCoursesResponse(BaseModel):
    courses: List[VaultCourseItem]


class VaultHackathonItem(VaultEntityMetadata):
    id:           str
    name:         str
    wikiPath:     Optional[str] = None
    rawPath:      Optional[str] = None
    lastModified: Optional[str] = None
    preview:      Optional[str] = None


class VaultHackathonsResponse(BaseModel):
    hackathons: List[VaultHackathonItem]


class VaultBusinessItem(VaultEntityMetadata):
    id:           str
    name:         str
    wikiPath:     Optional[str] = None
    rawPath:      Optional[str] = None
    lastModified: Optional[str] = None
    preview:      Optional[str] = None


class BusinessPipelineItem(BaseModel):
    id:          str
    name:        str
    status:      str = "unknown"
    description: str = ""
    created:     str = ""


class BusinessPipelineResponse(BaseModel):
    path:         str
    exists:       bool
    parseMode:    str
    items:        List[BusinessPipelineItem] = []
    lastModified: Optional[str] = None


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
    model_config = ConfigDict(extra="forbid")

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
    model_config = ConfigDict(extra="forbid")

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


class HandoffPackageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    itemId:         Optional[str] = None
    task:           Optional[str] = None
    target:         Optional[str] = None
    taskType:       Optional[str] = None
    repoPath:       Optional[str] = None
    contextFiles:   List[str] = []
    vaultContext:   List[str] = []
    expectedOutput: Optional[str] = None


class HandoffPackageResponse(BaseModel):
    """PRD §29's handoff package. Text only — nothing is launched."""
    taskType:            str
    recommendedAgent:    Optional[str] = None
    repoPath:            Optional[str] = None
    contextFiles:        List[str] = []
    vaultContext:        List[str] = []
    reasonForEscalation: str
    expectedOutput:      str
    approvalRequired:    bool = True
    prompt:              str


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


# ── proposal apply / reject (A1) ───────────────────────────────────────────────

class ApplyProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str


class ApplyBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: List[str]


class ApplyProposalResult(BaseModel):
    id:             str
    ok:             bool
    status:         str                    # applied | skipped | error
    message:        str
    targetPath:     Optional[str] = None
    alreadyApplied: bool = False


class ApplyBatchResponse(BaseModel):
    results:      List[ApplyProposalResult] = []
    appliedCount: int = 0
    failedCount:  int = 0


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


# ── OpenClaw / NemoClaw runtime status (v0: read-only readiness) ────────────────

class RuntimeStatusItem(BaseModel):
    id:          str                    # openclaw | nemoclaw_openshell | browser_harness | computer_use | mcp_gateway
    name:        str
    status:      str                    # available | unavailable | not_configured | disabled | planned | error
    available:   bool                   # verified reachable now (always False in v0 — no health check)
    enabled:     bool                   # effectively active now (always False in v0)
    requiredFor: List[str] = []         # what this runtime would unlock later
    dependsOn:   List[str] = []         # runtime ids this depends on
    blocks:      List[str] = []         # human-readable reasons it is currently blocked
    configured:  Dict[str, bool] = {}   # which config knobs are present (values never stored)
    notes:       Optional[str] = None


class RuntimeStatusResponse(BaseModel):
    items: List[RuntimeStatusItem] = []


# ── NemoClaw/OpenShell health probe (v0: explicit, opt-in reachability check) ───

class NemoclawProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeoutMs: Optional[int] = None     # clamped to [1, 3000] server-side


class NemoclawProbeDetails(BaseModel):
    urlConfigured:        bool
    policyPathConfigured: bool
    enabledFlag:          bool = False
    remoteProbeAllowed:   bool = False
    hostRedacted:         Optional[str] = None   # scheme://host[:port] only — never userinfo/path/query


class NemoclawProbeResponse(BaseModel):
    id:         str = "nemoclaw_openshell"
    checkedAt:  str
    configured: bool
    reachable:  bool
    status:     str               # reachable | unavailable | not_configured | error
    durationMs: int
    message:    str
    details:    NemoclawProbeDetails


class NemoclawLastProbeResponse(BaseModel):
    lastProbe: Optional[NemoclawProbeResponse] = None


# ── NemoClaw/OpenShell policy inspection (v0: read-only, no enforcement) ─────────

class NemoclawPolicySummary(BaseModel):
    declaredModes:      List[str] = []
    networkPolicy:      Optional[str] = None
    filesystemScopes:   List[str] = []
    browserAllowed:     Optional[bool] = None    # None = unknown (never implied allowed)
    computerUseAllowed: Optional[bool] = None
    mcpAllowed:         Optional[bool] = None
    credentialAccess:   str = "unknown"
    unknownKeys:        List[str] = []


class NemoclawPolicyResponse(BaseModel):
    id:                str = "nemoclaw_openshell"
    configured:        bool
    pathConfigured:    bool
    pathExists:        bool
    readable:          bool
    valid:             bool
    status:            str            # not_configured | missing | unreadable | invalid | loaded | error
    message:           str
    policyPathDisplay: Optional[str] = None
    format:            Optional[str] = None       # json | yaml | unknown
    summary:           Optional[NemoclawPolicySummary] = None
    warnings:          List[str] = []
    errors:            List[str] = []


# ── guardrail readiness (v0: read-only correlation, no enforcement/execution) ───

class GuardrailReadinessComponents(BaseModel):
    runtimeStatus: str    # nemoclaw runtime item status (available|unavailable|not_configured|disabled|...)
    lastProbe:     str    # cached probe status (reachable|unavailable|not_configured|error) or not_run
    policy:        str    # policy inspection status (loaded|not_configured|missing|unreadable|invalid|error)
    modePolicy:    str    # available | unavailable


class GuardrailCapabilityUnlocks(BaseModel):
    # Every unlock is False in every state — readiness enables nothing.
    openclawBridge: bool = False
    browserHarness: bool = False
    computerUse:    bool = False
    mcpGateway:     bool = False
    gmail:          bool = False


class GuardrailReadinessResponse(BaseModel):
    id:                str = "nemoclaw_openshell_guardrail"
    status:            str            # not_ready | partially_ready | ready_for_bridge_design | error
    ready:             bool           # true ONLY for ready_for_bridge_design (never "ready to execute")
    checkedAt:         str
    summary:           str
    components:        GuardrailReadinessComponents
    blockers:          List[str] = []
    warnings:          List[str] = []
    nextSteps:         List[str] = []
    capabilityUnlocks: GuardrailCapabilityUnlocks
    notes:             str


# ── runtime bridge contract (v0: dry-run validator only, no execution) ──────────

class RuntimeBridgeAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind:   str                                   # e.g. browser.open (see runtime_bridge_contract action kinds)
    target: Optional[str] = None                  # optional URL / selector / path (untrusted; never fetched)
    args:   Optional[Dict[str, Any]] = None       # untrusted; summarized only, never executed


class RuntimeBridgeValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source:          str = "openclaw"             # openclaw | nemoclaw | ... (echoed only)
    mode:            Optional[str] = None          # normalized via agent mode policy
    requestedAction: RuntimeBridgeAction
    reason:          Optional[str] = None
    conversationId:  Optional[str] = None


class RuntimeBridgeValidationChecks(BaseModel):
    schemaValid:                   bool
    modeAllowsEvaluation:          bool
    guardrailReadyForBridgeDesign: bool
    runtimeBridgeImplemented:      bool = False    # always False — the bridge is not implemented
    permissionGatewayDecision:     str             # gateway dry-run decision, or "n/a"


class RuntimeBridgeValidationResponse(BaseModel):
    id:               str
    status:           str          # blocked_by_mode | blocked | validated | error
    allowed:          bool         # always False — a valid request is never an approval to run
    requiresApproval: bool
    executionEnabled: bool         # always False — nothing executes here
    mode:             str
    source:           str
    actionKind:       str
    riskLevel:        str          # low | medium | high
    decision:         str
    message:          str
    checks:           RuntimeBridgeValidationChecks
    blockers:         List[str] = []
    warnings:         List[str] = []
    logId:            Optional[str] = None
    createdAt:        str


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
    source:               Optional[Literal[
        "gateway_eval", "gateway_execution", "runtime_bridge_validation",
        "approval_transition",
    ]] = "gateway_eval"
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
    approvalId:           Optional[str]   = None
    requestId:            Optional[str]   = None
    approvedBy:           Optional[str]   = None
    approvedAt:           Optional[str]   = None


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
    # Agent Mode Enforcement v0 — the selected mode gates whether the request is
    # evaluated at all. Optional; missing/unknown normalizes to the safest mode.
    mode:           Optional[str] = None


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
    mode:           str = "locked"
    approvalId:     Optional[str] = None
    approvalStatus: Optional[Literal[
        "pending_approval", "approved", "executing", "executed", "failed", "rejected",
    ]] = None
    evaluation:     AgentToolRequestEvaluation
    createdAt:      str
    status:         Literal[
        "evaluated_only", "pending_approval", "approved", "executing",
        "executed", "failed", "rejected",
    ]


class AgentToolRequestListResponse(BaseModel):
    requests: List[AgentToolRequestResponse] = []


class AgentChatStructured(BaseModel):
    toolRequests: List[AgentToolRequestResponse] = []
    parseErrors:  List[str] = []
    # Agent Mode Enforcement v0 — the resolved mode and whether tool requests were
    # blocked by it. When blockedByMode is True, toolRequests is empty (nothing was
    # evaluated or stored) and `message` explains why.
    mode:          Optional[str] = None
    blockedByMode: bool = False
    message:       Optional[str] = None


# Resolve the forward reference on AgentChatResponse now that AgentChatStructured exists.
AgentChatResponse.model_rebuild()


# ── agent modes (v0: backend-enforced policy) ──────────────────────────────────

class AgentModePolicy(BaseModel):
    id:                       str
    label:                    str
    available:                bool
    canEvaluateToolRequests:  bool
    canOfferReviewHandoff:    bool
    notes:                    Optional[str] = None


class AgentModesResponse(BaseModel):
    modes: List[AgentModePolicy] = []


class AgentModeBlockedResponse(BaseModel):
    """Returned when a tool request is blocked because the current mode disallows it."""
    status:  str = "blocked_by_mode"
    mode:    str
    message: str


# ── gated local tool approvals (A3) ───────────────────────────────────────────

class ToolApprovalExecutionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok:         bool
    # Must stay in sync with tool_approvals._execution_summary. It emitted
    # sandboxed_search / sandboxed_page_read / calendar_event_created long before
    # this Literal listed them, so those executions would have failed at response
    # serialization even once they became queueable.
    resultType: Literal[
        "brain_command", "task_created", "calendar_candidate_created",
        "calendar_event_created", "sandboxed_search", "sandboxed_page_read",
        "computer_session_started", "entity_metadata_updated",
    ]
    message:    str = Field(max_length=300)
    path:       Optional[str] = Field(default=None, max_length=500)
    id:         Optional[str] = Field(default=None, max_length=100)


class ToolApprovalBrainReviewFields(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolApprovalTaskReviewFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title:    str = Field(max_length=300)
    status:   Literal["todo", "in progress", "blocked", "done"]
    area:     Optional[str] = Field(default=None, max_length=500)
    priority: Optional[Literal["low", "medium", "high"]] = None
    due:      Optional[str] = Field(default=None, max_length=10)
    source:   Optional[str] = Field(default=None, max_length=500)


class ToolApprovalCalendarReviewFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date:     str = Field(max_length=10)
    time:     Optional[str] = Field(default=None, max_length=5)
    duration: Optional[str] = Field(default=None, max_length=50)
    title:    str = Field(max_length=300)
    reason:   Optional[str] = Field(default=None, max_length=500)
    source:   Optional[str] = Field(default=None, max_length=500)
    approved: Literal["No"] = "No"


class ToolApprovalCalendarEventReviewFields(BaseModel):
    """The ONLY external write. Distinct from the candidate model above: no
    `source`/`approved`, and it carries location/timeZone, which shape a real event."""
    model_config = ConfigDict(extra="forbid")
    date:     str = Field(max_length=10)
    time:     Optional[str] = Field(default=None, max_length=5)
    duration: Optional[str] = Field(default=None, max_length=50)
    title:    str = Field(max_length=300)
    reason:   Optional[str] = Field(default=None, max_length=500)
    location: Optional[str] = Field(default=None, max_length=500)
    timeZone: Optional[str] = Field(default=None, max_length=60)


class ToolApprovalBrowserSearchReviewFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sessionId: str = Field(max_length=64)
    query:     str = Field(max_length=500)
    limit:     Optional[int] = None


class ToolApprovalBrowserPageReviewFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sessionId: str = Field(max_length=64)
    url:       str = Field(max_length=2000)


class ToolApprovalEntityUpdateReviewFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entityType: str
    wikiPath:   str = Field(max_length=400)
    status:     Optional[str] = None
    domain:     Optional[str] = None
    repoPath:   Optional[str] = None
    githubUrl:  Optional[str] = None
    demoUrl:    Optional[str] = None


class ToolApprovalComputerSessionReviewFields(BaseModel):
    """What the operator is authorising: real input, on these windows, for this long."""
    model_config = ConfigDict(extra="forbid")
    task:           str = Field(max_length=300)
    allowedWindows: List[str] = Field(max_length=20)
    budgetSeconds:  Optional[int] = None


class ToolApprovalResponse(BaseModel):
    id:                     str
    requestId:              str
    status:                 Literal[
        "pending_approval", "approved", "executing", "executed", "failed", "rejected",
    ]
    tool:                   str
    mode:                   str
    risk:                   str
    argsSummary:            str = Field(max_length=240)
    # Each member sets extra="forbid", which is what keeps them mutually
    # exclusive: _review_fields always emits every key for its tool, so the
    # candidate ({source, approved}) and event ({location, timeZone}) shapes
    # cannot be confused for one another.
    reviewFields:           Union[
        ToolApprovalTaskReviewFields,
        ToolApprovalCalendarReviewFields,
        ToolApprovalCalendarEventReviewFields,
        ToolApprovalBrowserSearchReviewFields,
        ToolApprovalBrowserPageReviewFields,
        ToolApprovalComputerSessionReviewFields,
        ToolApprovalEntityUpdateReviewFields,
        ToolApprovalBrainReviewFields,
    ]
    reason:                 Optional[str] = Field(default=None, max_length=300)
    requestedBy:            str
    approvedBy:             Optional[str] = None
    rejectedBy:             Optional[str] = None
    createdAt:              str
    approvedAt:             Optional[str] = None
    rejectedAt:             Optional[str] = None
    executionStartedAt:     Optional[str] = None
    executedAt:             Optional[str] = None
    failedAt:               Optional[str] = None
    evaluationLogId:        Optional[str] = None
    executionLogId:         Optional[str] = None
    transitionLogId:        Optional[str] = None
    result:                 Optional[ToolApprovalExecutionSummary] = None
    error:                  Optional[str] = Field(default=None, max_length=300)
    auditWarning:           Optional[str] = Field(default=None, max_length=200)


class ToolApprovalListResponse(BaseModel):
    approvals: List[ToolApprovalResponse] = []


class ApproveToolApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approvedBy: Optional[str] = Field(default=None, max_length=80)


class RejectToolApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rejectedBy: Optional[str] = Field(default=None, max_length=80)
    reason: Optional[str] = Field(default=None, max_length=300)


class ExecuteToolApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── capture AI assist (A2: preview only) ──────────────────────────────────────

AssistString = Annotated[str, Field(max_length=500)]


class CaptureAssistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modelTier: Literal["everyday", "heavy"]


class ConsolidationAssistPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversationTitle: str = Field(min_length=1, max_length=300)
    domain: Literal["project", "course", "business", "research", "personal", "unknown"]
    entity: Optional[str] = Field(max_length=200)
    summary: str = Field(max_length=4000)
    decisions: List[AssistString] = Field(max_length=20)
    actionItems: List[AssistString] = Field(max_length=20)
    codeOrFilesReferenced: List[AssistString] = Field(max_length=20)


class ResearchAssistPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    topic: Optional[str] = Field(max_length=200)
    domain: Literal[
        "project", "course", "business", "personal",
        "technical", "market", "general", "unknown",
    ]
    entity: Optional[str] = Field(max_length=200)
    researchQuestion: Optional[str] = Field(max_length=1000)
    summary: str = Field(max_length=4000)
    keyFindings: List[AssistString] = Field(max_length=20)
    openQuestions: List[AssistString] = Field(max_length=20)
    recommendedNextActions: List[AssistString] = Field(max_length=20)


class EmailIntakeAssistPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str = Field(min_length=1, max_length=500)
    sender: Optional[str] = Field(max_length=300)
    receivedAt: Optional[str] = Field(max_length=100)
    domain: Literal["course", "business", "personal", "unknown"]
    entity: Optional[str] = Field(max_length=200)
    summary: str = Field(max_length=4000)
    actionRequired: Optional[str] = Field(max_length=1000)
    dueDate: Optional[str] = Field(max_length=100)
    confidence: Optional[Literal["High", "Medium", "Low"]]
    proposedTaskRows: List[AssistString] = Field(max_length=20)
    proposedCalendarRows: List[AssistString] = Field(max_length=20)


class ConsolidationAssistResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modelTier: Literal["everyday", "heavy"]
    model: str
    durationMs: float
    draftUpdatedAt: str
    suggestions: ConsolidationAssistPreview


class ResearchAssistResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modelTier: Literal["everyday", "heavy"]
    model: str
    durationMs: float
    draftUpdatedAt: str
    suggestions: ResearchAssistPreview


class EmailIntakeAssistResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    modelTier: Literal["everyday", "heavy"]
    model: str
    durationMs: float
    draftUpdatedAt: str
    suggestions: EmailIntakeAssistPreview


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


# ══════════════════════════════════════════════════════════════════════════════
# Gmail read intake (B1) — READ-ONLY
# ══════════════════════════════════════════════════════════════════════════════

class GmailStatusResponse(BaseModel):
    configured:   bool          # OAuth client + token both present on disk
    clientConfigured: bool
    tokenPresent: bool
    scopes:       List[str] = []
    readsEnabled: bool          # gateway would allow a read right now
    message:      str


class GmailSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query:      str
    maxResults: Optional[int] = None


class GmailThreadSummary(BaseModel):
    threadId:  str
    messageId: Optional[str] = None
    subject:   str
    sender:    Optional[str] = None
    to:        Optional[str] = None
    date:      Optional[str] = None
    snippet:   str = ""


class GmailSearchResponse(BaseModel):
    query:    str
    count:    int
    threads:  List[GmailThreadSummary] = []
    decision: str
    logId:    Optional[str] = None
    warnings: List[str] = []


class GmailMessageResponse(BaseModel):
    messageId:     str
    threadId:      Optional[str] = None
    subject:       str
    sender:        Optional[str] = None
    to:            Optional[str] = None
    date:          Optional[str] = None
    snippet:       str = ""
    body:          str = ""
    bodyTruncated: bool = False
    labelIds:      List[str] = []
    decision:      str
    logId:         Optional[str] = None
    warnings:      List[str] = []


class GmailImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messageId: str
    domain:    Optional[str] = None   # course | business | personal | unknown
    entity:    Optional[str] = None


class GmailImportResponse(BaseModel):
    ok:     bool
    draft:  EmailIntakeDraftResponse
    logId:  Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# Google Calendar read + reconciliation (B2) — READ-ONLY
# ══════════════════════════════════════════════════════════════════════════════
# There is deliberately no create/update/delete event model here. Event creation
# is Phase D2 and requires an additional scope plus explicit re-consent.

class CalendarEvent(BaseModel):
    eventId:  str
    title:    str
    start:    Optional[str] = None
    end:      Optional[str] = None
    allDay:   bool = False
    status:   str = ""
    htmlLink: Optional[str] = None


class CalendarEventsResponse(BaseModel):
    events:   List[CalendarEvent] = []
    count:    int
    timeMin:  Optional[str] = None
    timeMax:  Optional[str] = None
    decision: str
    logId:    Optional[str] = None
    warnings: List[str] = []


class CalendarReconcileCounts(BaseModel):
    matched:     int
    conflicting: int
    missing:     int
    unparseable: int
    events:      int


class CalendarReconcileItem(BaseModel):
    candidateId: Optional[str] = None
    title:       str = ""
    date:        Optional[str] = None
    time:        Optional[str] = None
    duration:    Optional[str] = None
    eventId:     Optional[str] = None
    eventTitle:  Optional[str] = None
    eventStart:  Optional[str] = None
    htmlLink:    Optional[str] = None
    note:        Optional[str] = None


class CalendarReconcileResponse(BaseModel):
    counts:      CalendarReconcileCounts
    matched:     List[CalendarReconcileItem] = []
    conflicting: List[CalendarReconcileItem] = []
    missing:     List[CalendarReconcileItem] = []
    unparseable: List[CalendarReconcileItem] = []
    notes:       List[str] = []
    decision:    str
    logId:       Optional[str] = None


class CalendarStatusResponse(BaseModel):
    configured:   bool
    tokenPresent: bool
    scopes:       List[str] = []
    readsEnabled: bool
    writesEnabled: bool = False   # permanently False until D2
    message:      str


# ══════════════════════════════════════════════════════════════════════════════
# Local voice transcription (D1) — ON-DEVICE ONLY
# ══════════════════════════════════════════════════════════════════════════════

class VoiceStatusResponse(BaseModel):
    available:       bool
    model:           str
    device:          str
    computeType:     str
    localFilesOnly:  bool
    maxUploadBytes:  int
    maxAudioSeconds: int
    message:         str


class TranscriptSegment(BaseModel):
    start: float
    end:   float
    text:  str


class TranscribeResponse(BaseModel):
    text:         str
    language:     Optional[str] = None
    audioSeconds: float = 0.0
    durationMs:   int = 0
    segments:     List[TranscriptSegment] = []
    warnings:     List[str] = []


# ══════════════════════════════════════════════════════════════════════════════
# Time-boxed browser research (C1) — GUARDRAILED
# ══════════════════════════════════════════════════════════════════════════════

class ResearchCapture(BaseModel):
    url:        str
    title:      str = ""
    timestamp:  str
    snippet:    str = ""
    textChars:  int = 0
    httpStatus: Optional[int] = None


class ResearchSessionSummary(BaseModel):
    id:               Optional[str] = None
    topic:            Optional[str] = None
    status:           Optional[str] = None
    budgetSeconds:    Optional[int] = None
    remainingSeconds: float = 0.0
    captureCount:     int = 0
    errorCount:       int = 0
    allowedDomains:   List[str] = []
    startedAt:        Optional[str] = None
    endedAt:          Optional[str] = None


class ResearchSessionResponse(BaseModel):
    session:  ResearchSessionSummary
    captures: List[ResearchCapture] = []
    warnings: List[str] = []


class ResearchSessionsResponse(BaseModel):
    sessions: List[ResearchSessionSummary] = []


class StartResearchSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic:          str
    allowedDomains: List[str]
    budgetSeconds:  Optional[int] = None


class OpenResearchPageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str


class ResearchDraftPayloadResponse(BaseModel):
    title:     str
    topic:     str
    sources:   List[Dict[str, Any]] = []
    rawNotes:  str = ""
    warnings:  List[str] = []


class ChatCapturePayloadResponse(BaseModel):
    sourceTool:        str
    conversationTitle: str
    domain:            str
    entity:            Optional[str] = None
    transcript:        str
    turnCount:         int = 0
    sourceUrl:         str = ""
    capturedAt:        Optional[str] = None
    warnings:          List[str] = []


# ══════════════════════════════════════════════════════════════════════════════
# Local vault semantic search (D3) — READ-ONLY, ON-DEVICE
# ══════════════════════════════════════════════════════════════════════════════

class VaultSearchHit(BaseModel):
    path:    str
    heading: str = ""
    score:   float = 0.0
    snippet: str = ""


class VaultSearchResponse(BaseModel):
    query:    str
    results:  List[VaultSearchHit] = []
    count:    int = 0
    degraded: bool = False
    mode:     str = "lexical"
    builtAt:  Optional[str] = None
    warnings: List[str] = []


class VaultIndexStatusResponse(BaseModel):
    built:     bool = False
    builtAt:   Optional[str] = None
    chunks:    int = 0
    embedded:  bool = False
    degraded:  bool = True
    vaultPath: Optional[str] = None


class BuildVaultIndexResponse(BaseModel):
    files:    int = 0
    chunks:   int = 0
    embedded: bool = False
    degraded: bool = True
    builtAt:  Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# GitHub + Drive read-only integrations (D3)
# ══════════════════════════════════════════════════════════════════════════════

class GitHubStatusResponse(BaseModel):
    configured: bool
    readOnly:   bool = True
    message:    str


class GitHubRepo(BaseModel):
    fullName:    str
    description: str = ""
    private:     bool = False
    language:    Optional[str] = None
    pushedAt:    Optional[str] = None
    htmlUrl:     Optional[str] = None
    openIssues:  int = 0


class GitHubReposResponse(BaseModel):
    repos:    List[GitHubRepo] = []
    logId:    Optional[str] = None
    warnings: List[str] = []


class GitHubCommit(BaseModel):
    sha:     str
    message: str = ""
    author:  Optional[str] = None
    date:    Optional[str] = None
    htmlUrl: Optional[str] = None


class GitHubCommitsResponse(BaseModel):
    repo:     str
    commits:  List[GitHubCommit] = []
    logId:    Optional[str] = None
    warnings: List[str] = []


class GitHubIssue(BaseModel):
    number:        int
    title:         str = ""
    state:         str = ""
    isPullRequest: bool = False
    updatedAt:     Optional[str] = None
    htmlUrl:       Optional[str] = None


class GitHubIssuesResponse(BaseModel):
    repo:     str
    issues:   List[GitHubIssue] = []
    logId:    Optional[str] = None
    warnings: List[str] = []


class DriveFile(BaseModel):
    fileId:       str
    name:         str = ""
    mimeType:     str = ""
    modifiedTime: Optional[str] = None
    webViewLink:  Optional[str] = None
    readable:     bool = False


class DriveFilesResponse(BaseModel):
    files:    List[DriveFile] = []
    logId:    Optional[str] = None
    warnings: List[str] = []


class DriveDocumentResponse(BaseModel):
    fileId:      str
    name:        str = ""
    mimeType:    str = ""
    webViewLink: Optional[str] = None
    text:        str = ""
    truncated:   bool = False
    logId:       Optional[str] = None
    warnings:    List[str] = []


# ══════════════════════════════════════════════════════════════════════════════
# Vault graph / Graphify viewer (D3d) — READ-ONLY
# ══════════════════════════════════════════════════════════════════════════════

class GraphNode(BaseModel):
    id:         str
    label:      str = ""
    path:       Optional[str] = None
    folder:     str = ""
    exists:     bool = True
    outDegree:  int = 0
    inDegree:   int = 0
    fileCount:  int = 0


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphStats(BaseModel):
    files:     int = 0
    nodes:     int = 0
    edges:     int = 0
    dangling:  int = 0
    orphans:   int = 0
    collapsed: int = 0
    truncated: bool = False


class VaultGraphResponse(BaseModel):
    nodes:    List[GraphNode] = []
    edges:    List[GraphEdge] = []
    stats:    GraphStats
    source:   str
    warnings: List[str] = []


class SearchResultItem(BaseModel):
    url:           str
    title:         str = ""
    openable:      bool = False
    blockedReason: Optional[str] = None


class ResearchSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    limit: Optional[int] = None


class ResearchSearchResponse(BaseModel):
    query:         str
    results:       List[SearchResultItem] = []
    count:         int = 0
    openableCount: int = 0
    warnings:      List[str] = []


# ══════════════════════════════════════════════════════════════════════════════
# Canvas / Quercus intake (MVP v10) — READ-ONLY
# ══════════════════════════════════════════════════════════════════════════════

class QuercusStatusResponse(BaseModel):
    configured: bool
    host:       str
    readOnly:   bool = True
    message:    str


class QuercusCourse(BaseModel):
    courseId:   str
    name:       str = ""
    courseCode: str = ""
    term:       Optional[str] = None


class QuercusCoursesResponse(BaseModel):
    courses:  List[QuercusCourse] = []
    logId:    Optional[str] = None
    warnings: List[str] = []


class QuercusAssignment(BaseModel):
    assignmentId:   str
    courseId:       str
    name:           str = ""
    dueAt:          Optional[str] = None
    pointsPossible: Optional[float] = None
    htmlUrl:        Optional[str] = None
    description:    str = ""


class QuercusAssignmentsResponse(BaseModel):
    courseId:    str
    assignments: List[QuercusAssignment] = []
    logId:       Optional[str] = None
    warnings:    List[str] = []


class QuercusAnnouncement(BaseModel):
    announcementId: str
    courseId:       str
    title:          str = ""
    postedAt:       Optional[str] = None
    htmlUrl:        Optional[str] = None
    message:        str = ""


class QuercusAnnouncementsResponse(BaseModel):
    courseId:      str
    announcements: List[QuercusAnnouncement] = []
    logId:         Optional[str] = None
    warnings:      List[str] = []


# ══════════════════════════════════════════════════════════════════════════════
# Computer-use harness (MVP v7) — PRIVILEGED, FULL DESKTOP
# ══════════════════════════════════════════════════════════════════════════════

class ComputerUseSessionSummary(BaseModel):
    id:               Optional[str] = None
    task:             Optional[str] = None
    status:           Optional[str] = None
    budgetSeconds:    Optional[int] = None
    remainingSeconds: float = 0.0
    allowedWindows:   List[str] = []
    actionCount:      int = 0
    refusedCount:     int = 0
    startedAt:        Optional[str] = None
    endedAt:          Optional[str] = None


class ComputerUseStatusResponse(BaseModel):
    enabled: bool
    active:  Optional[ComputerUseSessionSummary] = None
    message: str


class StartComputerUseSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task:           str
    allowedWindows: List[str]
    budgetSeconds:  Optional[int] = None


class ComputerUseSessionResponse(BaseModel):
    session:  ComputerUseSessionSummary
    warnings: List[str] = []


class ComputerUseObserveResponse(BaseModel):
    window:           str = ""
    width:            int = 0
    height:           int = 0
    screenshotBase64: str = ""
    warnings:         List[str] = []


class ComputerUseClickRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x:           int
    y:           int
    confirmRisk: Optional[str] = None


class ComputerUseTypeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text:        str
    confirmRisk: Optional[str] = None


class ComputerUseActionResponse(BaseModel):
    ok:       bool
    window:   str = ""
    x:        Optional[int] = None
    y:        Optional[int] = None
    chars:    Optional[int] = None
    warnings: List[str] = []
