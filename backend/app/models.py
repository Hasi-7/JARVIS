from typing import List, Optional

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
