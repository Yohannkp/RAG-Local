"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { fetchHealth, type HealthStatus } from "@/lib/api";

export function HealthBanner() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((h) => !cancelled && setHealth(h))
      .catch(() => !cancelled && setHealth({ ollama_reachable: false, models: {} }))
      .finally(() => !cancelled && setChecked(true));
    return () => {
      cancelled = true;
    };
  }, []);

  if (!checked || !health) return null;

  const missingModels = Object.entries(health.models)
    .filter(([, present]) => !present)
    .map(([name]) => name);

  if (health.ollama_reachable && missingModels.length === 0) return null;

  return (
    <Alert variant="destructive" className="rounded-none border-x-0 border-t-0">
      <AlertTriangle className="size-4" />
      <AlertTitle>
        {!health.ollama_reachable
          ? "Ollama est injoignable"
          : "Modèle(s) manquant(s) dans Ollama"}
      </AlertTitle>
      <AlertDescription>
        {!health.ollama_reachable
          ? "Vérifie qu'Ollama tourne bien en local (ollama serve) sur le port 11434."
          : `Lance : ${missingModels.map((m) => `ollama pull ${m}`).join(" && ")}`}
      </AlertDescription>
    </Alert>
  );
}
