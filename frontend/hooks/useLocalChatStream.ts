"use client";

import { useCallback, useState } from "react";
import { API_URL, type LocalChatSource } from "@/lib/api";

interface LocalChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: LocalChatSource[];
}

interface LocalChatFilters {
  rootPath: string;
  directory?: string;
  extensions?: string[];
  modifiedAfter?: string;
  modifiedBefore?: string;
}

function parseSseBlock(block: string): { event: string; data: string } | null {
  const lines = block.split("\n");
  let event = "message";
  let data = "";
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  return data ? { event, data } : null;
}

export function useLocalChatStream() {
  const [messages, setMessages] = useState<LocalChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (text: string, filters: LocalChatFilters) => {
      setError(null);
      const history = messages.map(({ role, content }) => ({ role, content }));
      setMessages((previous) => [
        ...previous,
        { role: "user", content: text },
        { role: "assistant", content: "", sources: [] },
      ]);
      setIsStreaming(true);

      try {
        const response = await fetch(`${API_URL}/api/local/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: text,
            root_path: filters.rootPath || null,
            directory: filters.directory || null,
            extensions: filters.extensions?.length ? filters.extensions : null,
            modified_after: filters.modifiedAfter || null,
            modified_before: filters.modifiedBefore || null,
            history,
          }),
        });
        if (!response.ok || !response.body) {
          throw new Error(`Le serveur a répondu avec une erreur (${response.status})`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
          const blocks = buffer.split("\n\n");
          buffer = blocks.pop() ?? "";
          for (const block of blocks) {
            const parsed = parseSseBlock(block);
            if (!parsed) continue;
            if (parsed.event === "sources") {
              const sources: LocalChatSource[] = JSON.parse(parsed.data);
              setMessages((previous) => {
                const next = [...previous];
                next[next.length - 1] = { ...next[next.length - 1], sources };
                return next;
              });
            } else if (parsed.event === "token") {
              const { text: token } = JSON.parse(parsed.data);
              setMessages((previous) => {
                const next = [...previous];
                const last = next[next.length - 1];
                next[next.length - 1] = { ...last, content: last.content + token };
                return next;
              });
            }
          }
        }
      } catch (err) {
        setError((err as Error).message || "Une erreur est survenue");
      } finally {
        setIsStreaming(false);
      }
    },
    [messages]
  );

  return { messages, isStreaming, error, sendMessage };
}