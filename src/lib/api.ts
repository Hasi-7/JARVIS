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
  repoPath?: string | null;
}

export interface CreateCourseRequest {
  code: string;
  name?: string | null;
}

export interface CreateHackathonRequest {
  name: string;
  date?: string | null;
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
}

export interface StreamError {
  message: string;
}

export interface StreamHandlers {
  onMeta:  (meta:  StreamMeta)  => void;
  onToken: (text:  string)      => void;
  onDone:  (done:  StreamDone)  => void;
  onError: (error: StreamError) => void;
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

export interface VaultProject {
  id: string;
  name: string;
  wikiPath: string | null;
  rawPath: string | null;
  status: string;
  lastModified: string | null;
  preview: string | null;
}

export interface VaultProjectsResponse {
  projects: VaultProject[];
}

export interface VaultCourse {
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

export interface VaultHackathon {
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

export interface VaultBusinessItem {
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

// ── HTTP helpers ──────────────────────────────────────────────────────────────

async function parseError(res: Response): Promise<string> {
  return res.json()
    .then((d: { detail?: unknown }) =>
      typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail)
    )
    .catch(() => res.statusText);
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<T>;
}

async function fetchWithBody<T>(method: string, path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<T>;
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<T>;
}

async function uploadForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST', body: form });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<T>;
}

// ── API surface ───────────────────────────────────────────────────────────────

export const api = {
  // health / config
  health:       ()                    => get<BackendHealth>('/api/health'),
  config:       ()                    => get<BackendConfig>('/api/config'),
  updateConfig: (cfg: ConfigUpdate)   => fetchWithBody<BackendConfig>('PUT', '/api/config', cfg),

  // brain commands
  commands:     ()                    => get<string[]>('/api/brain/commands'),
  runBrain:     (command: string)     => fetchWithBody<BrainRunResult>('POST', '/api/brain/run', { command }),

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

  // AI classification
  aiClassifyProposal:       (fileId: string)        => fetchWithBody<ClassificationProposal>('POST', `/api/intake/proposals/${fileId}/ai-classify`, {}),
  aiClassifyProposalsBatch: (fileIds: string[])      => fetchWithBody<BatchAiClassifyResponse>('POST', '/api/intake/proposals/ai-classify-batch', { fileIds }),

  // local agent
  getAgentStatus:   ()                          => get<AgentStatus>('/api/agent/status'),
  sendAgentMessage: (payload: AgentChatRequest) => fetchWithBody<AgentChatResponse>('POST', '/api/agent/chat', payload),

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
export async function streamAgentMessage(
  payload:  AgentChatRequest,
  handlers: StreamHandlers,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/agent/chat/stream`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
  } catch (err) {
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
          else if (eventName === 'done')  handlers.onDone(data);
          else if (eventName === 'error') handlers.onError(data);
        } catch { /* ignore malformed SSE */ }
      }
    }
  } catch (err) {
    handlers.onError({ message: err instanceof Error ? err.message : 'Stream read error.' });
  } finally {
    reader.releaseLock();
  }
}
