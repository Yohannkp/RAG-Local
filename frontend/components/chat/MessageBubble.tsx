import { Bot, User } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import type { ChatMessage, Source } from "@/lib/types";
import { SourceCitation } from "./SourceCitation";

interface MessageBubbleProps {
  message: ChatMessage;
  isWarmingUp?: boolean;
  onOpenSource: (source: Source) => void;
}

export function MessageBubble({ message, isWarmingUp, onOpenSource }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}
      >
        {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>
      <div className={cn("flex max-w-[80%] flex-col gap-2", isUser && "items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-2.5 text-sm",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-foreground"
          )}
        >
          {message.content ? (
            <div className="prose prose-sm dark:prose-invert max-w-none prose-p:my-1.5 prose-pre:my-2">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="inline-flex gap-1">
                <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
                <span className="size-1.5 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
                <span className="size-1.5 animate-bounce rounded-full bg-current" />
              </span>
              {isWarmingUp && (
                <span className="text-xs text-muted-foreground">
                  Premier chargement du modèle en mémoire — jusqu&apos;à 30s la
                  première fois…
                </span>
              )}
            </div>
          )}
        </div>
        {message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.sources.map((source) => (
              <SourceCitation key={source.index} source={source} onOpen={onOpenSource} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
