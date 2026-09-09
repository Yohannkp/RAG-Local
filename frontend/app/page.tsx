"use client";

import { useState } from "react";
import { Lock } from "lucide-react";
import { HealthBanner } from "@/components/HealthBanner";
import { DocumentLibrary } from "@/components/documents/DocumentLibrary";
import { ChatWindow } from "@/components/chat/ChatWindow";

export default function Home() {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [documentCount, setDocumentCount] = useState(0);

  return (
    <div className="flex h-screen flex-col">
      <HealthBanner />
      <header className="flex items-center gap-2.5 border-b px-4 py-3">
        <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Lock className="size-3.5" />
        </div>
        <h1 className="text-sm font-semibold">RAG Local</h1>
        <span className="text-xs text-muted-foreground">
          — assistant documentaire 100% privé
        </span>
      </header>
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-72 shrink-0 border-r p-3">
          <DocumentLibrary
            selectedIds={selectedIds}
            onSelectionChange={setSelectedIds}
            onDocumentCountChange={setDocumentCount}
          />
        </aside>
        <main className="flex-1 overflow-hidden">
          <ChatWindow selectedIds={selectedIds} documentCount={documentCount} />
        </main>
      </div>
    </div>
  );
}
