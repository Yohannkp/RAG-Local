import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { Source } from "@/lib/types";

function sourceLabel(source: Source): string {
  if (source.page_number != null) return `${source.filename} · p.${source.page_number}`;
  if (source.section_title) return `${source.filename} · ${source.section_title}`;
  return source.filename;
}

interface SourceCitationProps {
  source: Source;
  onOpen: (source: Source) => void;
}

export function SourceCitation({ source, onOpen }: SourceCitationProps) {
  const preview =
    source.snippet.length > 220 ? `${source.snippet.slice(0, 220)}…` : source.snippet;

  return (
    <Tooltip>
      <TooltipTrigger
        className="inline-flex cursor-pointer items-center gap-1 rounded-full border bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground hover:bg-accent"
        onClick={() => onOpen(source)}
      >
        [{source.index}] {sourceLabel(source)}
      </TooltipTrigger>
      <TooltipContent className="max-w-xs whitespace-pre-wrap text-xs">
        {preview}
      </TooltipContent>
    </Tooltip>
  );
}
