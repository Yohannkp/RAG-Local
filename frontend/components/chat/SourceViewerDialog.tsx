"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { API_URL } from "@/lib/api";
import type { Source } from "@/lib/types";

pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

interface SourceViewerDialogProps {
  source: Source | null;
  onOpenChange: (open: boolean) => void;
}

export function SourceViewerDialog({ source, onOpenChange }: SourceViewerDialogProps) {
  const isPdf = source?.page_number != null;

  return (
    <Dialog open={!!source} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="truncate pr-6">{source?.filename}</DialogTitle>
        </DialogHeader>
        {source && isPdf && (
          // key force un remount (donc un reset de la page affichee) a chaque
          // nouvelle source cliquee, plutot que de synchroniser via useEffect.
          <PdfSourceView
            key={`${source.doc_id}-${source.page_number}`}
            docId={source.doc_id}
            initialPage={source.page_number!}
          />
        )}
        {source && !isPdf && (
          <div className="max-h-[65vh] overflow-auto rounded-md border bg-muted/30 p-4">
            {source.section_title && (
              <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                {source.section_title}
              </p>
            )}
            <p className="text-sm whitespace-pre-wrap">{source.snippet}</p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function PdfSourceView({ docId, initialPage }: { docId: string; initialPage: number }) {
  const [numPages, setNumPages] = useState<number | null>(null);
  const [pageNumber, setPageNumber] = useState(initialPage);

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="max-h-[65vh] w-full overflow-auto rounded-md border bg-muted/30">
        <Document
          file={`${API_URL}/api/documents/${docId}/file`}
          onLoadSuccess={({ numPages: n }) => setNumPages(n)}
          loading={
            <div className="flex items-center gap-2 p-10 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" /> Chargement du PDF…
            </div>
          }
          error={
            <p className="p-10 text-center text-sm text-destructive">
              Impossible de charger le PDF.
            </p>
          }
        >
          <div className="flex justify-center py-2">
            <Page pageNumber={pageNumber} width={560} />
          </div>
        </Document>
      </div>
      {numPages && (
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="icon"
            disabled={pageNumber <= 1}
            onClick={() => setPageNumber((p) => p - 1)}
          >
            <ChevronLeft className="size-4" />
          </Button>
          <span className="text-xs text-muted-foreground">
            Page {pageNumber} / {numPages}
          </span>
          <Button
            variant="outline"
            size="icon"
            disabled={pageNumber >= numPages}
            onClick={() => setPageNumber((p) => p + 1)}
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
