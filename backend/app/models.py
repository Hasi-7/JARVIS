from typing import List, Optional

from pydantic import BaseModel


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
