export interface Identity {
  role: "guest" | "admin";
  csrf_token: string;
  provider: "fake" | "online";
  health_targets: string[];
}
export interface Project {
  id: string;
  name: string;
  description: string;
}
export interface Citation {
  id: string;
  content: string;
  heading: string;
  line_start: number;
  line_end: number;
  document: string;
  version: string;
  source: string;
}
export interface Result {
  summary: string;
  facts: string[];
  causes: { text: string; citation_ids: string[] }[];
  steps: string[];
  missing_information: string[];
  citation_ids: string[];
}
export interface Draft {
  id: string;
  version: number;
  title: string;
  description: string;
  status: string;
}
export interface Task {
  id: string;
  title: string;
  project_id: string;
  mode: string;
  status: string;
  created_at: string;
  result: Result | null;
  messages: { id: string; role: string; content: string }[];
  events: {
    id: number;
    kind: string;
    payload: { message?: string; observation?: unknown };
  }[];
  citations: Citation[];
  draft: Draft | null;
  runs: { retryable: boolean }[];
}
export interface Ticket {
  id: string;
  title: string;
  description: string;
  status: string;
  sandbox: boolean;
  task_id: string;
  created_at: string;
  evidence: { result?: Result; citations: Citation[] };
  approvals?: { decision: string; created_at: string }[];
}
export interface Document {
  id: string;
  logical_key: string;
  project_id: string;
  enabled: boolean;
  active_version: string | null;
  versions: {
    id: string;
    label: string;
    status: string;
    error: string | null;
    content_hash: string;
  }[];
}
export interface Usage {
  items: {
    id: string;
    kind: string;
    model: string;
    success: boolean;
    input_tokens: number | null;
    output_tokens: number | null;
    cost: number | null;
    elapsed_ms: number;
    created_at: string;
  }[];
  provider: string;
  runs: {
    id: string;
    created_at: string;
    started_at: string | null;
    finished_at: string | null;
  }[];
}
