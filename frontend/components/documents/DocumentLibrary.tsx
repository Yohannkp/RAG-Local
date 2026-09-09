"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FileText, FolderOpen, Loader2, Trash2, Upload, AlertTriangle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { deleteDocument, fetchDocuments, uploadDocument } from "@/lib/api";
import type { DocumentItem } from "@/lib/types";

interface DocumentLibraryProps {
  selectedIds: string[];
  onSelectionChange: (ids: string[]) => void;
  onDocumentCountChange?: (count: number) => void;
}

export function DocumentLibrary({
  selectedIds,
  onSelectionChange,
  onDocumentCountChange,
}: DocumentLibraryProps) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setDocuments(await fetchDocuments());
    } catch {
      // La bannière de statut backend (health check) couvre déjà ce cas.
    }
  }, []);

  useEffect(() => {
    onDocumentCountChange?.(documents.length);
  }, [documents.length, onDocumentCountChange]);

  useEffect(() => {
    let cancelled = false;
    fetchDocuments()
      .then((docs) => {
        if (!cancelled) setDocuments(docs);
      })
      .catch(() => {
        // La bannière de statut backend (health check) couvre déjà ce cas.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploadError(null);
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const doc = await uploadDocument(file);
        setDocuments((prev) => [...prev, doc]);
        // Une sélection vide veut dire "tous les documents" : un nouvel
        // import y est donc déjà implicitement inclus, pas besoin de le
        // cocher. On ne l'ajoute à la sélection que si l'utilisateur avait
        // déjà restreint explicitement sa recherche à certains documents.
        if (selectedIds.length > 0) {
          onSelectionChange([...selectedIds, doc.id]);
        }
      }
    } catch (err) {
      setUploadError((err as Error).message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    onSelectionChange(selectedIds.filter((sid) => sid !== id));
    await deleteDocument(id).catch(() => refresh());
  }

  function toggle(id: string) {
    if (selectedIds.includes(id)) {
      onSelectionChange(selectedIds.filter((sid) => sid !== id));
    } else {
      onSelectionChange([...selectedIds, id]);
    }
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          multiple
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
        <Button
          className="w-full"
          variant="secondary"
          disabled={uploading}
          onClick={() => fileInputRef.current?.click()}
        >
          {uploading ? (
            <Loader2 className="animate-spin" />
          ) : (
            <Upload />
          )}
          {uploading ? "Traitement en cours…" : "Importer un document"}
        </Button>
        {uploadError && (
          <Alert variant="destructive" className="mt-2">
            <AlertDescription className="text-xs">{uploadError}</AlertDescription>
          </Alert>
        )}
      </div>

      {documents.length > 0 && (
        <div className="flex items-center justify-between px-1">
          <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Documents ({documents.length})
          </p>
          {selectedIds.length > 0 && (
            <button
              type="button"
              className="text-xs text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => onSelectionChange([])}
            >
              Tout désélectionner
            </button>
          )}
        </div>
      )}
      {documents.length > 0 && (
        <p className="px-1 text-xs text-muted-foreground">
          {selectedIds.length === 0
            ? "Aucune sélection : la recherche porte sur tous les documents."
            : `Recherche restreinte à ${selectedIds.length} document${selectedIds.length > 1 ? "s" : ""}.`}
        </p>
      )}

      <ScrollArea className="flex-1 -mx-1 px-1">
        {documents.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-2 py-10 text-center text-muted-foreground">
            <FolderOpen className="size-8" />
            <p className="text-sm font-medium">Aucun document pour l&apos;instant</p>
            <p className="text-xs">
              Importe un PDF, un Word ou un fichier texte pour commencer.
            </p>
          </div>
        ) : (
          <ul className="space-y-1">
            {documents.map((doc) => (
              <li
                key={doc.id}
                className="group flex items-center gap-2 rounded-md px-2 py-2 hover:bg-accent"
              >
                <Checkbox
                  checked={selectedIds.includes(doc.id)}
                  onCheckedChange={() => toggle(doc.id)}
                />
                <FileText className="size-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{doc.filename}</p>
                  <p className="text-xs text-muted-foreground">
                    {doc.num_chunks} extrait{doc.num_chunks > 1 ? "s" : ""}
                  </p>
                </div>
                {doc.warning && (
                  <Tooltip>
                    <TooltipTrigger className="shrink-0 bg-transparent p-0">
                      <AlertTriangle className="size-4 text-amber-500" />
                    </TooltipTrigger>
                    <TooltipContent>{doc.warning}</TooltipContent>
                  </Tooltip>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7 shrink-0 opacity-0 group-hover:opacity-100"
                  onClick={() => handleDelete(doc.id)}
                >
                  <Trash2 className="size-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </ScrollArea>
    </div>
  );
}
