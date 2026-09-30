"use client";

import { useEffect, useRef, useState } from "react";
import { Lock, Search, FolderSearch, Loader2, FolderOpen, FileUp } from "lucide-react";
import { HealthBanner } from "@/components/HealthBanner";
import { DocumentLibrary } from "@/components/documents/DocumentLibrary";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { Button } from "@/components/ui/button";
import { fetchLocalConfig, fetchLocalIndexProgress, indexLocalFiles, type LocalIndexProgress } from "@/lib/api";
import { useLocalChatStream } from "@/hooks/useLocalChatStream";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";

function getOpenFileUrl(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  if (/^[A-Za-z]:\//.test(normalized)) {
    return `file:///${normalized}`;
  }
  return `file://${normalized.startsWith("/") ? "" : "/"}${normalized}`;
}

export default function Home() {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [documentCount, setDocumentCount] = useState(0);
  const [mode, setMode] = useState<"documents" | "ordinateur">("documents");
  const [localRoot, setLocalRoot] = useState("C:\\");
  const [localQuery, setLocalQuery] = useState("");
  const [localDirectory, setLocalDirectory] = useState("");
  const [localExtensions, setLocalExtensions] = useState("");
  const [localModifiedAfter, setLocalModifiedAfter] = useState("");
  const [localModifiedBefore, setLocalModifiedBefore] = useState("");
  const [localIndexing, setLocalIndexing] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [localProgress, setLocalProgress] = useState<LocalIndexProgress | null>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const { messages: localMessages, isStreaming: localLoading, error: localChatError, sendMessage: sendLocalMessage } = useLocalChatStream();

  async function handleAutoIndex(root: string) {
    try {
      setLocalIndexing(true);
      await indexLocalFiles(root, 3000);
    } catch {
      // L'indexation automatique doit rester silencieuse si la machine n'est pas prête.
    } finally {
      setLocalIndexing(false);
    }
  }

  useEffect(() => {
    fetchLocalConfig()
      .then((config) => {
        const root = config.default_root || "C:\\";
        setLocalRoot(root);
        void handleAutoIndex(root);
      })
      .catch(() => {
        void handleAutoIndex("C:\\");
      });
  }, []);

  useEffect(() => {
    if (!localIndexing && !localLoading) return;
    const poll = async () => {
      try {
        setLocalProgress(await fetchLocalIndexProgress());
      } catch {
        // Le résultat de l'indexation reste la source d'erreur principale.
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 700);
    return () => window.clearInterval(timer);
  }, [localIndexing, localLoading]);

  async function handleIndexLocal() {
    try {
      setLocalIndexing(true);
      setLocalError(null);
      await indexLocalFiles(localRoot, 3000);
    } catch (err) {
      setLocalError((err as Error).message);
    } finally {
      setLocalIndexing(false);
    }
  }

  async function handleSearchLocal() {
    if (!localQuery.trim()) return;
    try {
      setLocalError(null);
      await sendLocalMessage(localQuery, {
        rootPath: localRoot,
        directory: localDirectory || undefined,
        extensions: localExtensions
          ? localExtensions.split(",").map((value) => value.trim()).filter(Boolean)
          : undefined,
        modifiedAfter: localModifiedAfter || undefined,
        modifiedBefore: localModifiedBefore || undefined,
      });
    } catch (err) {
      setLocalError((err as Error).message);
    }
  }

  function onPickDirectory() {
    folderInputRef.current?.click();
  }

  const lastLocalMessage = localMessages[localMessages.length - 1];

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
        <main className="flex-1 overflow-hidden p-4">
          <div className="mb-3 flex gap-2 rounded-lg border bg-card p-1">
            <Button
              variant={mode === "documents" ? "default" : "ghost"}
              className="flex-1"
              onClick={() => setMode("documents")}
            >
              <FileUp className="mr-2 size-4" />
              Chat documentaire
            </Button>
            <Button
              variant={mode === "ordinateur" ? "default" : "ghost"}
              className="flex-1"
              onClick={() => setMode("ordinateur")}
            >
              <FolderSearch className="mr-2 size-4" />
              Question sur mon ordinateur
            </Button>
          </div>

          {mode === "documents" ? (
            <div className="h-[calc(100%-40px)] min-h-0">
              <ChatWindow selectedIds={selectedIds} documentCount={documentCount} />
            </div>
          ) : (
            <div className="h-[calc(100%-40px)] min-h-0 overflow-y-auto rounded-lg border bg-card p-3 shadow-sm">
              <div className="mb-3 flex items-center gap-2">
                <FolderSearch className="size-4 text-primary" />
                <h2 className="text-sm font-semibold">Recherche locale sur l’ordinateur</h2>
              </div>

              <div className="mb-3 flex gap-2">
                <input
                  value={localRoot}
                  onChange={(e) => setLocalRoot(e.target.value)}
                  placeholder="Dossier racine à indexer, ex: C:\\Users\\TonNom\\Documents"
                  className="flex-1 rounded-md border bg-background px-3 py-2 text-sm outline-none ring-0"
                />
                <input
                  ref={folderInputRef}
                  type="file"
                  webkitdirectory="true"
                  className="hidden"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) {
                      const path = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
                      if (path) {
                        setLocalRoot(path.split('/')[0] || localRoot);
                      }
                    }
                  }}
                />
                <Button variant="secondary" onClick={onPickDirectory}>
                  <FolderOpen className="size-4" />
                </Button>
              </div>

              {localProgress && (localIndexing || localLoading || localProgress.status === "completed" || localProgress.status === "error") && (
                <div className="mb-3 rounded-md border bg-background p-3 text-xs">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="font-medium">{localProgress.current_action}</span>
                    <span className="font-semibold tabular-nums">{localProgress.percent}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={localProgress.percent} aria-valuemin={0} aria-valuemax={100}>
                    <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${localProgress.percent}%` }} />
                  </div>
                  <p className="mt-2 truncate text-muted-foreground">
                    {localProgress.processed}/{localProgress.total} fichiers • {localProgress.indexed} indexés • {localProgress.skipped} inchangés
                    {localProgress.current_file ? ` • ${localProgress.current_file}` : ""}
                  </p>
                </div>
              )}

              <div className="mb-3 grid gap-2 md:grid-cols-2">
                <input
                  value={localDirectory}
                  onChange={(e) => setLocalDirectory(e.target.value)}
                  placeholder="Filtre dossier (ex: projets, bureau)"
                  className="rounded-md border bg-background px-3 py-2 text-sm outline-none ring-0"
                />
                <input
                  value={localExtensions}
                  onChange={(e) => setLocalExtensions(e.target.value)}
                  placeholder="Extensions (pdf, docx, txt)"
                  className="rounded-md border bg-background px-3 py-2 text-sm outline-none ring-0"
                />
                <input
                  type="date"
                  value={localModifiedAfter}
                  onChange={(e) => setLocalModifiedAfter(e.target.value)}
                  className="rounded-md border bg-background px-3 py-2 text-sm outline-none ring-0"
                />
                <input
                  type="date"
                  value={localModifiedBefore}
                  onChange={(e) => setLocalModifiedBefore(e.target.value)}
                  className="rounded-md border bg-background px-3 py-2 text-sm outline-none ring-0"
                />
              </div>

              <div className="mb-3 flex gap-2">
                <input
                  value={localQuery}
                  onChange={(e) => setLocalQuery(e.target.value)}
                  placeholder="Ex: contrat de travail, dossier client, migration Python..."
                  className="flex-1 rounded-md border bg-background px-3 py-2 text-sm outline-none ring-0"
                />
                <Button onClick={handleSearchLocal} disabled={localLoading || !localQuery.trim()}>
                  {localLoading ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
                  Chercher
                </Button>
                <Button variant="secondary" onClick={handleIndexLocal} disabled={localIndexing}>
                  {localIndexing ? <Loader2 className="size-4 animate-spin" /> : <FolderSearch className="size-4" />}
                  Indexer
                </Button>
              </div>

              {(localError || localChatError) && <p className="mb-3 text-xs text-red-500">{localError || localChatError}</p>}

              <div className="mb-3 space-y-3 rounded-md border bg-background p-3">
                {localMessages.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Décris ce que tu cherches, par exemple : « mes photos prises à la plage ».
                  </p>
                ) : (
                  localMessages.map((message, index) => (
                    <div key={index} className={cn("rounded-md p-2 text-sm", message.role === "user" ? "ml-8 bg-primary text-primary-foreground" : "mr-8 bg-muted")}>
                      {message.content ? <ReactMarkdown>{message.content}</ReactMarkdown> : "Recherche dans les fichiers locaux…"}
                      {message.sources && message.sources.length > 0 && (
                        <div className="mt-2 space-y-1 border-t pt-2 text-xs">
                          {message.sources.map((source, sourceIndex) => (
                            <a key={source.path} href={getOpenFileUrl(source.path)} target="_blank" rel="noreferrer" className="block truncate text-primary hover:underline">
                              [{sourceIndex + 1}] {source.path}
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>

              {lastLocalMessage?.sources && (
                <div className="space-y-2">
                  {lastLocalMessage.sources.map((result) => (
                    <div key={result.path} className="rounded-md border bg-muted/30 p-2 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate font-medium">{result.filename}</p>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-muted-foreground">score {result.score}</span>
                          <a
                            href={getOpenFileUrl(result.path)}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded border px-2 py-1 text-xs text-primary hover:bg-accent"
                          >
                            Ouvrir
                          </a>
                        </div>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{result.path}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {result.directory} • {result.extension || "fichier"}
                      </p>
                      <p className="mt-2 text-xs text-muted-foreground">{result.snippet}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
