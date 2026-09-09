"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Mic, MicOff, Send } from "lucide-react";
import SpeechRecognition, { useSpeechRecognition } from "react-speech-recognition";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
  placeholder?: string;
}

export function ChatInput({ onSend, disabled, placeholder }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [mounted, setMounted] = useState(false);
  const baseTextRef = useRef("");
  const { transcript, listening, resetTranscript, browserSupportsSpeechRecognition } =
    useSpeechRecognition();

  // browserSupportsSpeechRecognition ne peut etre determine que cote client
  // (l'API n'existe pas en environnement Node) : l'evaluer directement dans
  // le rendu produirait un mismatch d'hydratation SSR/client. Pattern
  // "mounted flag" standard — pas d'alternative sans effet ici.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!listening) return;
    setValue(`${baseTextRef.current}${baseTextRef.current ? " " : ""}${transcript}`);
  }, [transcript, listening]);

  function toggleMic() {
    if (listening) {
      SpeechRecognition.stopListening();
      return;
    }
    baseTextRef.current = value;
    resetTranscript();
    SpeechRecognition.startListening({ language: "fr-FR" });
  }

  function submit() {
    const text = value.trim();
    if (!text || disabled) return;
    if (listening) SpeechRecognition.stopListening();
    onSend(text);
    setValue("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="flex items-end gap-2 border-t bg-background p-3">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={1}
        placeholder={placeholder ?? "Pose une question sur tes documents…"}
        className="max-h-40 flex-1 resize-none rounded-md border bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      {mounted && browserSupportsSpeechRecognition && (
        <Tooltip>
          <TooltipTrigger
            className={
              listening
                ? "bg-destructive text-white hover:bg-destructive/90"
                : "bg-secondary text-secondary-foreground hover:bg-secondary/80"
            }
            onClick={toggleMic}
          >
            {listening ? <MicOff className="size-4" /> : <Mic className="size-4" />}
          </TooltipTrigger>
          <TooltipContent className="max-w-56 text-xs">
            {listening
              ? "Arrêter la dictée"
              : "Dicter ta question (reconnaissance vocale du navigateur — peut passer par un service en ligne selon le navigateur, contrairement au reste de l'app)"}
          </TooltipContent>
        </Tooltip>
      )}
      <Button size="icon" disabled={disabled || !value.trim()} onClick={submit}>
        <Send className="size-4" />
      </Button>
    </div>
  );
}
