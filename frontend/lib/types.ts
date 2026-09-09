export interface DocumentItem {
  id: string;
  filename: string;
  file_type: "pdf" | "docx" | "txt";
  num_chunks: number;
  warning: string | null;
  created_at: string;
}

export interface Source {
  index: number;
  doc_id: string;
  filename: string;
  page_number: number | null;
  section_title: string | null;
  snippet: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
}
