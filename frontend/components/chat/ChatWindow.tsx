"use client";

import { useEffect, useRef, useState } from "react";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import dynamic from "next/dynamic";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useChatStream } from "@/hooks/useChatStream";
import type { Source } from "@/lib/types";
import { ChatInput } from "./ChatInput";
import { MessageBubble } from "./MessageBubble";

// react-pdf (via pdfjs-dist) touche des API navigateur (DOMMatrix) absentes
// cote serveur : ce composant ne doit jamais etre rendu pendant le SSR/build.
const SourceViewerDialog = dynamic(
  () => import("./SourceViewerDialog").then((m) => m.SourceViewerDialog),
  { ssr: false }
);

export function ChatWindow({ selectedIds }: { selectedIds: string[] }) {
  const { messages, isStreaming, isWarmingUp, error, sendMessage } = useChatStream();
  const [viewerSource, setViewerSource] = useState<Source | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-muted-foreground">
            <ShieldCheck className="size-8" />
            <p className="text-sm font-medium">
              Tout reste sur ta machine — aucune donnée n&apos;est envoyée à un
              service externe.
            </p>
            <p className="text-xs">
              Sélectionne un ou plusieurs documents à gauche, puis pose ta question.
            </p>
          </div>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-6">
            {messages.map((message, i) => (
              <MessageBubble
                key={i}
                message={message}
                isWarmingUp={isWarmingUp && i === messages.length - 1}
                onOpenSource={setViewerSource}
              />
            ))}
            <div ref={bottomRef} />
          </div>
        )}
        {error && (
          <Alert variant="destructive" className="mx-auto mt-4 max-w-3xl">
            <AlertTriangle className="size-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>
      <div className="mx-auto w-full max-w-3xl">
        <ChatInput
          onSend={(text) => sendMessage(text, selectedIds)}
          disabled={isStreaming}
          placeholder={
            selectedIds.length === 0
              ? "Sélectionne au moins un document pour commencer…"
              : undefined
          }
        />
      </div>
      <SourceViewerDialog
        source={viewerSource}
        onOpenChange={(open) => !open && setViewerSource(null)}
      />
    </div>
  );
}
