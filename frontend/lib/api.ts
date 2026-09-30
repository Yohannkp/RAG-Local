import type { DocumentItem } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function fetchDocuments(): Promise<DocumentItem[]> {
  const res = await fetch(`${API_URL}/api/documents`);
  if (!res.ok) throw new Error("Impossible de charger les documents");
  return res.json();
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_URL}/api/documents`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Échec de l'upload" }));
    throw new Error(body.detail ?? "Échec de l'upload");
  }
  return res.json();
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/documents/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Échec de la suppression");
}

export interface HealthStatus {
  ollama_reachable: boolean;
  models: Record<string, boolean>;
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_URL}/api/health`);
  if (!res.ok) throw new Error("Backend injoignable");
  return res.json();
}

export interface LocalSearchResult {
  path: string;
  filename: string;
  directory: string;
  extension: string;
  snippet: string;
  score: number;
  modified_at?: string;
}

export type LocalChatSource = LocalSearchResult;

export interface LocalConfig {
  default_root: string;
  ignored_dirs: string[];
}

export interface LocalIndexProgress {
  status: "idle" | "scanning" | "completed" | "error";
  root: string | null;
  current_file: string | null;
  current_action: string;
  processed: number;
  total: number;
  percent: number;
  indexed: number;
  skipped: number;
  error: string | null;
}

export async function fetchLocalConfig(): Promise<LocalConfig> {
  const res = await fetch(`${API_URL}/api/local/config`);
  if (!res.ok) throw new Error("Impossible de charger la configuration locale");
  return res.json();
}

export async function fetchLocalIndexProgress(): Promise<LocalIndexProgress> {
  const res = await fetch(`${API_URL}/api/local/index/progress`, { cache: "no-store" });
  if (!res.ok) throw new Error("Impossible de lire l'avancement");
  return res.json();
}

export async function indexLocalFiles(rootPath: string, maxFiles = 5000): Promise<{ indexed: number; root: string }> {
  const res = await fetch(`${API_URL}/api/local/index`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ root_path: rootPath, max_files: maxFiles }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Échec de l'indexation locale" }));
    throw new Error(body.detail ?? "Échec de l'indexation locale");
  }
  return res.json();
}

export async function searchLocalFiles(
  query: string,
  limit = 5,
  rootPath?: string,
  directory?: string,
  extensions?: string[],
  modifiedAfter?: string,
  modifiedBefore?: string,
): Promise<LocalSearchResult[]> {
  const res = await fetch(`${API_URL}/api/local/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      limit,
      root_path: rootPath ?? null,
      directory: directory || null,
      extensions: extensions && extensions.length > 0 ? extensions : null,
      modified_after: modifiedAfter || null,
      modified_before: modifiedBefore || null,
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Recherche locale impossible" }));
    throw new Error(body.detail ?? "Recherche locale impossible");
  }
  return res.json();
}
