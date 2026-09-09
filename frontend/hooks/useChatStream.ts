"use client";

import { useCallback, useRef, useState } from "react";
import { API_URL } from "@/lib/api";
import type { ChatMessage, Source } from "@/lib/types";

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

// Au-delà de ce délai sans le moindre token, on suppose qu'Ollama est en
// train de charger le modèle en VRAM (fréquent au premier message après un
// redémarrage) plutôt qu'un vrai blocage, et on l'affiche à l'utilisateur.
const WARMUP_HINT_DELAY_MS = 4000;

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isWarmingUp, setIsWarmingUp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (text: string, docIds: string[]) => {
      setError(null);
      const history = messages.map((m) => ({ role: m.role, content: m.content }));
      setMessages((prev) => [
        ...prev,
        { role: "user", content: text },
        { role: "assistant", content: "", sources: [] },
      ]);
      setIsStreaming(true);

      const controller = new AbortController();
      controllerRef.current = controller;
      const warmupTimer = setTimeout(() => setIsWarmingUp(true), WARMUP_HINT_DELAY_MS);

      try {
        const res = await fetch(`${API_URL}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, doc_ids: docIds, history }),
          signal: controller.signal,
        });
        if (!res.ok || !res.body) {
          throw new Error(`Le serveur a répondu avec une erreur (${res.status})`);
        }

        const reader = res.body.getReader();
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
              const sources: Source[] = JSON.parse(parsed.data);
              setMessages((prev) => {
                const next = [...prev];
                next[next.length - 1] = { ...next[next.length - 1], sources };
                return next;
              });
            } else if (parsed.event === "token") {
              clearTimeout(warmupTimer);
              setIsWarmingUp(false);
              const { text: tokenText } = JSON.parse(parsed.data);
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                next[next.length - 1] = { ...last, content: last.content + tokenText };
                return next;
              });
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setError((err as Error).message || "Une erreur est survenue");
        }
      } finally {
        clearTimeout(warmupTimer);
        setIsWarmingUp(false);
        setIsStreaming(false);
        controllerRef.current = null;
      }
    },
    [messages]
  );

  const stop = useCallback(() => {
    controllerRef.current?.abort();
  }, []);

  return { messages, isStreaming, isWarmingUp, error, sendMessage, stop };
}
