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
