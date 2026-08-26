const BASE = 'http://localhost:8000';

// ── config ────────────────────────────────────────────────────────────────────

export interface BackendHealth {
  ok: boolean;
  service: string;
  version: string;
}

export interface BackendConfig {
  vaultPath: string;
  brainCmd: string;
  backendReady: boolean;
  brainCmdExists?: boolean;
  vaultPathExists?: boolean;
  configSource?: 'env' | 'file' | 'defaults' | 'runtime';
  configPersisted?: boolean;
  configWarning?: string | null;
}

export interface ConfigUpdate {
  vaultPath: string;
  brainCmd: string;
}

// ── brain commands ────────────────────────────────────────────────────────────

export interface BrainRunResult {
  command: string;
  ok: boolean;
  exitCode: number;
  stdout: string;
  stderr: string;
  durationMs: number;
}

// ── entity creation ───────────────────────────────────────────────────────────

export interface CreateProjectRequest {
  name: string;
}

export interface CreateCourseRequest {
  code: string;
  name?: string | null;
}

export interface CreateHackathonRequest {
  name: string;
}

export interface CreateBusinessRequest {
  name: string;
  description?: string | null;
}

export interface EntityCreateResponse {
  ok: boolean;
  entityType: 'project' | 'course' | 'hackathon' | 'business';
  name: string;
  command: string | null;
  stdout: string | null;
  stderr: string | null;
  paths: {
    wikiPath: string | null;
    rawPath: string | null;
  };
}

// ── intake / staging ──────────────────────────────────────────────────────────

export interface StagedFileInfo {
  id: string;
  originalName: string;
  storedName: string;
  sizeBytes: number;
  contentType: string | null;
  uploadedAt: string;
  status: string;
}

export interface UploadResponse {
  uploaded: StagedFileInfo[];
}

export interface StagedFilesResponse {
  files: StagedFileInfo[];
}

export interface DeleteStagedResponse {
  ok: boolean;
  deletedId: string;
}

// ── classification proposals ──────────────────────────────────────────────────

export interface ClassificationProposal {
  fileId: string;
  domain: string;
  entity: string;
  sourceType: string;
  proposedDestination: string;
  confidence: 'High' | 'Medium' | 'Low';
  needsReview: boolean;
  reason: string;
  status: 'proposed' | 'edited' | 'approved' | 'skipped' | 'routed' | 'archived';
  routedAt?: string;
  routedPath?: string;
  routedName?: string;
  archivedAt?: string;
  archivePath?: string;
  archiveName?: string;
  // Populated after AI classification
  classifiedBy?: 'heuristic' | 'local-ai';
  aiModel?: string;
  aiClassifiedAt?: string;
}

export interface ProposalsResponse {
  proposals: ClassificationProposal[];
}

export interface ProposalUpdatePayload {
  domain?: string;
  entity?: string;
  sourceType?: string;
  proposedDestination?: string;
  confidence?: string;
  needsReview?: boolean;
}

export interface BatchSkippedItem {
  fileId: string;
  reason: string;
}

export interface BatchApproveResponse {
  approved: ClassificationProposal[];
  skipped: BatchSkippedItem[];
}

export interface BatchAiSkippedItem {
  fileId: string;
  reason: string;
}

export interface BatchAiClassifyResponse {
  classified: ClassificationProposal[];
  skipped: BatchAiSkippedItem[];
}

export interface RouteInfo {
  copied: boolean;
  relativePath: string;
  absolutePath: string;
}

export interface RouteResponse {
  ok: boolean;
  proposal: ClassificationProposal;
  route: RouteInfo;
}

export interface ArchiveInfo {
  archiveName: string;
  archivePath: string;
  archivedAt: string;
}

export interface ArchiveResponse {
  ok: boolean;
  fileId: string;
  archived: ArchiveInfo;
  proposal: ClassificationProposal;
}

export interface ArchivedFilesResponse {
  count: number;
  archived: ClassificationProposal[];
}

// ── local agent ──────────────────────────────────────────────────────────────

export interface AgentStatus {
  ok: boolean;
  provider: string;
  baseUrl: string;
  model: string;
  everydayModel?: string | null;
  heavyModel?: string | null;
  everydayAvailable?: boolean | null;
  heavyAvailable?: boolean | null;
  available: boolean;
  message: string;
}

export interface AgentChatRequest {
  message: string;
  mode?: string;
  conversationId?: string | null;
  context?: {
    screen?: string;
    vaultPath?: string | null;
  };
}

export interface AgentChatResponse {
  ok: boolean;
  provider: string;
  model: string;
  message: string;
  durationMs: number;
  conversationId: string;
  contextWindowMessages?: number;
  contextMessagesUsed?: number;
  structured?: AgentStructuredOutput | null;
}

// Structured tool requests parsed from an assistant reply (evaluate-only).
export type AgentStructuredParseError = string;
export type AgentStructuredToolRequestResult = AgentToolRequestResponse;

export interface AgentStructuredOutput {
  toolRequests: AgentStructuredToolRequestResult[];
  parseErrors:  AgentStructuredParseError[];
  // Agent Mode Enforcement v0 — the resolved mode and whether tool requests were
  // blocked by it. When blockedByMode is true, toolRequests is empty (nothing was
  // evaluated or stored) and `message` explains why.
  mode?:          string | null;
  blockedByMode?: boolean;
  message?:       string | null;
}

// ── agent modes (v0: backend-enforced policy) ──────────────────────────────────

export interface AgentModePolicy {
  id:                      string;
  label:                   string;
  available:               boolean;
  canEvaluateToolRequests: boolean;
  canOfferReviewHandoff:   boolean;
  notes:                   string | null;
}

export interface AgentModesResponse {
  modes: AgentModePolicy[];
}

// Returned when a tool request is blocked because the current mode disallows it.
export interface AgentModeBlockedResponse {
  status:  'blocked_by_mode';
  mode:    string;
  message: string;
}

// ── conversations ─────────────────────────────────────────────────────────────

export interface ConversationSummary {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

export interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  createdAt: string;
  provider: string | null;
  model: string | null;
  durationMs: number | null;
}

export interface ConversationDetail {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ConversationMessage[];
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
}

export interface DeleteConversationResponse {
  ok: boolean;
  deletedId: string;
}

// ── streaming agent ──────────────────────────────────────────────────────────

export interface StreamMeta {
  conversationId: string;
  provider: string;
  model: string;
  contextWindowMessages?: number;
  contextMessagesUsed?: number;
}

export interface StreamDone {
  ok: boolean;
  durationMs: number;
  /** True when the turn was stopped by the user rather than finishing. */
  aborted?: boolean;
}

export interface StreamError {
  message: string;
}

export interface StreamHandlers {
  onMeta:  (meta:  StreamMeta)  => void;
  onToken: (text:  string)      => void;
  onDone:  (done:  StreamDone)  => void;
  onError: (error: StreamError) => void;
  // Optional: emitted once after streaming completes if the reply contained
  // structured tool requests (evaluate-only — nothing executed).
  onStructured?: (structured: AgentStructuredOutput) => void;
}

// ── vault (read-only) ────────────────────────────────────────────────────────

export interface VaultFolders {
  raw?: boolean;
  wiki?: boolean;
  ops?: boolean;
  schema?: boolean;
  templates?: boolean;
}

export interface VaultSummary {
  ok: boolean;
  vaultPath: string;
  exists: boolean;
  folders: VaultFolders;
}

export interface VaultEntityMetadata {
  domain:    string | null;
  status:    string | null;
  repoPath:  string | null;
  githubUrl: string | null;
  demoUrl:   string | null;
  createdAt: string | null;
  updatedAt: string | null;
  /** Set when this note's YAML could not be parsed. Degrades one card only. */
  frontmatterError: string | null;
  /** Opaque mtime+size token; send it back as the write precondition. */
  version:   string | null;
}

export interface BusinessPipelineItem {
  id: string; name: string; status: string; description: string; created: string;
}

export interface BusinessPipelineResponse {
  path: string; exists: boolean; parseMode: string;
  items: BusinessPipelineItem[]; lastModified: string | null;
}

export interface VaultProject extends VaultEntityMetadata {
  id: string;
  name: string;
  wikiPath: string | null;
  rawPath: string | null;
  lastModified: string | null;
  preview: string | null;
}

export interface VaultProjectsResponse {
  projects: VaultProject[];
}

export interface VaultCourse extends VaultEntityMetadata {
  id: string;
  name: string;
  wikiPath: string | null;
  rawPath: string | null;
  lastModified: string | null;
  preview: string | null;
}

export interface VaultCoursesResponse {
  courses: VaultCourse[];
}

export interface VaultHackathon extends VaultEntityMetadata {
  id: string;
  name: string;
  wikiPath: string | null;
  rawPath: string | null;
  lastModified: string | null;
  preview: string | null;
}

export interface VaultHackathonsResponse {
  hackathons: VaultHackathon[];
}

export interface VaultBusinessItem extends VaultEntityMetadata {
  id: string;
  name: string;
  wikiPath: string | null;
  rawPath: string | null;
  lastModified: string | null;
  preview: string | null;
}

export interface VaultBusinessResponse {
  entities: VaultBusinessItem[];
}

export interface VaultOpsFile {
  path: string;
  exists: boolean;
  preview: string | null;
  lastModified: string | null;
}

export interface VaultTask {
  id: string;
  title: string;
  status: string;
  area: string | null;
  priority: string | null;
  due: string | null;
  source: string | null;
  raw: string;
}

export interface VaultTasksResponse {
  path: string;
  exists: boolean;
  lastModified: string | null;
  preview: string | null;
  tasks: VaultTask[];
  parseMode: 'markdown-table' | 'checklist' | 'preview-only';
}

export type TaskStatus   = 'todo' | 'in progress' | 'blocked' | 'done';
export type TaskPriority = 'low' | 'medium' | 'high';

export const TASK_STATUSES:   TaskStatus[]   = ['todo', 'in progress', 'blocked', 'done'];
export const TASK_PRIORITIES: TaskPriority[] = ['low', 'medium', 'high'];

export interface TaskStatusUpdateResponse {
  ok: boolean;
  task: VaultTask;
  path: string;
  updatedAt: string;
}

// ── calendar candidates ───────────────────────────────────────────────────────

export interface CalendarCandidate {
  id:       string;
  date:     string;
  time:     string | null;
  duration: string | null;
  title:    string;
  reason:   string | null;
  source:   string | null;
  approved: string;
  raw:      string;
}

export interface CalendarCandidatesResponse {
  path:         string;
  exists:       boolean;
  lastModified: string | null;
  preview:      string | null;
  parseMode:    'markdown-table' | 'preview-only' | 'missing';
  candidates:   CalendarCandidate[];
}

export interface UpdateCalendarCandidateRequest {
  date:     string;
  time?:    string | null;
  duration?: string | null;
  title:    string;
  reason?:  string | null;
  source?:  string | null;
  approved: 'Yes' | 'No';
}

export interface CreateCalendarCandidateRequest {
  date:     string;
  time?:    string | null;
  duration?: string | null;
  title:    string;
  reason?:  string | null;
  source?:  string | null;
  approved: 'Yes' | 'No';
}

export interface UpdateCalendarCandidateResponse {
  ok:        boolean;
  candidate: CalendarCandidate;
  path:      string;
  updatedAt: string;
}

export interface CreateVaultTaskRequest {
  title:    string;
  status:   TaskStatus;
  area?:    string | null;
  priority?: TaskPriority | null;
  due?:     string | null;
  source?:  string | null;
}

export interface CreateVaultTaskResponse {
  ok:        boolean;
  task:      VaultTask;
  path:      string;
  updatedAt: string;
}

// ── resume pipeline ───────────────────────────────────────────────────────────

export type ResumePipelineStatus =
  | 'new' | 'tailoring' | 'applied' | 'interview'
  | 'offer' | 'rejected' | 'archived';

export type ResumePipelinePriority = 'high' | 'medium' | 'low';

export interface ResumePipelineItem {
  id:       string;
  target:   string;
  company:  string | null;
  role:     string | null;
  status:   string;
  priority: string | null;
  deadline: string | null;
  link:     string | null;
  notes:    string | null;
  raw:      string;
}

export interface ResumePipelineResponse {
  path:         string;
  exists:       boolean;
  lastModified: string | null;
  preview:      string | null;
  parseMode:    'markdown-table' | 'preview-only' | 'missing';
  items:        ResumePipelineItem[];
}

export interface UpdateResumePipelineStatusResponse {
  ok:        boolean;
  item:      ResumePipelineItem;
  path:      string;
  updatedAt: string;
}

export interface CreateResumePipelineItemRequest {
  target:    string;
  company?:  string | null;
  role?:     string | null;
  status?:   ResumePipelineStatus | null;
  priority?: ResumePipelinePriority | null;
  deadline?: string | null;
  link?:     string | null;
  notes?:    string | null;
}

export interface CreateResumePipelineItemResponse {
  ok:        boolean;
  item:      ResumePipelineItem;
  path:      string;
  updatedAt: string;
}

export interface UpdateResumePipelineItemRequest {
  target:    string;
  company?:  string | null;
  role?:     string | null;
  priority?: ResumePipelinePriority | null;
  deadline?: string | null;
  link?:     string | null;
  notes?:    string | null;
}

export interface UpdateResumePipelineItemResponse {
  ok:        boolean;
  item:      ResumePipelineItem;
  path:      string;
  updatedAt: string;
}

// ── backfill ──────────────────────────────────────────────────────────────────

export type BackfillStatus = 'new' | 'triaged' | 'in-progress' | 'done' | 'skipped';
export type BackfillType   = 'project' | 'repo' | 'hackathon' | 'course' | 'business' | 'other';
export type BackfillAgent  = 'claude-code' | 'opencode' | 'manual';
export type BackfillValue  = 'high' | 'medium' | 'low';

export interface BackfillItem {
  id:     string;
  item:   string;
  type:   string | null;
  status: string;
  value:  string | null;
  path:   string | null;
  notes:  string | null;
  agent:  string | null;
  raw:    string;
}

export interface BackfillResponse {
  path:         string;
  exists:       boolean;
  lastModified: string | null;
  preview:      string | null;
  parseMode:    'markdown-table' | 'preview-only' | 'missing';
  items:        BackfillItem[];
}

export interface UpdateBackfillStatusResponse {
  ok:        boolean;
  item:      BackfillItem;
  path:      string;
  updatedAt: string;
}

export interface CreateBackfillItemRequest {
  item:    string;
  type?:   BackfillType | null;
  status?: BackfillStatus | null;
  value?:  BackfillValue | null;
  path?:   string | null;
  agent?:  BackfillAgent | null;
  notes?:  string | null;
}

export interface CreateBackfillItemResponse {
  ok:        boolean;
  item:      BackfillItem;
  path:      string;
  updatedAt: string;
}

export interface UpdateBackfillItemRequest {
  item:   string;
  type?:  BackfillType | null;
  value?: BackfillValue | null;
  path?:  string | null;
  agent?: BackfillAgent | null;
  notes?: string | null;
}

export interface UpdateBackfillItemResponse {
  ok:        boolean;
  item:      BackfillItem;
  path:      string;
  updatedAt: string;
}

// ── escalation queue ─────────────────────────────────────────────────────────

export type EscalationStatus = 'new' | 'ready' | 'in-progress' | 'done' | 'blocked' | 'skipped';
export type EscalationTarget = 'claude-code' | 'opencode' | 'manual';

export interface EscalationItem {
  id:       string;
  task:     string;
  target:   EscalationTarget | string | null;
  status:   EscalationStatus | string;
  priority: string | null;
  source:   string | null;
  path:     string | null;
  notes:    string | null;
  created:  string | null;
  raw:      string;
}

export interface EscalationResponse {
  path:         string;
  exists:       boolean;
  lastModified: string | null;
  preview:      string | null;
  parseMode:    'markdown-table' | 'preview-only' | 'missing';
  items:        EscalationItem[];
}

export interface CreateEscalationRequest {
  task:     string;
  target:   EscalationTarget;
  priority?: string | null;
  source?:  string | null;
  path?:    string | null;
  notes?:   string | null;
}

export interface UpdateEscalationStatusResponse {
  ok:        boolean;
  item:      EscalationItem;
  path:      string;
  updatedAt: string;
}

export interface UpdateEscalationItemRequest {
  task:     string;
  target:   EscalationTarget;
  priority?: string | null;
  source?:  string | null;
  path?:    string | null;
  notes?:   string | null;
}

export interface UpdateEscalationItemResponse {
  ok:        boolean;
  item:      EscalationItem;
  path:      string;
  updatedAt: string;
}

// ── dashboard summary ─────────────────────────────────────────────────────────

export interface DashboardRawSummary {
  staged: number;
  proposed: number;
  edited: number;
  approved: number;
  routed: number;
  archived: number;
}

export interface DashboardTaskSummary {
  total: number;
  todo: number;
  inProgress: number;
  blocked: number;
  done: number;
}

export interface DashboardCalendarSummary {
  total: number;
  approved: number;
  pending: number;
}

export interface DashboardEntitySummary {
  projects: number;
  courses: number;
  hackathons: number;
  business: number;
}

export interface DashboardBackfillSummary {
  total: number;
  new: number;
  triaged: number;
  inProgress: number;
  done: number;
  skipped: number;
}

export interface DashboardResumeSummary {
  total: number;
  new: number;
  tailoring: number;
  applied: number;
  interview: number;
  offer: number;
  rejected: number;
  archived: number;
}

export interface DashboardEscalationSummary {
  total:      number;
  active:     number;
  new:        number;
  ready:      number;
  inProgress: number;
  blocked:    number;
  done:       number;
  skipped:    number;
}

export interface DashboardRuntimeSummary {
  backend: string;
  brain: 'available' | 'unavailable' | 'unknown';
  agent: 'available' | 'unavailable' | 'unknown';
  vaultExists: boolean;
}

export interface DashboardSummaryError {
  source: string;
  message: string;
}

export interface DashboardTodayPlanItem {
  id: string;
  title: string;
  status: string;
  priority: string | null;
  due: string | null;
  area: string | null;
  source: string | null;
  reason: string;
}

export interface DashboardTodayPlan {
  items: DashboardTodayPlanItem[];
  source: string;
  generatedAt: string;
}

// ── active work drill-down ────────────────────────────────────────────────────

export interface DashboardActiveWorkBackfillItem {
  id:       string;
  title:    string;
  status:   string;
  priority: string | null;
  type:     string | null;
  path:     string | null;
  reason:   string;
}

export interface DashboardActiveWorkEscalationItem {
  id:       string;
  title:    string;
  status:   string;
  priority: string | null;
  target:   string | null;
  path:     string | null;
  reason:   string;
}

export interface DashboardActiveWorkResumeItem {
  id:       string;
  title:    string;
  status:   string;
  priority: string | null;
  company:  string | null;
  role:     string | null;
  reason:   string;
}

export interface DashboardActiveWorkCalendarItem {
  id:     string;
  title:  string;
  status: string;
  date:   string | null;
  time:   string | null;
  reason: string;
}

export interface DashboardActiveWorkRawItem {
  id:     string;
  title:  string;
  status: string;
  reason: string;
}

export interface DashboardActiveWork {
  backfill:    DashboardActiveWorkBackfillItem[];
  escalations: DashboardActiveWorkEscalationItem[];
  resume:      DashboardActiveWorkResumeItem[];
  calendar:    DashboardActiveWorkCalendarItem[];
  raw:         DashboardActiveWorkRawItem[];
}

export interface DashboardSummary {
  raw:         DashboardRawSummary;
  tasks:       DashboardTaskSummary;
  calendar:    DashboardCalendarSummary;
  entities:    DashboardEntitySummary;
  backfill:    DashboardBackfillSummary;
  resume:      DashboardResumeSummary;
  escalations: DashboardEscalationSummary;
  runtime:     DashboardRuntimeSummary;
  todayPlan:   DashboardTodayPlan;
  activeWork:  DashboardActiveWork;
  errors:      DashboardSummaryError[];
}

// ── proposal queue (v1: aggregates Raw Inbox classification proposals) ─────────

export type ProposalStatus    = 'pending' | 'approved' | 'rejected' | 'applied' | 'skipped';
export type ProposalRiskLevel = 'low' | 'medium' | 'high';
export type ProposalType      = 'file_route' | 'chat_consolidation' | 'research_note' | 'email_summary';   // future: note_write | calendar_candidate | …
export type ProposalSource    = 'raw-inbox' | 'chat-consolidation' | 'research' | 'email-intake';          // future: mcp | agent
export type ProposalAction    = 'open_raw_inbox' | 'open_consolidation' | 'open_research' | 'open_email_intake';

export interface ProposalDetails {
  filename:   string | null;
  domain:     string | null;
  entity:     string | null;
  sourceType: string | null;
  reason:     string | null;
}

export interface ProposalItem {
  id:         string;
  source:     ProposalSource | string;
  type:       ProposalType | string;
  riskLevel:  ProposalRiskLevel | string;
  title:      string;
  summary:    string;
  status:     ProposalStatus | string;
  confidence: 'High' | 'Medium' | 'Low' | null;
  targetPath: string | null;
  createdAt:  string | null;
  updatedAt:  string | null;
  relatedId:  string;
  actions:    (ProposalAction | string)[];
  details:    ProposalDetails;
}

export interface ProposalListError {
  source:  string;
  message: string;
}

export interface ProposalListResponse {
  proposals: ProposalItem[];
  errors:    ProposalListError[];
}

// ── proposal apply / reject (A1) ────────────────────────────────────────────────

export interface ApplyProposalResult {
  id:             string;
  ok:             boolean;
  status:         string;            // applied | skipped | error
  message:        string;
  targetPath:     string | null;
  alreadyApplied: boolean;
}

export interface ApplyBatchResponse {
  results:      ApplyProposalResult[];
  appliedCount: number;
  failedCount:  number;
}

// ── tool / MCP connections (v0: read-only readiness inventory) ─────────────────

export type ToolConnectionCategory = 'runtime' | 'mcp' | 'browser' | 'external' | 'developer';
export type ToolConnectionState    = 'available' | 'unavailable' | 'not_configured' | 'disabled' | 'planned' | 'error';
export type ToolRiskLevel          = 'low' | 'medium' | 'high';

export interface ToolConnectionStatus {
  id:            string;
  name:          string;
  category:      ToolConnectionCategory | string;
  status:        ToolConnectionState | string;
  enabled:       boolean;
  riskLevel:     ToolRiskLevel | string;
  capabilities:  string[];
  allowedNow:    string[];
  blockedNow:    string[];
  requires:      string[];
  lastCheckedAt: string | null;
  lastError:     string | null;
  notes:         string | null;
}

export interface ToolConnectionStatusResponse {
  items: ToolConnectionStatus[];
}

// ── OpenClaw / NemoClaw runtime status (v0: read-only readiness) ────────────────

export type RuntimeStatusState = 'available' | 'unavailable' | 'not_configured' | 'disabled' | 'planned' | 'error';

export interface RuntimeStatusItem {
  id:          string;   // openclaw | nemoclaw_openshell | browser_harness | computer_use | mcp_gateway
  name:        string;
  status:      RuntimeStatusState | string;
  available:   boolean;
  enabled:     boolean;
  requiredFor: string[];
  dependsOn:   string[];
  blocks:      string[];
  configured:  Record<string, boolean>;
  notes:       string | null;
}

export interface RuntimeStatusResponse {
  items: RuntimeStatusItem[];
}

// ── NemoClaw/OpenShell health probe (v0: explicit, opt-in reachability) ─────────

export type RuntimeProbeStatus = 'reachable' | 'unavailable' | 'not_configured' | 'error';

export interface NemoclawProbeRequest {
  timeoutMs?: number | null;
}

export interface NemoclawProbeDetails {
  urlConfigured:        boolean;
  policyPathConfigured: boolean;
  enabledFlag:          boolean;
  remoteProbeAllowed:   boolean;
  hostRedacted:         string | null;   // scheme://host[:port] only — never userinfo/path/query
}

export interface NemoclawProbeResponse {
  id:         string;
  checkedAt:  string;
  configured: boolean;
  reachable:  boolean;
  status:     RuntimeProbeStatus | string;
  durationMs: number;
  message:    string;
  details:    NemoclawProbeDetails;
}

export interface NemoclawLastProbeResponse {
  lastProbe: NemoclawProbeResponse | null;
}

// ── NemoClaw/OpenShell policy inspection (v0: read-only, no enforcement) ─────────

export type NemoclawPolicyStatus =
  | 'not_configured' | 'missing' | 'unreadable' | 'invalid' | 'loaded' | 'error';

export interface NemoclawPolicySummary {
  declaredModes:      string[];
  networkPolicy:      string | null;
  filesystemScopes:   string[];
  browserAllowed:     boolean | null;   // null = unknown (never implied allowed)
  computerUseAllowed: boolean | null;
  mcpAllowed:         boolean | null;
  credentialAccess:   string;
  unknownKeys:        string[];
}

export interface NemoclawPolicyResponse {
  id:                string;
  configured:        boolean;
  pathConfigured:    boolean;
  pathExists:        boolean;
  readable:          boolean;
  valid:             boolean;
  status:            NemoclawPolicyStatus | string;
  message:           string;
  policyPathDisplay: string | null;
  format:            string | null;   // json | yaml | unknown
  summary:           NemoclawPolicySummary | null;
  warnings:          string[];
  errors:            string[];
}

// ── guardrail readiness (v0: read-only correlation, no enforcement/execution) ───

export type GuardrailReadinessStatus =
  | 'not_ready' | 'partially_ready' | 'ready_for_bridge_design' | 'error';

export interface GuardrailReadinessComponents {
  runtimeStatus: string;   // nemoclaw runtime item status
  lastProbe:     string;   // cached probe status or 'not_run'
  policy:        string;   // policy inspection status
  modePolicy:    string;   // available | unavailable
}

export interface GuardrailCapabilityUnlocks {
  openclawBridge: boolean;   // all false in every state — readiness enables nothing
  browserHarness: boolean;
  computerUse:    boolean;
  mcpGateway:     boolean;
  gmail:          boolean;
}

export interface GuardrailReadinessResponse {
  id:                string;
  status:            GuardrailReadinessStatus | string;
  ready:             boolean;   // true ONLY for ready_for_bridge_design (never execution-ready)
  checkedAt:         string;
  summary:           string;
  components:        GuardrailReadinessComponents;
  blockers:          string[];
  warnings:          string[];
  nextSteps:         string[];
  capabilityUnlocks: GuardrailCapabilityUnlocks;
  notes:             string;
}

// ── runtime bridge contract (v0: dry-run validator, no execution) ───────────────

export type RuntimeBridgeActionKind =
  | 'browser.open' | 'browser.search' | 'browser.read_page'
  | 'computer.click' | 'computer.type' | 'computer.screenshot'
  | 'mcp.call' | 'gmail.search' | 'gmail.read' | 'calendar.read'
  | 'vault.read' | 'vault.write'
  | 'brain.status' | 'brain.raw_status' | 'brain.vault_path'
  | 'unknown';

export type RuntimeBridgeValidationStatus =
  | 'blocked_by_mode' | 'blocked' | 'validated' | 'error';

export interface RuntimeBridgeAction {
  kind:    RuntimeBridgeActionKind | string;
  target?: string | null;
  args?:   Record<string, unknown> | null;   // untrusted; summarized only, never executed
}

export interface RuntimeBridgeValidationRequest {
  source:          string;                    // default 'openclaw'
  mode?:           string | null;
  requestedAction: RuntimeBridgeAction;
  reason?:         string | null;
  conversationId?: string | null;
}

export interface RuntimeBridgeValidationChecks {
  schemaValid:                   boolean;
  modeAllowsEvaluation:          boolean;
  guardrailReadyForBridgeDesign: boolean;
  runtimeBridgeImplemented:      boolean;     // always false — bridge not implemented
  permissionGatewayDecision:     string;      // gateway dry-run decision, or 'n/a'
}

export interface RuntimeBridgeValidationResponse {
  id:               string;
  status:           RuntimeBridgeValidationStatus | string;
  allowed:          boolean;                  // always false — never an approval to run
  requiresApproval: boolean;
  executionEnabled: boolean;                  // always false — nothing executes
  mode:             string;
  source:           string;
  actionKind:       string;
  riskLevel:        string;                   // low | medium | high
  decision:         string;
  message:          string;
  checks:           RuntimeBridgeValidationChecks;
  blockers:         string[];
  warnings:         string[];
  logId:            string | null;
  createdAt:        string;
}

// ── permission gateway (v0: deny-by-default classification, no execution) ───────

export type ToolDecision =
  | 'allowed' | 'denied' | 'requires_approval' | 'not_wired' | 'disabled'
  | 'approved' | 'rejected' | 'executed' | 'failed';
export type PermissionRisk    = 'low' | 'medium' | 'high' | 'disabled';
export type PermissionStatus  = 'not_wired' | 'available' | 'disabled';

export interface PermissionPolicy {
  tool:             string;
  category:         string;
  riskLevel:        PermissionRisk | string;
  status:           PermissionStatus | string;
  requiresApproval: boolean;
  executionEnabled: boolean;
  notes:            string | null;
}

export interface PermissionPolicyResponse {
  policies: PermissionPolicy[];
}

export interface ToolRequestEvaluationRequest {
  tool:         string;
  args?:        Record<string, unknown> | null;
  reason?:      string | null;
  requestedBy?: string | null;
}

export interface ToolRequestEvaluationResponse {
  allowed:              boolean;
  decision:             ToolDecision | string;
  riskLevel:            PermissionRisk | string;
  tool:                 string;
  requiresApproval:     boolean;
  executionEnabled:     boolean;
  reason:               string;
  policyNotes:          string | null;
  sanitizedArgsSummary: string;
  wouldLog:             boolean;
  logId?:               string | null;   // id of the backend-local audit entry
}

export type ToolLogSource =
  | 'gateway_eval' | 'gateway_execution' | 'runtime_bridge_validation'
  | 'approval_transition';

export interface PermissionEvaluationLog {
  id:                   string;
  timestamp:            string;
  source:               ToolLogSource | null;
  tool:                 string;
  requestedBy:          string | null;
  reason:               string | null;
  decision:             ToolDecision | string;
  riskLevel:            PermissionRisk | string;
  allowed:              boolean;
  requiresApproval:     boolean;
  executionEnabled:     boolean;
  sanitizedArgsSummary: string;
  policyNotes:          string | null;
  result:               string;   // evaluated_only | success | failure
  exitCode?:            number | null;
  stdoutPreview?:       string | null;
  stderrPreview?:       string | null;
  durationMs?:          number | null;
  approvalId:           string | null;
  requestId:            string | null;
  approvedBy:           string | null;
  approvedAt:           string | null;
}

export interface PermissionEvaluationLogsResponse {
  logs: PermissionEvaluationLog[];
}

export interface PermissionLogQuery {
  limit?:    number;
  tool?:     string;
  decision?: string;
}

// ── safe-local tool execution (v0) ──────────────────────────────────────────────

export interface ToolExecutionRequest {
  tool:         string;
  args?:        Record<string, unknown> | null;
  reason?:      string | null;
  requestedBy?: string | null;
}

export interface ToolExecutionResponse {
  tool:             string;
  allowed:          boolean;
  decision:         string;   // executed | denied | requires_approval | not_wired | disabled
  riskLevel:        PermissionRisk | string;
  requiresApproval: boolean;
  executionEnabled: boolean;
  evaluationLogId:  string;
  executionLogId:   string | null;
  ok:               boolean;
  exitCode?:        number | null;
  stdout?:          string | null;
  stderr?:          string | null;
  durationMs?:      number | null;
  error?:           string | null;
}

// ── agent tool request (v0: evaluate-only; never executes) ──────────────────────

export interface AgentToolRequestEvaluation {
  allowed:          boolean;
  decision:         string;   // allowed | denied | requires_approval | not_wired | disabled
  riskLevel:        PermissionRisk | string;
  requiresApproval: boolean;
  executionEnabled: boolean;
  reason:           string;
  policyNotes:      string | null;
  logId:            string;
}

export interface AgentToolRequestResponse {
  id:             string;
  tool:           string;
  argsSummary:    string;
  reason:         string | null;
  requestedBy:    string;
  conversationId: string | null;
  mode:           string;
  approvalId:     string | null;
  approvalStatus: ToolApprovalStatus | null;
  evaluation:     AgentToolRequestEvaluation;
  createdAt:      string;
  status:         'evaluated_only' | ToolApprovalStatus;
}

// Alias for the stored/listed record (same shape as the create response).
export type AgentToolRequest = AgentToolRequestResponse;

export interface CreateAgentToolRequestRequest {
  tool:            string;
  args?:           Record<string, unknown> | null;
  reason?:         string | null;
  requestedBy?:    string | null;
  conversationId?: string | null;
  // Agent Mode Enforcement v0 — selected mode gates whether the request is evaluated.
  mode?:           string | null;
}

// Create returns either an evaluated record or a blocked-by-mode response.
export type CreateAgentToolRequestResult = AgentToolRequestResponse | AgentModeBlockedResponse;

export function isBlockedByMode(
  r: CreateAgentToolRequestResult,
): r is AgentModeBlockedResponse {
  return (r as AgentModeBlockedResponse).status === 'blocked_by_mode';
}

export interface AgentToolRequestListResponse {
  requests: AgentToolRequestResponse[];
}

// ── gated local tool approvals (A3) ───────────────────────────────────────────

export type ToolApprovalStatus =
  | 'pending_approval' | 'approved' | 'rejected'
  | 'executing' | 'executed' | 'failed';

export interface ToolApprovalExecutionSummary {
  ok:         boolean;
  resultType: 'brain_command' | 'task_created' | 'calendar_candidate_created';
  message:    string;
  path:       string | null;
  id:         string | null;
}

export type ToolApprovalBrainReviewFields = Record<string, never>;

export interface ToolApprovalTaskReviewFields {
  title:    string;
  status:   'todo' | 'in progress' | 'blocked' | 'done';
  area:     string | null;
  priority: 'low' | 'medium' | 'high' | null;
  due:      string | null;
  source:   string | null;
}

export interface ToolApprovalCalendarReviewFields {
  date:     string;
  time:     string | null;
  duration: string | null;
  title:    string;
  reason:   string | null;
  source:   string | null;
  approved: 'No';
}

// The ONLY external write. Distinct from the candidate shape above: no
// source/approved, and it carries location/timeZone.
export interface ToolApprovalCalendarEventReviewFields {
  date:     string;
  time:     string | null;
  duration: string | null;
  title:    string;
  reason:   string | null;
  location: string | null;
  timeZone: string | null;
}

export interface ToolApprovalBrowserSearchReviewFields {
  sessionId: string;
  query:     string;
  limit:     number | null;
}

export interface ToolApprovalBrowserPageReviewFields {
  sessionId: string;
  url:       string;
}

export type ToolApprovalReviewFields =
  | ToolApprovalBrainReviewFields
  | ToolApprovalTaskReviewFields
  | ToolApprovalCalendarReviewFields
  | ToolApprovalCalendarEventReviewFields
  | ToolApprovalBrowserSearchReviewFields
  | ToolApprovalBrowserPageReviewFields;

export interface ToolApproval {
  id:                 string;
  requestId:          string;
  status:             ToolApprovalStatus;
  tool:               string;
  mode:               string;
  risk:               string;
  argsSummary:        string;
  reviewFields:       ToolApprovalReviewFields;
  reason:             string | null;
  requestedBy:        string;
  approvedBy:         string | null;
  rejectedBy:         string | null;
  createdAt:          string;
  approvedAt:         string | null;
  rejectedAt:         string | null;
  executionStartedAt: string | null;
  executedAt:         string | null;
  failedAt:           string | null;
  evaluationLogId:    string | null;
  executionLogId:     string | null;
  transitionLogId:    string | null;
  result:             ToolApprovalExecutionSummary | null;
  error:              string | null;
  auditWarning:       string | null;
}

export interface ToolApprovalListResponse {
  approvals: ToolApproval[];
}

export interface ApproveToolApprovalRequest {
  approvedBy?: string;
}

export interface RejectToolApprovalRequest {
  rejectedBy?: string;
  reason?:     string;
}

// ── chat / AI consolidation (v1: manual paste/import) ──────────────────────────

export type ConsolidationSourceTool = 'chatgpt' | 'claude' | 'claude-code' | 'opencode' | 'other';
export type ConsolidationDomain     = 'project' | 'course' | 'business' | 'research' | 'personal' | 'unknown';
export type ConsolidationStatus     = 'draft' | 'saved';

export interface ConsolidationDraft {
  id:                     string;
  sourceTool:             ConsolidationSourceTool;
  conversationTitle:      string;
  domain:                 ConsolidationDomain;
  entity:                 string | null;
  transcript:             string;
  summary:                string;
  decisions:              string[];
  actionItems:            string[];
  codeOrFilesReferenced:  string[];
  status:                 ConsolidationStatus;
  proposedDestination:    string;
  savedPath:              string | null;
  createdAt:              string;
  updatedAt:              string;
}

export interface ConsolidationDraftsResponse {
  drafts: ConsolidationDraft[];
}

export interface CreateConsolidationDraftRequest {
  sourceTool:             ConsolidationSourceTool;
  conversationTitle:      string;
  domain:                 ConsolidationDomain;
  entity?:                string | null;
  transcript:             string;
  summary?:               string | null;
  decisions?:             string[];
  actionItems?:           string[];
  codeOrFilesReferenced?: string[];
}

export interface UpdateConsolidationDraftRequest {
  conversationTitle?:     string;
  domain?:                ConsolidationDomain;
  entity?:                string | null;
  summary?:               string;
  decisions?:             string[];
  actionItems?:           string[];
  codeOrFilesReferenced?: string[];
}

export interface SaveConsolidationDraftResponse {
  ok:           boolean;
  draft:        ConsolidationDraft;
  relativePath: string;
  absolutePath: string;
}

// ── research (v1: manual capture) ──────────────────────────────────────────────

export type ResearchDomain = 'project' | 'course' | 'business' | 'personal' | 'technical' | 'market' | 'general' | 'unknown';
export type ResearchStatus = 'draft' | 'saved';

export interface ResearchSource {
  title: string | null;
  url:    string | null;
  notes:  string | null;
}

export interface ResearchDraft {
  id:                     string;
  title:                  string;
  topic:                  string | null;
  domain:                 ResearchDomain;
  entity:                 string | null;
  researchQuestion:       string | null;
  summary:                string;
  keyFindings:            string[];
  sources:                ResearchSource[];
  openQuestions:          string[];
  recommendedNextActions: string[];
  rawNotes:               string;
  status:                 ResearchStatus;
  proposedDestination:    string;
  savedPath:              string | null;
  createdAt:              string;
  updatedAt:              string;
}

export interface ResearchDraftsResponse {
  drafts: ResearchDraft[];
}

export interface CreateResearchDraftRequest {
  title:                   string;
  topic?:                  string | null;
  domain:                  ResearchDomain;
  entity?:                 string | null;
  researchQuestion?:       string | null;
  summary?:                string | null;
  keyFindings?:            string[];
  sources?:                ResearchSource[];
  openQuestions?:          string[];
  recommendedNextActions?: string[];
  rawNotes:                string;
}

export interface UpdateResearchDraftRequest {
  title?:                  string;
  topic?:                  string | null;
  domain?:                 ResearchDomain;
  entity?:                 string | null;
  researchQuestion?:       string | null;
  summary?:                string;
  keyFindings?:            string[];
  sources?:                ResearchSource[];
  openQuestions?:          string[];
  recommendedNextActions?: string[];
  rawNotes?:               string;
}

export interface SaveResearchDraftResponse {
  ok:           boolean;
  draft:        ResearchDraft;
  relativePath: string;
  absolutePath: string;
}

// ── email intake (v1: manual paste/import) ─────────────────────────────────────

export type EmailIntakeDomain = 'course' | 'business' | 'personal' | 'unknown';
export type EmailIntakeStatus = 'draft' | 'saved';
export type EmailConfidence   = 'High' | 'Medium' | 'Low';

export interface EmailIntakeDraft {
  id:                   string;
  subject:              string;
  sender:               string | null;
  receivedAt:           string | null;
  domain:               EmailIntakeDomain;
  entity:               string | null;
  summary:              string;
  actionRequired:       string | null;
  dueDate:              string | null;
  confidence:           EmailConfidence | null;
  rawEmail:             string;
  proposedTaskRows:     string[];
  proposedCalendarRows: string[];
  status:               EmailIntakeStatus;
  proposedDestination:  string;
  savedPath:            string | null;
  createdAt:            string;
  updatedAt:            string;
}

export interface EmailIntakeDraftsResponse {
  drafts: EmailIntakeDraft[];
}

export interface CreateEmailIntakeDraftRequest {
  subject:               string;
  sender?:               string | null;
  receivedAt?:           string | null;
  domain:                EmailIntakeDomain;
  entity?:               string | null;
  summary?:              string | null;
  actionRequired?:       string | null;
  dueDate?:              string | null;
  confidence?:           EmailConfidence | null;
  rawEmail:              string;
  proposedTaskRows?:     string[];
  proposedCalendarRows?: string[];
}

export interface UpdateEmailIntakeDraftRequest {
  subject?:              string;
  sender?:               string | null;
  receivedAt?:           string | null;
  domain?:               EmailIntakeDomain;
  entity?:               string | null;
  summary?:              string;
  actionRequired?:       string | null;
  dueDate?:              string | null;
  confidence?:           EmailConfidence | null;
  proposedTaskRows?:     string[];
  proposedCalendarRows?: string[];
}

// ── opt-in draft AI assist (A2: preview only) ──────────────────────────────────

export type DraftAssistModelTier = 'everyday' | 'heavy';

export interface DraftAssistRequest {
  modelTier: DraftAssistModelTier;
}

export interface DraftAssistPreview<TSuggestions> {
  modelTier:      DraftAssistModelTier;
  model:          string;
  durationMs:     number;
  draftUpdatedAt: string;
  suggestions:    TSuggestions;
}

export interface ConsolidationAssistSuggestions {
  conversationTitle:     string;
  domain:                ConsolidationDomain;
  entity:                string | null;
  summary:               string;
  decisions:             string[];
  actionItems:           string[];
  codeOrFilesReferenced: string[];
}

export interface ResearchAssistSuggestions {
  title:                  string;
  topic:                  string | null;
  domain:                 ResearchDomain;
  entity:                 string | null;
  researchQuestion:       string | null;
  summary:                string;
  keyFindings:            string[];
  openQuestions:          string[];
  recommendedNextActions: string[];
}

export interface EmailIntakeAssistSuggestions {
  subject:              string;
  sender:               string | null;
  receivedAt:           string | null;
  domain:               EmailIntakeDomain;
  entity:               string | null;
  summary:              string;
  actionRequired:       string | null;
  dueDate:              string | null;
  confidence:           EmailConfidence | null;
  proposedTaskRows:     string[];
  proposedCalendarRows: string[];
}

export type ConsolidationAssistPreview = DraftAssistPreview<ConsolidationAssistSuggestions>;
export type ResearchAssistPreview      = DraftAssistPreview<ResearchAssistSuggestions>;
export type EmailIntakeAssistPreview   = DraftAssistPreview<EmailIntakeAssistSuggestions>;

// ── Computer-use harness (MVP v7) — PRIVILEGED, FULL DESKTOP ───────────────────
// Every mutating call needs the operator token. Status and stop deliberately do
// not, so the visible indicator always renders and Stop always works.

export interface ComputerUseSessionSummary {
  id:               string | null;
  task:             string | null;
  status:           string | null;
  budgetSeconds:    number | null;
  remainingSeconds: number;
  allowedWindows:   string[];
  actionCount:      number;
  refusedCount:     number;
  startedAt:        string | null;
  endedAt:          string | null;
}

export interface ComputerUseStatusResponse {
  enabled: boolean;
  active:  ComputerUseSessionSummary | null;
  message: string;
}

export interface ComputerUseSessionResponse {
  session:  ComputerUseSessionSummary;
  warnings: string[];
}

export interface ComputerUseObserveResponse {
  window:           string;
  width:            number;
  height:           number;
  screenshotBase64: string;
  warnings:         string[];
}

export interface ComputerUseActionResponse {
  ok:       boolean;
  window:   string;
  x:        number | null;
  y:        number | null;
  chars:    number | null;
  warnings: string[];
}

// ── Vault graph / Graphify viewer (D3d) — READ-ONLY ────────────────────────────

export interface GraphNode {
  id:        string;
  label:     string;
  path:      string | null;
  folder:    string;
  exists:    boolean;
  outDegree: number;
  inDegree:  number;
  fileCount: number;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface GraphStats {
  files:     number;
  nodes:     number;
  edges:     number;
  dangling:  number;
  orphans:   number;
  collapsed: number;
  truncated: boolean;
}

export interface VaultGraphResponse {
  nodes:    GraphNode[];
  edges:    GraphEdge[];
  stats:    GraphStats;
  source:   string;
  warnings: string[];
}

// ── Time-boxed browser research (C1) — GUARDRAILED ─────────────────────────────
// Page fetches are gated: the Permission Gateway classifies them, and the driver
// refuses unless the OpenShell sandbox guardrail is healthy. Browsing fails CLOSED.

export interface ResearchCapture {
  url:        string;
  title:      string;
  timestamp:  string;
  snippet:    string;
  textChars:  number;
  httpStatus: number | null;
}

export interface ResearchSessionSummary {
  id:               string | null;
  topic:            string | null;
  status:           string | null;
  budgetSeconds:    number | null;
  remainingSeconds: number;
  captureCount:     number;
  errorCount:       number;
  allowedDomains:   string[];
  startedAt:        string | null;
  endedAt:          string | null;
}

export interface ResearchSessionResponse {
  session:  ResearchSessionSummary;
  captures: ResearchCapture[];
  warnings: string[];
}

export interface ResearchSessionsResponse {
  sessions: ResearchSessionSummary[];
}

export interface StartResearchSessionRequest {
  topic:          string;
  allowedDomains: string[];
  budgetSeconds?: number;
}

export interface ChatCapturePayloadResponse {
  sourceTool:        string;
  conversationTitle: string;
  domain:            string;
  entity:            string | null;
  transcript:        string;
  turnCount:         number;
  sourceUrl:         string;
  capturedAt:        string | null;
  warnings:          string[];
}

export interface SearchResultItem {
  url:           string;
  title:         string;
  openable:      boolean;
  blockedReason: string | null;
}

export interface ResearchSearchResponse {
  query:         string;
  results:       SearchResultItem[];
  count:         number;
  openableCount: number;
  warnings:      string[];
}

export interface ResearchDraftPayloadResponse {
  title:    string;
  topic:    string;
  sources:  { title?: string; url?: string; notes?: string }[];
  rawNotes: string;
  warnings: string[];
}

// ── Local voice transcription (D1) — ON-DEVICE ONLY ────────────────────────────
// Audio is transcribed by faster-whisper in the backend process. It is never sent
// to a cloud speech service.

export interface VoiceStatusResponse {
  available:       boolean;
  model:           string;
  device:          string;
  computeType:     string;
  localFilesOnly:  boolean;
  maxUploadBytes:  number;
  maxAudioSeconds: number;
  message:         string;
}

export interface TranscriptSegment {
  start: number;
  end:   number;
  text:  string;
}

export interface TranscribeResponse {
  text:         string;
  language:     string | null;
  audioSeconds: number;
  durationMs:   number;
  segments:     TranscriptSegment[];
  warnings:     string[];
}

// ── Google Calendar read + reconciliation (B2) — READ-ONLY ─────────────────────
// No create/update/delete event type exists here. Event creation is Phase D2 and
// requires an additional scope plus explicit re-consent.

export interface GoogleCalendarEvent {
  eventId:  string;
  title:    string;
  start:    string | null;
  end:      string | null;
  allDay:   boolean;
  status:   string;
  htmlLink: string | null;
}

export interface GoogleCalendarEventsResponse {
  events:   GoogleCalendarEvent[];
  count:    number;
  timeMin:  string | null;
  timeMax:  string | null;
  decision: string;
  logId:    string | null;
  warnings: string[];
}

export interface CalendarReconcileCounts {
  matched:     number;
  conflicting: number;
  missing:     number;
  unparseable: number;
  events:      number;
}

export interface CalendarReconcileItem {
  candidateId: string | null;
  title:       string;
  date:        string | null;
  time:        string | null;
  duration:    string | null;
  eventId:     string | null;
  eventTitle:  string | null;
  eventStart:  string | null;
  htmlLink:    string | null;
  note:        string | null;
}

export interface CalendarReconcileResponse {
  counts:      CalendarReconcileCounts;
  matched:     CalendarReconcileItem[];
  conflicting: CalendarReconcileItem[];
  missing:     CalendarReconcileItem[];
  unparseable: CalendarReconcileItem[];
  notes:       string[];
  decision:    string;
  logId:       string | null;
}

export interface GoogleCalendarStatusResponse {
  configured:    boolean;
  tokenPresent:  boolean;
  scopes:        string[];
  readsEnabled:  boolean;
  writesEnabled: boolean;
  message:       string;
}

// ── Gmail read intake (B1) — READ-ONLY ─────────────────────────────────────────
// There is deliberately no send/delete/trash/archive/label type here: the backend
// exposes no such endpoint, and Gmail mutations are permanently disabled.

export interface GmailStatusResponse {
  configured:       boolean;
  clientConfigured: boolean;
  tokenPresent:     boolean;
  scopes:           string[];
  readsEnabled:     boolean;
  message:          string;
}

export interface GmailSearchRequest {
  query:       string;
  maxResults?: number;
}

export interface GmailThreadSummary {
  threadId:  string;
  messageId: string | null;
  subject:   string;
  sender:    string | null;
  to:        string | null;
  date:      string | null;
  snippet:   string;
}

export interface GmailSearchResponse {
  query:    string;
  count:    number;
  threads:  GmailThreadSummary[];
  decision: string;
  logId:    string | null;
  warnings: string[];
}

export interface GmailMessageResponse {
  messageId:     string;
  threadId:      string | null;
  subject:       string;
  sender:        string | null;
  to:            string | null;
  date:          string | null;
  snippet:       string;
  body:          string;
  bodyTruncated: boolean;
  labelIds:      string[];
  decision:      string;
  logId:         string | null;
  warnings:      string[];
}

export interface GmailImportRequest {
  messageId: string;
  domain?:   EmailIntakeDomain;
  entity?:   string;
}

export interface GmailImportResponse {
  ok:    boolean;
  draft: EmailIntakeDraft;
  logId: string | null;
}

export interface SaveEmailIntakeDraftResponse {
  ok:           boolean;
  draft:        EmailIntakeDraft;
  relativePath: string;
  absolutePath: string;
}

// ── HTTP helpers ──────────────────────────────────────────────────────────────

async function parseError(res: Response): Promise<string> {
  return res.json()
    .then((d: { detail?: unknown }) =>
      typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail)
    )
    .catch(() => res.statusText);
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail || `Request failed with status ${status}.`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function responseError(res: Response): Promise<ApiError> {
  return new ApiError(res.status, await parseError(res));
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw await responseError(res);
  return res.json() as Promise<T>;
}

async function getWithHeaders<T>(path: string, headers: Record<string, string>): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) throw await responseError(res);
  return res.json() as Promise<T>;
}

async function fetchWithBody<T>(method: string, path: string, body: unknown, headers?: Record<string, string>): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...headers },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await responseError(res);
  return res.json() as Promise<T>;
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' });
  if (!res.ok) throw await responseError(res);
  return res.json() as Promise<T>;
}

async function uploadForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST', body: form });
  if (!res.ok) throw await responseError(res);
  return res.json() as Promise<T>;
}

// ── API surface ───────────────────────────────────────────────────────────────


// ── MVP v10 read-only integrations (GitHub / Drive / Quercus) + vault search ────
// All read-only. Every payload below is UNTRUSTED external content: commit
// messages, issue bodies, Drive documents and Canvas descriptions are rendered
// as data and never treated as instructions.

export interface GitHubStatusResponse { configured: boolean; readOnly: boolean; message: string; }

export interface GitHubRepo {
  fullName: string; description: string; private: boolean;
  language: string | null; pushedAt: string | null; htmlUrl: string | null; openIssues: number;
}
export interface GitHubReposResponse { repos: GitHubRepo[]; logId: string | null; warnings: string[]; }

export interface GitHubCommit {
  sha: string; message: string; author: string | null; date: string | null; htmlUrl: string | null;
}
export interface GitHubCommitsResponse { repo: string; commits: GitHubCommit[]; logId: string | null; warnings: string[]; }

export interface GitHubIssue {
  number: number; title: string; state: string; isPullRequest: boolean;
  updatedAt: string | null; htmlUrl: string | null;
}
export interface GitHubIssuesResponse { repo: string; issues: GitHubIssue[]; logId: string | null; warnings: string[]; }

export interface DriveFile {
  fileId: string; name: string; mimeType: string;
  modifiedTime: string | null; webViewLink: string | null; readable: boolean;
}
export interface DriveFilesResponse { files: DriveFile[]; logId: string | null; warnings: string[]; }
export interface DriveDocumentResponse {
  fileId: string; name: string; mimeType: string; webViewLink: string | null;
  text: string; truncated: boolean; logId: string | null; warnings: string[];
}

export interface QuercusStatusResponse { configured: boolean; host: string; readOnly: boolean; message: string; }
export interface QuercusCourse { courseId: string; name: string; courseCode: string; term: string | null; }
export interface QuercusCoursesResponse { courses: QuercusCourse[]; logId: string | null; warnings: string[]; }
export interface QuercusAssignment {
  assignmentId: string; courseId: string; name: string; dueAt: string | null;
  pointsPossible: number | null; htmlUrl: string | null; description: string;
}
export interface QuercusAssignmentsResponse { courseId: string; assignments: QuercusAssignment[]; logId: string | null; warnings: string[]; }
export interface QuercusAnnouncement {
  announcementId: string; courseId: string; title: string;
  postedAt: string | null; htmlUrl: string | null; message: string;
}
export interface QuercusAnnouncementsResponse { courseId: string; announcements: QuercusAnnouncement[]; logId: string | null; warnings: string[]; }

export interface VaultSearchHit { path: string; heading: string; score: number; snippet: string; }
export interface VaultSearchResponse {
  query: string; results: VaultSearchHit[]; count: number;
  degraded: boolean; mode: string; builtAt: string | null; warnings: string[];
}
export interface VaultIndexStatusResponse {
  built: boolean; builtAt: string | null; chunks: number;
  embedded: boolean; degraded: boolean; vaultPath: string | null;
}
export interface BuildVaultIndexResponse {
  files: number; chunks: number; embedded: boolean; degraded: boolean; builtAt: string | null;
}

export const api = {
  // dashboard summary
  getDashboardSummary: () => get<DashboardSummary>('/api/dashboard/summary'),

  // proposal queue (read-only aggregation; Raw Inbox + Consolidation drafts)
  getProposals: () => get<ProposalListResponse>('/api/proposals'),

  // proposal apply / reject — dispatches to the source save/route path (A1).
  // Adds no new write primitive; inherits every source-workflow safety guarantee.
  applyProposal: (id: string) =>
    fetchWithBody<ApplyProposalResult>('POST', '/api/proposals/apply', { id }),
  applyProposalBatch: (ids: string[]) =>
    fetchWithBody<ApplyBatchResponse>('POST', '/api/proposals/apply-batch', { ids }),
  rejectProposal: (id: string) =>
    fetchWithBody<ApplyProposalResult>('POST', '/api/proposals/reject', { id }),

  // tool / MCP connections (read-only readiness inventory; no tool execution)
  getToolConnectionStatus: () => get<ToolConnectionStatusResponse>('/api/tools/status'),

  // OpenClaw / NemoClaw runtime readiness (read-only; v0 launches nothing)
  getRuntimeStatus: () => get<RuntimeStatusResponse>('/api/runtime/status'),

  // NemoClaw/OpenShell health probe — explicit, opt-in reachability check only.
  // Unlocks nothing; starts no runtime; loading the cached "last" result is not a probe.
  probeNemoclawRuntime: (payload?: NemoclawProbeRequest) =>
    fetchWithBody<NemoclawProbeResponse>('POST', '/api/runtime/probe/nemoclaw', payload ?? {}),
  getLastNemoclawProbe: () => get<NemoclawLastProbeResponse>('/api/runtime/probe/nemoclaw/last'),

  // NemoClaw/OpenShell policy inspection — read-only summarized view of the configured
  // policy file. Does not enforce policy, start the runtime, or enable any capability.
  getNemoclawPolicy: () => get<NemoclawPolicyResponse>('/api/runtime/policy/nemoclaw'),

  // Guardrail readiness — read-only correlation of runtime status + last probe +
  // policy inspection + mode policy. Enforces nothing, unlocks nothing, runs no fresh
  // probe (reads the cached last probe only); refreshing it triggers no health probe.
  getGuardrailReadiness: () => get<GuardrailReadinessResponse>('/api/runtime/guardrail-readiness'),

  // Runtime bridge contract — DRY-RUN validator for a future bridge request. Validates
  // shape + mode + readiness + a permission-gateway dry-run classification. Executes
  // nothing, calls no runtime, unlocks nothing; a valid request is not an approval to run.
  validateRuntimeBridgeRequest: (payload: RuntimeBridgeValidationRequest) =>
    fetchWithBody<RuntimeBridgeValidationResponse>('POST', '/api/runtime/bridge/validate', payload),

  // permission gateway (deny-by-default classification; v0 executes nothing)
  getPermissionPolicies: () => get<PermissionPolicyResponse>('/api/permissions/policies'),
  evaluateToolRequest: (payload: ToolRequestEvaluationRequest) =>
    fetchWithBody<ToolRequestEvaluationResponse>('POST', '/api/permissions/evaluate', payload),
  getPermissionLogs: (params?: PermissionLogQuery) => {
    const q = new URLSearchParams();
    if (params?.limit != null)        q.set('limit', String(params.limit));
    if (params?.tool)                 q.set('tool', params.tool);
    if (params?.decision)             q.set('decision', params.decision);
    const qs = q.toString();
    return get<PermissionEvaluationLogsResponse>(`/api/permissions/logs${qs ? `?${qs}` : ''}`);
  },
  executePermissionTool: (payload: ToolExecutionRequest) =>
    fetchWithBody<ToolExecutionResponse>('POST', '/api/permissions/execute', payload),

  // agent modes (backend-enforced policy; read-only)
  getAgentModes: () => get<AgentModesResponse>('/api/agent/modes'),

  // agent tool requests (evaluate-only via the permission gateway; never executes)
  // Returns either an evaluated record or a blocked-by-mode response (HTTP 200).
  createAgentToolRequest: (payload: CreateAgentToolRequestRequest, operatorToken?: string) =>
    fetchWithBody<CreateAgentToolRequestResult>('POST', '/api/agent/tool-request', payload,
      operatorToken ? { 'X-Brain-Approval-Token': operatorToken } : undefined),
  listAgentToolRequests: (params?: { limit?: number }) => {
    const qs = params?.limit != null ? `?limit=${params.limit}` : '';
    return get<AgentToolRequestListResponse>(`/api/agent/tool-requests${qs}`);
  },

  // Approval mutations authenticate only with the dedicated operator header.
  // The caller owns the token; the API layer never stores or logs it.
  listToolApprovals: (operatorToken: string, params?: { limit?: number }) => {
    const qs = params?.limit != null ? `?limit=${params.limit}` : '';
    return getWithHeaders<ToolApprovalListResponse>(`/api/tool-approvals${qs}`, {
      'X-Brain-Approval-Token': operatorToken,
    });
  },
  approveToolApproval: (id: string, payload: ApproveToolApprovalRequest, operatorToken: string) =>
    fetchWithBody<ToolApproval>('POST', `/api/tool-approvals/${encodeURIComponent(id)}/approve`, payload, {
      'X-Brain-Approval-Token': operatorToken,
    }),
  rejectToolApproval: (id: string, payload: RejectToolApprovalRequest, operatorToken: string) =>
    fetchWithBody<ToolApproval>('POST', `/api/tool-approvals/${encodeURIComponent(id)}/reject`, payload, {
      'X-Brain-Approval-Token': operatorToken,
    }),
  executeToolApproval: (id: string, operatorToken: string) =>
    fetchWithBody<ToolApproval>('POST', `/api/tool-approvals/${encodeURIComponent(id)}/execute`, {}, {
      'X-Brain-Approval-Token': operatorToken,
    }),

  // chat / AI consolidation (manual paste/import; vault write only on explicit save)
  createConsolidationDraft: (payload: CreateConsolidationDraftRequest) =>
    fetchWithBody<ConsolidationDraft>('POST', '/api/consolidation/drafts', payload),
  listConsolidationDrafts:  ()                => get<ConsolidationDraftsResponse>('/api/consolidation/drafts'),
  getConsolidationDraft:    (id: string)      => get<ConsolidationDraft>(`/api/consolidation/drafts/${id}`),
  updateConsolidationDraft: (id: string, p: UpdateConsolidationDraftRequest) =>
    fetchWithBody<ConsolidationDraft>('PATCH', `/api/consolidation/drafts/${id}`, p),
  saveConsolidationDraft:   (id: string)      =>
    fetchWithBody<SaveConsolidationDraftResponse>('POST', `/api/consolidation/drafts/${id}/save`, {}),
  assistConsolidationDraft: (id: string, modelTier: DraftAssistModelTier) =>
    fetchWithBody<ConsolidationAssistPreview>('POST', `/api/consolidation/drafts/${id}/assist`, { modelTier }),

  // research (manual capture; vault write only on explicit save)
  createResearchDraft: (payload: CreateResearchDraftRequest) =>
    fetchWithBody<ResearchDraft>('POST', '/api/research/drafts', payload),
  listResearchDrafts:  ()                => get<ResearchDraftsResponse>('/api/research/drafts'),
  getResearchDraft:    (id: string)      => get<ResearchDraft>(`/api/research/drafts/${id}`),
  updateResearchDraft: (id: string, p: UpdateResearchDraftRequest) =>
    fetchWithBody<ResearchDraft>('PATCH', `/api/research/drafts/${id}`, p),
  saveResearchDraft:   (id: string)      =>
    fetchWithBody<SaveResearchDraftResponse>('POST', `/api/research/drafts/${id}/save`, {}),
  assistResearchDraft: (id: string, modelTier: DraftAssistModelTier) =>
    fetchWithBody<ResearchAssistPreview>('POST', `/api/research/drafts/${id}/assist`, { modelTier }),

  // email intake (manual paste/import; vault write only on explicit save)
  createEmailIntakeDraft: (payload: CreateEmailIntakeDraftRequest) =>
    fetchWithBody<EmailIntakeDraft>('POST', '/api/email-intake/drafts', payload),
  listEmailIntakeDrafts:  ()                => get<EmailIntakeDraftsResponse>('/api/email-intake/drafts'),
  getEmailIntakeDraft:    (id: string)      => get<EmailIntakeDraft>(`/api/email-intake/drafts/${id}`),
  updateEmailIntakeDraft: (id: string, p: UpdateEmailIntakeDraftRequest) =>
    fetchWithBody<EmailIntakeDraft>('PATCH', `/api/email-intake/drafts/${id}`, p),
  saveEmailIntakeDraft:   (id: string)      =>
    fetchWithBody<SaveEmailIntakeDraftResponse>('POST', `/api/email-intake/drafts/${id}/save`, {}),
  assistEmailIntakeDraft: (id: string, modelTier: DraftAssistModelTier) =>
    fetchWithBody<EmailIntakeAssistPreview>('POST', `/api/email-intake/drafts/${id}/assist`, { modelTier }),

  // Gmail (READ-ONLY). No mutation endpoint exists on the backend.
  gmailStatus:  ()                    => get<GmailStatusResponse>('/api/gmail/status'),
  gmailSearch:  (payload: GmailSearchRequest) =>
    fetchWithBody<GmailSearchResponse>('POST', '/api/gmail/search', payload),
  gmailMessage: (messageId: string)   =>
    get<GmailMessageResponse>(`/api/gmail/messages/${encodeURIComponent(messageId)}`),
  gmailImport:  (payload: GmailImportRequest) =>
    fetchWithBody<GmailImportResponse>('POST', '/api/gmail/import', payload),

  // Google Calendar (READ-ONLY). No event create/update/delete function exists.
  googleCalendarStatus: () => get<GoogleCalendarStatusResponse>('/api/calendar/google/status'),
  googleCalendarEvents: (timeMin?: string, timeMax?: string) => {
    const q = new URLSearchParams();
    if (timeMin) q.set('timeMin', timeMin);
    if (timeMax) q.set('timeMax', timeMax);
    const suffix = q.toString() ? `?${q.toString()}` : '';
    return get<GoogleCalendarEventsResponse>(`/api/calendar/google/events${suffix}`);
  },
  googleCalendarReconcile: (timeMin?: string, timeMax?: string) => {
    const q = new URLSearchParams();
    if (timeMin) q.set('timeMin', timeMin);
    if (timeMax) q.set('timeMax', timeMax);
    const suffix = q.toString() ? `?${q.toString()}` : '';
    return get<CalendarReconcileResponse>(`/api/calendar/google/reconcile${suffix}`);
  },

  // Time-boxed browser research (C1). Guardrailed; fetches fail closed.
  startResearchSession: (payload: StartResearchSessionRequest) =>
    fetchWithBody<ResearchSessionResponse>('POST', '/api/research/sessions', payload),
  listResearchSessions: () => get<ResearchSessionsResponse>('/api/research/sessions'),
  getResearchSession: (id: string) =>
    get<ResearchSessionResponse>(`/api/research/sessions/${encodeURIComponent(id)}`),
  openResearchPage: (id: string, url: string) =>
    fetchWithBody<ResearchSessionResponse>(
      'POST', `/api/research/sessions/${encodeURIComponent(id)}/open`, { url }),
  stopResearchSession: (id: string) =>
    fetchWithBody<ResearchSessionResponse>(
      'POST', `/api/research/sessions/${encodeURIComponent(id)}/stop`, {}),
  searchInResearchSession: (id: string, query: string, limit?: number) =>
    fetchWithBody<ResearchSearchResponse>(
      'POST', `/api/research/sessions/${encodeURIComponent(id)}/search`, { query, limit }),
  researchDraftPayload: (id: string) =>
    get<ResearchDraftPayloadResponse>(
      `/api/research/sessions/${encodeURIComponent(id)}/draft-payload`),

  chatCapturePayload: (id: string, captureIndex?: number) => {
    const q = captureIndex === undefined ? '' : `?captureIndex=${captureIndex}`;
    return get<ChatCapturePayloadResponse>(
      `/api/research/sessions/${encodeURIComponent(id)}/chat-payload${q}`);
  },

  // Computer-use (MVP v7). Mutating calls require the operator token.
  computerUseStatus: () => get<ComputerUseStatusResponse>('/api/computer-use/status'),
  stopComputerUseSession: (id: string) =>
    fetchWithBody<ComputerUseSessionResponse>(
      'POST', `/api/computer-use/sessions/${encodeURIComponent(id)}/stop`, {}),
  /**
   * Request a computer-use session. This does NOT start one.
   *
   * Direct start was removed: it let the most privileged capability in the app
   * skip the gateway, and meant the documented Assist-mode requirement was never
   * enforced. The session is now queued as a `computer.start_session` approval,
   * which the operator must then approve and execute.
   */
  requestComputerUseSession: (
    payload: { task: string; allowedWindows: string[]; budgetSeconds?: number },
    token: string,
  ) =>
    fetchWithBody<CreateAgentToolRequestResult>('POST', '/api/agent/tool-request', {
      tool: 'computer.start_session',
      args: payload,
      mode: 'assist',
      reason: payload.task,
      requestedBy: 'computer-use-ui',
    }, { 'X-Brain-Approval-Token': token }),
  observeComputerUse: (id: string, token: string) =>
    fetchWithBody<ComputerUseObserveResponse>(
      'POST', `/api/computer-use/sessions/${encodeURIComponent(id)}/observe`, {},
      { 'X-Brain-Approval-Token': token }),
  clickComputerUse: (
    id: string, x: number, y: number, token: string, confirmRisk?: string,
  ) =>
    fetchWithBody<ComputerUseActionResponse>(
      'POST', `/api/computer-use/sessions/${encodeURIComponent(id)}/click`,
      { x, y, confirmRisk }, { 'X-Brain-Approval-Token': token }),
  typeComputerUse: (id: string, text: string, token: string, confirmRisk?: string) =>
    fetchWithBody<ComputerUseActionResponse>(
      'POST', `/api/computer-use/sessions/${encodeURIComponent(id)}/type`,
      { text, confirmRisk }, { 'X-Brain-Approval-Token': token }),


  // ── MVP v10 read-only integrations. GET only; no write path exists. ──────────
  githubStatus: () => get<GitHubStatusResponse>('/api/github/status'),
  githubRepos: (limit?: number) =>
    get<GitHubReposResponse>(`/api/github/repos${limit != null ? `?limit=${limit}` : ''}`),
  githubCommits: (repo: string, limit?: number) => {
    const q = new URLSearchParams({ repo });
    if (limit != null) q.set('limit', String(limit));
    return get<GitHubCommitsResponse>(`/api/github/commits?${q}`);
  },
  githubIssues: (repo: string, state?: string, limit?: number) => {
    const q = new URLSearchParams({ repo });
    if (state) q.set('state', state);
    if (limit != null) q.set('limit', String(limit));
    return get<GitHubIssuesResponse>(`/api/github/issues?${q}`);
  },

  driveFiles: (search?: string, limit?: number) => {
    const q = new URLSearchParams();
    if (search) q.set('q', search);
    if (limit != null) q.set('limit', String(limit));
    const qs = q.toString();
    return get<DriveFilesResponse>(`/api/drive/files${qs ? `?${qs}` : ''}`);
  },
  driveDocument: (fileId: string) =>
    get<DriveDocumentResponse>(`/api/drive/files/${encodeURIComponent(fileId)}`),

  quercusStatus: () => get<QuercusStatusResponse>('/api/quercus/status'),
  quercusCourses: (limit?: number) =>
    get<QuercusCoursesResponse>(`/api/quercus/courses${limit != null ? `?limit=${limit}` : ''}`),
  quercusAssignments: (courseId: string, limit?: number) => {
    const q = new URLSearchParams({ courseId });
    if (limit != null) q.set('limit', String(limit));
    return get<QuercusAssignmentsResponse>(`/api/quercus/assignments?${q}`);
  },
  quercusAnnouncements: (courseId: string, limit?: number) => {
    const q = new URLSearchParams({ courseId });
    if (limit != null) q.set('limit', String(limit));
    return get<QuercusAnnouncementsResponse>(`/api/quercus/announcements?${q}`);
  },

  // Local vault search. Embeddings come from local Ollama, so no vault text
  // leaves the machine; without the model it degrades to lexical and says so.
  vaultSearch: (query: string, limit?: number) => {
    const q = new URLSearchParams({ q: query });
    if (limit != null) q.set('limit', String(limit));
    return get<VaultSearchResponse>(`/api/vault/search?${q}`);
  },
  vaultSearchStatus: () => get<VaultIndexStatusResponse>('/api/vault/search/status'),
  buildVaultSearchIndex: () =>
    fetchWithBody<BuildVaultIndexResponse>('POST', '/api/vault/search/index', {}),

  getBusinessPipeline: () => get<BusinessPipelineResponse>('/api/vault/business-pipeline'),

  // Vault graph (D3d). Read-only; derived from wikilinks.
  vaultGraph: (exportPath?: string) => {
    const q = exportPath ? `?exportPath=${encodeURIComponent(exportPath)}` : '';
    return get<VaultGraphResponse>(`/api/vault/graph${q}`);
  },

  // Local voice (D1). Audio never leaves this machine.
  voiceStatus: () => get<VoiceStatusResponse>('/api/agent/voice/status'),
  transcribeAudio: async (blob: Blob, filename = 'clip.webm'): Promise<TranscribeResponse> => {
    const form = new FormData();
    form.append('file', blob, filename);
    const res = await fetch(`${BASE}/api/agent/transcribe`, { method: 'POST', body: form });
    if (!res.ok) {
      let detail = `Transcription failed (${res.status})`;
      try { const j = await res.json(); if (j?.detail) detail = j.detail; } catch { /* ignore */ }
      throw new Error(detail);
    }
    return res.json();
  },

  // health / config
  health:       ()                    => get<BackendHealth>('/api/health'),
  config:       ()                    => get<BackendConfig>('/api/config'),
  updateConfig: (cfg: ConfigUpdate)   => fetchWithBody<BackendConfig>('PUT', '/api/config', cfg),

  // brain commands
  commands:     ()                    => get<string[]>('/api/brain/commands'),
  // `args` is accepted only for commands with a declared schema (project-closeout,
  // new-repo-scaffold, archive-hackathon); the backend validates and refuses others.
  runBrain: (command: string, args?: Record<string, string>) =>
    fetchWithBody<BrainRunResult>('POST', '/api/brain/run', args ? { command, args } : { command }),

  // entity creation
  createProject: (payload: CreateProjectRequest) =>
    fetchWithBody<EntityCreateResponse>('POST', '/api/entities/projects', payload),
  createCourse: (payload: CreateCourseRequest) =>
    fetchWithBody<EntityCreateResponse>('POST', '/api/entities/courses', payload),
  createHackathon: (payload: CreateHackathonRequest) =>
    fetchWithBody<EntityCreateResponse>('POST', '/api/entities/hackathons', payload),
  createBusinessArea: (payload: CreateBusinessRequest) =>
    fetchWithBody<EntityCreateResponse>('POST', '/api/entities/business', payload),

  // intake / staging
  uploadIntakeFiles: (files: File[]) => {
    const form = new FormData();
    for (const f of files) form.append('files', f);
    return uploadForm<UploadResponse>('/api/intake/upload', form);
  },
  getStagedFiles:   ()               => get<StagedFilesResponse>('/api/intake/staged'),
  deleteStagedFile: (id: string)     => del<DeleteStagedResponse>(`/api/intake/staged/${id}`),

  // proposals
  getIntakeProposals: ()                                            => get<ProposalsResponse>('/api/intake/proposals'),
  updateIntakeProposal: (fileId: string, p: ProposalUpdatePayload) => fetchWithBody<ClassificationProposal>('PUT', `/api/intake/proposals/${fileId}`, p),
  approveIntakeProposal: (fileId: string)                          => fetchWithBody<ClassificationProposal>('POST', `/api/intake/proposals/${fileId}/approve`, {}),
  skipIntakeProposal: (fileId: string)                             => fetchWithBody<ClassificationProposal>('POST', `/api/intake/proposals/${fileId}/skip`, {}),
  approveIntakeProposalsBatch: (fileIds: string[])                 => fetchWithBody<BatchApproveResponse>('POST', '/api/intake/proposals/approve-batch', { fileIds }),
  routeIntakeProposal: (fileId: string)                           => fetchWithBody<RouteResponse>('POST', `/api/intake/proposals/${fileId}/route`, {}),

  // archive
  archiveStagedFile:      (fileId: string) => fetchWithBody<ArchiveResponse>('POST', `/api/intake/staged/${fileId}/archive`, {}),
  getArchivedIntakeFiles: ()               => get<ArchivedFilesResponse>('/api/intake/archived'),

  // vault (read-only + safe task/calendar writes)
  getVaultTasks:      ()             => get<VaultTasksResponse>('/api/vault/tasks'),
  createVaultTask:    (payload: CreateVaultTaskRequest) =>
    fetchWithBody<CreateVaultTaskResponse>('POST', '/api/vault/tasks', payload),
  updateVaultTaskStatus: (taskId: string, status: TaskStatus) =>
    fetchWithBody<TaskStatusUpdateResponse>('PATCH', `/api/vault/tasks/${encodeURIComponent(taskId)}/status`, { status }),

  // calendar candidates
  getCalendarCandidates: () =>
    get<CalendarCandidatesResponse>('/api/vault/calendar-candidates'),
  createCalendarCandidatesFile: () =>
    fetchWithBody<CalendarCandidatesResponse>('POST', '/api/vault/calendar-candidates/create', {}),
  createCalendarCandidate: (payload: CreateCalendarCandidateRequest) =>
    fetchWithBody<UpdateCalendarCandidateResponse>('POST', '/api/vault/calendar-candidates', payload),
  updateCalendarCandidate: (candidateId: string, payload: UpdateCalendarCandidateRequest) =>
    fetchWithBody<UpdateCalendarCandidateResponse>('PATCH', `/api/vault/calendar-candidates/${encodeURIComponent(candidateId)}`, payload),
  approveCalendarCandidate: (candidateId: string) =>
    fetchWithBody<UpdateCalendarCandidateResponse>('POST', `/api/vault/calendar-candidates/${encodeURIComponent(candidateId)}/approve`, {}),
  getVaultSummary:    ()             => get<VaultSummary>('/api/vault/summary'),
  getVaultProjects:   ()             => get<VaultProjectsResponse>('/api/vault/projects'),
  getVaultCourses:    ()             => get<VaultCoursesResponse>('/api/vault/courses'),
  getVaultHackathons: ()             => get<VaultHackathonsResponse>('/api/vault/hackathons'),
  getVaultBusiness:   ()             => get<VaultBusinessResponse>('/api/vault/business'),
  getVaultOpsFile:    (kind: string) => get<VaultOpsFile>(`/api/vault/ops/${encodeURIComponent(kind)}`),

  // resume pipeline
  getVaultResumePipeline: () => get<ResumePipelineResponse>('/api/vault/resume-pipeline'),
  createResumePipelineFile: () =>
    fetchWithBody<ResumePipelineResponse>('POST', '/api/vault/resume-pipeline/create', {}),
  createResumePipelineItem: (payload: CreateResumePipelineItemRequest) =>
    fetchWithBody<CreateResumePipelineItemResponse>('POST', '/api/vault/resume-pipeline', payload),
  updateResumePipelineStatus: (itemId: string, status: ResumePipelineStatus) =>
    fetchWithBody<UpdateResumePipelineStatusResponse>(
      'PATCH',
      `/api/vault/resume-pipeline/${encodeURIComponent(itemId)}/status`,
      { status },
    ),
  updateResumePipelineItem: (itemId: string, payload: UpdateResumePipelineItemRequest) =>
    fetchWithBody<UpdateResumePipelineItemResponse>(
      'PATCH',
      `/api/vault/resume-pipeline/${encodeURIComponent(itemId)}`,
      payload,
    ),

  // backfill
  getVaultBackfill: () => get<BackfillResponse>('/api/vault/backfill'),
  createBackfillFile: () =>
    fetchWithBody<BackfillResponse>('POST', '/api/vault/backfill/create', {}),
  createBackfillItem: (payload: CreateBackfillItemRequest) =>
    fetchWithBody<CreateBackfillItemResponse>('POST', '/api/vault/backfill', payload),
  updateBackfillStatus: (itemId: string, status: BackfillStatus) =>
    fetchWithBody<UpdateBackfillStatusResponse>(
      'PATCH',
      `/api/vault/backfill/${encodeURIComponent(itemId)}/status`,
      { status },
    ),
  updateBackfillItem: (itemId: string, payload: UpdateBackfillItemRequest) =>
    fetchWithBody<UpdateBackfillItemResponse>(
      'PATCH',
      `/api/vault/backfill/${encodeURIComponent(itemId)}`,
      payload,
    ),

  // AI classification
  aiClassifyProposal:       (fileId: string)        => fetchWithBody<ClassificationProposal>('POST', `/api/intake/proposals/${fileId}/ai-classify`, {}),
  aiClassifyProposalsBatch: (fileIds: string[])      => fetchWithBody<BatchAiClassifyResponse>('POST', '/api/intake/proposals/ai-classify-batch', { fileIds }),

  // local agent
  getAgentStatus:   ()                          => get<AgentStatus>('/api/agent/status'),
  sendAgentMessage: (payload: AgentChatRequest) => fetchWithBody<AgentChatResponse>('POST', '/api/agent/chat', payload),

  // escalation queue
  getVaultEscalations:        ()                                         => get<EscalationResponse>('/api/vault/escalations'),
  createEscalationQueueFile:  ()                                         => fetchWithBody<EscalationResponse>('POST', '/api/vault/escalations/create', {}),
  createEscalationItem:       (payload: CreateEscalationRequest)         => fetchWithBody<EscalationResponse>('POST', '/api/vault/escalations', payload),
  updateEscalationStatus:     (itemId: string, status: EscalationStatus) =>
    fetchWithBody<UpdateEscalationStatusResponse>(
      'PATCH',
      `/api/vault/escalations/${encodeURIComponent(itemId)}/status`,
      { status },
    ),
  updateEscalationItem: (itemId: string, payload: UpdateEscalationItemRequest) =>
    fetchWithBody<UpdateEscalationItemResponse>(
      'PATCH',
      `/api/vault/escalations/${encodeURIComponent(itemId)}`,
      payload,
    ),

  // conversations
  createConversation:  (title?: string)     => fetchWithBody<ConversationSummary>('POST', '/api/conversations', { title: title ?? null }),
  listConversations:   ()                   => get<ConversationListResponse>('/api/conversations'),
  getConversation:     (id: string)         => get<ConversationDetail>(`/api/conversations/${id}`),
  deleteConversation:  (id: string)         => del<DeleteConversationResponse>(`/api/conversations/${id}`),
};

/**
 * Stream a local-agent chat turn via SSE (POST /api/agent/chat/stream).
 *
 * SSE events:  meta | token | done | error
 * EventSource is not used because it doesn't support POST — we parse SSE
 * manually from a ReadableStream fetch response.
 */
/**
 * `signal` implements PRD §17's "Stop current action". Until it existed there
 * was no AbortController anywhere in the app, so a chat turn could not be
 * stopped once it started — the only option was to wait it out.
 *
 * An abort is a user action, not a failure, so it is reported through onDone
 * rather than onError: whatever tokens already arrived stay on screen.
 */
export async function streamAgentMessage(
  payload:  AgentChatRequest,
  handlers: StreamHandlers,
  signal?:  AbortSignal,
): Promise<void> {
  if (signal?.aborted) { handlers.onDone({ ok: false, durationMs: 0, aborted: true }); return; }

  let res: Response;
  try {
    res = await fetch(`${BASE}/api/agent/chat/stream`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
      signal,
    });
  } catch (err) {
    if (signal?.aborted || (err instanceof DOMException && err.name === 'AbortError')) {
      handlers.onDone({ ok: false, durationMs: 0, aborted: true });
      return;
    }
    handlers.onError({ message: err instanceof Error ? err.message : 'Network error.' });
    return;
  }

  if (!res.ok) {
    const msg = await parseError(res);
    handlers.onError({ message: msg });
    return;
  }

  if (!res.body) {
    handlers.onError({ message: 'No response body.' });
    return;
  }

  const reader  = res.body.getReader();
  const decoder = new TextDecoder();
  let   buffer  = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by double newlines.
      const parts = buffer.split('\n\n');
      buffer = parts.pop() ?? '';

      for (const block of parts) {
        const trimmed = block.trim();
        if (!trimmed) continue;

        let eventName = '';
        let dataStr   = '';
        for (const line of trimmed.split('\n')) {
          if      (line.startsWith('event: ')) eventName = line.slice(7).trim();
          else if (line.startsWith('data: '))  dataStr   = line.slice(6).trim();
        }

        if (!dataStr) continue;
        try {
          const data = JSON.parse(dataStr);
          if      (eventName === 'meta')  handlers.onMeta(data);
          else if (eventName === 'token') handlers.onToken((data as { text: string }).text ?? '');
          else if (eventName === 'structured') handlers.onStructured?.(data as AgentStructuredOutput);
          else if (eventName === 'done')  handlers.onDone(data);
          else if (eventName === 'error') handlers.onError(data);
        } catch { /* ignore malformed SSE */ }
      }
    }
  } catch (err) {
    // Aborting mid-stream throws here too. Tokens already delivered stay on
    // screen; stopping is a choice, not an error.
    if (signal?.aborted || (err instanceof DOMException && err.name === 'AbortError')) {
      handlers.onDone({ ok: false, durationMs: 0, aborted: true });
    } else {
      handlers.onError({ message: err instanceof Error ? err.message : 'Stream read error.' });
    }
  } finally {
    reader.releaseLock();
  }
}
